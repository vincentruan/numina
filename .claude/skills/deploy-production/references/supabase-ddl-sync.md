# Supabase DDL Sync Reference

> **Scope:** Keeping the Supabase standby schema aligned with the primary database after alembic migrations.
> Loaded when: deploying new migrations, replication errors referencing missing columns/tables, or periodic DDL audits.

## Why Manual DDL Sync

PostgreSQL logical replication (`pg_subscription`) replicates **DML only** (INSERT/UPDATE/DELETE). It does **not** replicate DDL (CREATE TABLE, ALTER TABLE, etc.).

After every `alembic upgrade head` on the primary, the equivalent DDL **must** be applied to the Supabase standby manually. If the standby schema falls behind:

- Replicated DML may reference non-existent columns/tables → **replication breaks**
- Data loss risk if the primary fails and you failover to an incomplete standby

## Quick Reference

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a

# Compare table counts
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  echo -n 'Main:    ' &&
  sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c \
    \"SELECT count(*) FROM pg_tables WHERE schemaname='public';\" | tr -d ' ' &&
  echo -n 'Supabase:' &&
  python3 -c \"
import psycopg
conn = psycopg.connect(host='db.vywwletyvrzyoozhsfqu.supabase.co', port=5432,
    user='postgres', password='sH6UCW4GG5smG',
    dbname='postgres', sslmode='require')
