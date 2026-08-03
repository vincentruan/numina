# Database Migration Reference

Read this when `alembic_version` is empty, behind head, or migrations fail with duplicate errors.

## Background

The server DB (PostgreSQL) was originally bootstrapped via `b00t5trap0001` — it creates all tables from `Base.metadata` directly, bypassing alembic history. Schema is current but `alembic_version` has no record. Running `upgrade head` tries to re-create existing tables/columns and fails.

## Decision Table

| `alembic_version` state | Action |
|------------------------|--------|
| Empty / no rows | Stamp to current head, then check for genuinely new schema objects |
| At latest head | No migration needed |
| Behind latest head | Try `upgrade head` first; if DuplicateTable/Column → stamp to head |

## Step 1: Check Current State

```bash
# Write check script to server
cat > /tmp/check_db.py << 'PYEOF'
import os
from sqlalchemy import create_engine, text, inspect

url = os.environ["DATABASE_URL"]
e = create_engine(url)
i = inspect(e)
tables = set(i.get_table_names())
with e.connect() as c:
    r = c.execute(text("SELECT version_num FROM alembic_version"))
    rows = [row[0] for row in r]
    print(f"alembic_version: {rows}")
    print(f"total_tables: {len(tables)}")
PYEOF

CONTAINER=$(docker compose -f $DEPLOY_REMOTE_DIR/docker-compose.yml ps -q backend)
docker cp /tmp/check_db.py $CONTAINER:/tmp/check_db.py
docker compose -f $DEPLOY_REMOTE_DIR/docker-compose.yml exec -T backend sh -c 'cd /app && uv run python /tmp/check_db.py'
```

## Step 2: Check for Genuinely New Schema Objects

Stamping past a migration means its DDL never runs. If a migration creates a table or column that the bootstrap didn't include, the app will crash at runtime.

Compare what the codebase expects vs what the server has:

```bash
# Run LOCALLY — what tables/columns does the current codebase expect?
cd server/apps/backend && uv run python -c "
from app.database import Base
for t in sorted(Base.metadata.tables):
    cols = [c.name for c in Base.metadata.tables[t].columns]
    print(f'{t}: {cols}')
"
```

Compare against the server's `total_tables` output from Step 1. If a table or column exists in the code but is absent on the server:

1. **Run just that migration** — stamp to the migration *before* the new one, then `upgrade head` to apply only the genuinely new DDL.
2. **Create manually** — if only a column is missing, add it directly:
   ```bash
   docker compose exec -T backend sh -c "cd /app && uv run python -c \"
   from sqlalchemy import create_engine, text
   import os
   e = create_engine(os.environ['DATABASE_URL'])
   with e.begin() as c:
       c.execute(text('ALTER TABLE <table> ADD COLUMN <col> <type>'))
   \""
   ```

Then stamp to head.

## Step 3: Execute

```bash
# If empty — stamp to head
docker compose exec -T backend sh -c \
  'cd /app && uv run alembic -c /app/apps/backend/alembic.ini stamp head'

# If behind — try upgrade first
docker compose exec -T backend sh -c \
  'cd /app && uv run alembic -c /app/apps/backend/alembic.ini upgrade head'

# If upgrade fails with DuplicateTable/DuplicateColumn — stamp to head
docker compose exec -T backend sh -c \
  'cd /app && uv run alembic -c /app/apps/backend/alembic.ini stamp head'
```
