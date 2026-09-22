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
# 1. Check table count gap
set -a && source .claude/skills/deploy-production/deploy.env && set +a

# Main DB count
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c \
    \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';\"
"

# Supabase count (via host Python — containers can't resolve Supabase IPv6)
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "python3 -c '
import psycopg
conn = psycopg.connect(host=\"db.vywwletyvrzyoozhsfqu.supabase.co\", port=5432,
    user=\"postgres\", password=\"<SUPABASE_PASSWORD>\",
    dbname=\"postgres\", sslmode=\"require\")
print(conn.execute(\"SELECT count(*) FROM pg_tables WHERE schemaname='\''public'\''\").fetchone()[0])
conn.close()
'"

# 2. If gap exists → generate DDL from main, apply to Supabase (see full procedure below)
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

This only needs to be done once. The `psycopg` package is small and has no system dependencies (uses the bundled `psycopg-binary` wheel).

## Step-by-Step: DDL Sync Procedure

### Step 1: Identify the gap

Compare table lists between main DB and Supabase:

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a

# Main DB tables
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c \
    \"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;\"
"

# Supabase tables
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "python3 -c '
import psycopg
conn = psycopg.connect(host=\"db.vywwletyvrzyoozhsfqu.supabase.co\", port=5432,
    user=\"postgres\", password=\"<SUPABASE_PASSWORD>\",
    dbname=\"postgres\", sslmode=\"require\")
for r in conn.execute(\"SELECT tablename FROM pg_tables WHERE schemaname='\''public'\'' ORDER BY tablename\"):
    print(r[0])
conn.close()
'"
```

Also check for column differences on existing tables:

```bash
# Example: check wishes table columns on both sides
# Main DB:
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c \
  "SELECT column_name FROM information_schema.columns WHERE table_name='wishes' ORDER BY ordinal_position;"

# Supabase: (same query via Python)
```

### Step 2: Get DDL from main DB

For missing tables, extract column definitions:

```bash
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  for tbl in <table1> <table2>; do
    echo \"--- \$tbl ---\"
    sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c \"
      SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
      FROM information_schema.columns
      WHERE table_schema='public' AND table_name='\$tbl'
      ORDER BY ordinal_position;
    \"
  done
"
```

### Step 3: Generate and apply DDL script

Create a Python script on the server that applies the DDL. **Critical rules:**

1. **Sequences first** — `CREATE SEQUENCE` must come before `CREATE TABLE` that references it via `nextval()`
2. **Parent tables first** — tables with FK references must be created before child tables
3. **`IF NOT EXISTS`** — use on all CREATE TABLE/INDEX/SEQUENCE for idempotency
4. **`ADD COLUMN IF NOT EXISTS`** — for ALTER TABLE additions

```python
# /tmp/supabase_ddl_sync.py
import psycopg, sys

CONN = {
    "host": "db.<project>.supabase.co",
    "port": 5432,
    "user": "postgres",
    "password": "<PASSWORD>",
    "dbname": "postgres",
    "sslmode": "require",
}

DDL = [
    # 1) Sequences FIRST
    "CREATE SEQUENCE IF NOT EXISTS <table>_id_seq",
    # ... more sequences ...

    # 2) Parent tables (no FK deps)
    "CREATE TABLE IF NOT EXISTS parent_table ( ... )",
    # 3) Child tables (with FK deps)
    "CREATE TABLE IF NOT EXISTS child_table ( ... REFERENCES parent_table(id) )",
    # 4) Indexes
    "CREATE INDEX IF NOT EXISTS ix_<table>_<col> ON <table>(<col>)",
    # 5) Column additions to existing tables
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
# Table counts should match (or differ by 1 for _cdc_test)
# Main DB: 88 tables (includes _cdc_test internal table)
# Supabase: 87 tables (_cdc_test not replicated — this is expected)

# Verify subscription still healthy
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c \
  "SELECT subname, subenabled FROM pg_subscription;"
# Both should show subenabled = t
```

## Expected Table Count

| Database | Tables | Notes |
|----------|--------|-------|
| Main (`numina_prod`) | 88 | Includes `_cdc_test` (Supabase internal) |
| Supabase standby | 87 | `_cdc_test` not needed on subscriber |

If the gap is exactly 1 and the missing table is `_cdc_test`, no action needed.

## Supabase Connection Info

To find the current Supabase connection parameters:

```bash
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c \
  "SELECT subname, subconninfo FROM pg_subscription;"
```

There are typically two subscriptions:
- `numina_sub` → connects to `postgres` database (main app tables)
- `deerflow_sub` → connects to `numina_deerflow` database (DeerFlow checkpoint tables)

DDL sync is only needed for `numina_sub` (the `postgres` database). The DeerFlow database is self-managing.

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `failed to resolve host` | Container can't resolve IPv6-only domain | Use host Python, not container |
| `relation "xxx_seq" does not exist` | CREATE TABLE references sequence before it's created | Reorder: CREATE SEQUENCE before CREATE TABLE |
| `relation "trips" does not exist` | FK references table not yet created | Reorder: parent tables before child tables |
| `connection refused` | Supabase project paused or network issue | Check Supabase dashboard; verify IPv6 route on host |
| `duplicate key value violates unique constraint` | Table/data already exists from partial sync | Use `IF NOT EXISTS` on all DDL statements |

## When to Run

- **After every `alembic upgrade head`** that creates tables or adds columns
- **Before deploying new images** (DDL gate in Mode A Step 5b)
- **Periodically** as a health check (compare table counts)
- **After replication errors** that reference missing schema objects
