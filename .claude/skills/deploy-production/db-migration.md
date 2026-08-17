# Database Migration Reference

Run this **before** starting new containers. The production image contains alembic + all migration files; a throwaway backend container applies the DDL.

## Why proactive migration

Deploying new code first, then running migrations → new code references columns that don't exist yet → crash loops, corrupted sessions, slow responses. Always migrate schema **before** service startup.

## Quick Reference

```bash
# Source deploy config (every command block)
set -a && source .claude/deploy.env && set +a

# 1. Check current state
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} 'cd $DEPLOY_REMOTE_DIR &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic current 2>&1 &&
    echo \"---\" &&
    uv run alembic heads 2>&1
  "'

# 2. Run migration (if behind)
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} 'cd $DEPLOY_REMOTE_DIR &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic upgrade head 2>&1
  "'

# 3. If DuplicateColumn/DuplicateTable → read the "Handle Failures" section below
```

## Alembic Path

The production image's `WORKDIR=/app`, `alembic.ini` at `/app/apps/backend/alembic.ini` with `script_location = apps/backend/alembic`. Running `uv run alembic ...` from `/app` auto-detects it. No `-c` flag needed.

`docker compose run --rm --no-deps backend` spins up a throwaway container from the new image with access to the DB via `.env`. No port conflicts, no health check interference.

## Step 1: Check Current State

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} 'cd $DEPLOY_REMOTE_DIR &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic current && uv run alembic heads
  "'
```

**Output interpretation:**

| Output | Meaning | Action |
|--------|---------|--------|
| `abc123 (head)` — same revision | Up to date | Skip migration |
| `abc123` then `def456 (head)` | Behind | Run Step 2 |
| `FAILED: Can't locate revision` | Version ahead of code | Investigate (wrong image?) |

## Step 2: Run Migration

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} 'cd $DEPLOY_REMOTE_DIR &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic upgrade head 2>&1
  "'
```

If it succeeds → done. Proceed to deploy.

## Step 3: Handle Failures

### Failure: DuplicateColumn / DuplicateTable

A column or table already exists. This happens when the DB was bootstrapped via `Base.metadata.create_all()` (fresh-DB path) or a previous partial migration.

**Do NOT blindly `stamp head`** — that skips ALL pending migrations, including ones with genuinely new DDL.

Instead, handle per-migration:

**Case A: The failing migration's object already exists**

1. Note which migration failed (e.g., `ua1v2a3t4r5u` — `column "avatar_url" already exists`)
2. Stamp just that revision (tells alembic "this migration is done"):
   ```bash
   ssh ... 'cd $DEPLOY_REMOTE_DIR && sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
     cd /app && uv run alembic stamp <failed-revision-id>
   "'
   ```
3. Re-run `upgrade head` to continue with remaining migrations

**Case B: A migration partially applied (some columns created, others not)**

This happens with PostgreSQL transactional DDL when `batch_alter_table` issues multiple statements. Check what's actually in the DB:

```bash
ssh ... 'cd $DEPLOY_REMOTE_DIR && sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
  cd /app && uv run python -c \"
from sqlalchemy import create_engine, inspect
import os
e = create_engine(os.environ[\\\"DATABASE_URL\\\"])
i = inspect(e)
for t in [\\\"<table_name>\\\"]:
    print(f\\\"{t}: {[c[\\\\\\\"name\\\\\\\"] for c in i.get_columns(t)]}\\\")
\"
"'
```

Manually add missing objects:

```bash
ssh ... 'cd $DEPLOY_REMOTE_DIR && sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
  cd /app && uv run python -c \"
from sqlalchemy import create_engine, text
import os
e = create_engine(os.environ[\\\"DATABASE_URL\\\"])
with e.connect() as conn:
    conn.execute(text(\\\"ALTER TABLE <table> ADD COLUMN IF NOT EXISTS <col> <type>\\\"))
    conn.commit()
\"
"'
```

Then stamp the failed revision + `upgrade head`.

**Case C: Empty alembic_version (bootstrap-only DB)**

Stamp to the last known-good revision before the new migrations, then upgrade:

```bash
# Stamp to current head in the OLD image (before new migrations)
# Then upgrade to apply only the new ones
ssh ... 'cd $DEPLOY_REMOTE_DIR && sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
  cd /app && uv run alembic stamp <old-head-revision> && uv run alembic upgrade head
"'
```

If the DB was bootstrapped from the same code version as the new image, stamp directly to `head`.

## Prevention: Idempotent Migrations

All new migrations MUST include existence checks. Use this template:

```python
def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Column guard
    existing = {c["name"] for c in inspector.get_columns("table_name")}
    if "new_column" not in existing:
        op.add_column("table_name", sa.Column("new_column", sa.String(100), nullable=True))

    # Table guard
    if "new_table" not in {t["name"] for t in inspector.get_tables()}:
        op.create_table("new_table", ...)
```

This allows `upgrade head` to run safely on any DB state — fresh, bootstrapped, or partially migrated.

## Post-Migration Verification

After migration, verify no errors in backend logs after restart:

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} 'cd $DEPLOY_REMOTE_DIR &&
  sudo docker compose -f docker-compose.production.yml restart backend &&
  sleep 10 &&
  sudo docker compose -f docker-compose.production.yml logs --since 15s backend 2>&1 | grep -i "error\|traceback" || echo "✓ No errors"
'
```