print(conn.execute(\\\"SELECT count(*) FROM pg_tables WHERE schemaname='public'\\\").fetchone()[0])
conn.close()
\"
"
# Expected: Main 95, Supabase 94 (差 1 = _cdc_test 内部表，正常)
```

## Network Constraint: Why Host Python

Supabase domains (`db.<project>.supabase.co`) resolve **only** to AAAA (IPv6) records — no A record exists. See [ipv6-disk-recovery.md](./ipv6-disk-recovery.md) §Supabase Has No IPv4.

| Environment | Can reach Supabase? | Why |
|-------------|---------------------|-----|
| Server host | ✅ Yes | Host has IPv6 connectivity |
| Docker container (bridge) | ❌ No | Container DNS can't resolve AAAA-only domains |
| Docker container (`--network host`) | ❌ No | Even with host networking, container resolver fails for these domains |
| Docker container (internal PG replication) | ✅ Yes | PostgreSQL's logical replication worker uses its own connection handling |

**Solution:** Install `psycopg` on the server host and run DDL scripts directly from the host's Python.

### One-time setup

```bash
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "pip3 install psycopg[binary]"
```

This only needs to be done once. Already installed: psycopg 3.3.6 on server host.

## Step-by-Step: DDL Sync Procedure

### Step 1: Identify the gap

Use Python on the server to compare table lists and find missing tables:

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "python3 << 'PYEOF'
import psycopg, subprocess

# Main DB tables
result = subprocess.run(
    ['sudo', 'docker', 'exec', 'numina-postgres-prod', 'psql', '-U', 'numina', '-d', 'numina_prod',
     '-t', '-c', \"SELECT tablename FROM pg_tables WHERE schemaname='public'\"],
    capture_output=True, text=True)
main_tables = set(l.strip() for l in result.stdout.strip().split('\n') if l.strip())

# Supabase tables
conn = psycopg.connect(host='db.vywwletyvrzyoozhsfqu.supabase.co', port=5432,
    user='postgres', password='sH6UCW4GG5smG', dbname='postgres', sslmode='require')
supa_tables = set(r[0] for r in conn.execute(\"SELECT tablename FROM pg_tables WHERE schemaname='public'\"))
conn.close()

missing = main_tables - supa_tables - {'_cdc_test'}
print(f'Main: {len(main_tables)}, Supabase: {len(supa_tables)}, Missing: {len(missing)}')
for t in sorted(missing): print(f'  - {t}')
PYEOF"
```

### Step 2: Get DDL from main DB

For missing tables, extract column definitions, indexes, and constraints in one query pass:

```bash
# Column definitions
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c "
  SELECT table_name, column_name, data_type, character_maximum_length,
         numeric_precision, is_nullable, column_default, udt_name
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='<table>'
  ORDER BY ordinal_position;"

# Indexes (use indexdef — it's the complete CREATE INDEX statement)
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c "
  SELECT indexdef FROM pg_indexes
  WHERE schemaname='public' AND tablename='<table>' AND indexname NOT LIKE '%_pkey';"

# Foreign keys
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c "
  SELECT conname, pg_get_constraintdef(oid)
  FROM pg_constraint
  WHERE conrelid='<table>'::regclass AND contype='f';"
```

For column additions to existing tables, check what columns the migration added by comparing `information_schema.columns` on both sides.

### Step 3: Generate and apply DDL script

Create a Python script on the server that applies the DDL. **Critical rules:**

1. **Parent tables first** — tables with no FK deps on other new tables (e.g. `learning_topics`)
2. **Child tables next** — tables with FK references to parent tables (respect FK dependency chain)
3. **Indexes after tables** — `CREATE INDEX IF NOT EXISTS` for all secondary indexes
4. **Column additions last** — `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for existing tables
5. **`IF NOT EXISTS`** — use on all CREATE TABLE/INDEX/SEQUENCE for idempotency

```python
# /tmp/supabase_ddl_sync.py
import psycopg

CONN = {
    "host": "db.vywwletyvrzyoozhsfqu.supabase.co",
    "port": 5432,
    "user": "postgres",
    "password": "sH6UCW4GG5smG",
    "dbname": "postgres",
    "sslmode": "require",
}

DDL = [
    # 1) Parent tables (no FK deps on other new tables)
    "CREATE TABLE IF NOT EXISTS learning_topics ( ... )",
    "CREATE TABLE IF NOT EXISTS learning_clusters ( ... )",

    # 2) Child tables (FK deps on parent tables — order matters!)
    "CREATE TABLE IF NOT EXISTS learning_assignments ( ... REFERENCES learning_topics(id) )",
    "CREATE TABLE IF NOT EXISTS learning_sessions ( ... REFERENCES learning_assignments(id) )",
    "CREATE TABLE IF NOT EXISTS learning_progress ( ... )",
    "CREATE TABLE IF NOT EXISTS learning_dependencies ( ... )",
    "CREATE TABLE IF NOT EXISTS learning_assessment_attempts ( ... REFERENCES learning_sessions(id) )",

    # 3) Indexes
    "CREATE INDEX IF NOT EXISTS ix_... ON ...",

    # 4) Column additions to existing tables
    "ALTER TABLE existing_table ADD COLUMN IF NOT EXISTS new_col TYPE",
]

conn = psycopg.connect(**CONN)
conn.autocommit = True
ok = fail = 0
for i, stmt in enumerate(DDL):
    try:
        conn.execute(stmt); ok += 1
    except Exception as e:
        fail += 1
        print(f"  [WARN] #{i+1}: {e}")
cur = conn.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
print(f"\n=== {ok} OK, {fail} warnings | tables: {cur.fetchone()[0]} ===")
conn.close()
```

Transfer and execute:

```bash
scp -P ${DEPLOY_SSH_PORT} /tmp/supabase_ddl_sync.py ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST}:/tmp/
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "python3 /tmp/supabase_ddl_sync.py"
```

### Step 4: Verify alignment

```bash
# Table counts: Main 95, Supabase 94 (差 1 = _cdc_test)
# 如果差 > 1，说明有表遗漏

# Verify subscription still healthy
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c \
  "SELECT subname, subenabled FROM pg_subscription;"
# Both should show subenabled = t
```

## Known Table Counts (history)

| Date | Main | Supabase | Trigger | Notes |
|------|------|----------|---------|-------|
| 2026-09-27 | 95 | 94 | learning OS (7 tables) + travel + column adds | 28 DDL statements, 0 warnings |
| 2026-09-22 | 88 | 87 | Initial sync after bootstrap | Gap = 1 (`_cdc_test`) |

`_cdc_test` is a Supabase internal test table created on the primary during CDC setup. It exists on the primary but not on the subscriber — this is expected and not a gap.

## Supabase Connection Info

Found via:
```bash
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c \
  "SELECT subname, subconninfo FROM pg_subscription;"
```

Current connections:

| Subscription | Host | DB | User |
|-------------|------|----|------|
| `numina_sub` | `db.vywwletyvrzyoozhsfqu.supabase.co:5432` | `postgres` | `postgres` |
| `deerflow_sub` | `db.vywwletyvrzyoozhsfqu.supabase.co:5432` | `numina_deerflow` | `postgres` |

Password: see `subconninfo` output (not stored here for security). Use the query above to retrieve.

DDL sync is only needed for `numina_sub` (the `postgres` database). The DeerFlow database is self-managing via `init_engine()`.

## FK Dependency Order (learning_* example)

When creating multiple related tables, the dependency chain determines creation order:

```
learning_topics        ← no FK deps (parent)
learning_clusters      ← no FK deps (parent)
    ↓
learning_assignments   ← FK → topics, users, families
    ↓
learning_sessions      ← FK → assignments, topics, users
    ↓
learning_assessment_attempts ← FK → sessions, topics, users

learning_progress      ← FK → topics, users (independent chain)
learning_dependencies  ← FK → topics (self-referencing)
```

**Rule:** If table B has `REFERENCES table_a(id)`, table A must appear earlier in the DDL list.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `failed to resolve host` | Container can't resolve IPv6-only domain | Use host Python, not container |
| `relation "xxx_seq" does not exist` | CREATE TABLE references sequence before it's created | Reorder: CREATE SEQUENCE before CREATE TABLE |
| `relation "trips" does not exist` | FK references table not yet created | Reorder: parent tables before child tables |
| `connection refused` | Supabase project paused or network issue | Check Supabase dashboard; verify IPv6 route on host |
| `duplicate key value violates unique constraint` | Table/data already exists from partial sync | Use `IF NOT EXISTS` on all DDL statements |
| Table count gap > expected | Missing tables or `_cdc_test` replicated | Run Step 1 to identify exact missing tables |
| `psycopg` not found | First time — not installed on host | `pip3 install psycopg[binary]` (one-time) |

## When to Run

- **After every `alembic upgrade head`** that creates tables or adds columns
- **Before deploying new images** (DDL gate in Mode A Step 5b)
- **Periodically** as a health check (compare table counts)
- **After replication errors** that reference missing schema objects
