---
name: deploy-production
description: >
  Deploy Numina to the production Linux Docker server via GitHub mirror.
  Triggers on: "部署到生产", "deploy to production", "上线", "发布",
  "更新生产环境", "deploy prod", "pull and deploy", "服务器更新",
  "更新服务器", "make deploy-images", "拉取最新镜像", or any request
  to deploy/update the live Numina instance. Also use when the user
  mentions server health check, disk cleanup, or database migration
  on the production server.
---

# Production Deployment Skill

Deploy Numina to the production Docker server using pre-built GHCR images.
The server never builds locally — it pulls images built by GitHub Actions CI.

> **Note:** The production server uses `docker-compose.yml` (the default).
> `docker-compose.production.yml` is an alternative profile — do not mix them.

## Architecture

```
GitHub Push → CI builds images → GHCR
                                      ↓
Local: SSH → git pull → disk check → make deploy-images → alembic → health check
```

## Prerequisites

SSH connection details are stored in `.claude/deploy.env` (gitignored).
If it doesn't exist, ask the user for these values and create it:

```bash
# .claude/deploy.env — DO NOT COMMIT
DEPLOY_SSH_HOST=<your-server-ip>
DEPLOY_SSH_PORT=<your-ssh-port>
DEPLOY_SSH_USER=<your-ssh-user>
DEPLOY_REMOTE_DIR=~/data/numina
```

Read this file at the start of every deployment to get connection parameters.

### Variable Sourcing

Shell state does NOT persist between bash calls. Source the env file in every
command block that uses `$DEPLOY_SSH_HOST` etc.:

```bash
set -a && source .claude/deploy.env && set +a
# Now $DEPLOY_SSH_HOST, $DEPLOY_SSH_PORT, $DEPLOY_SSH_USER, $DEPLOY_REMOTE_DIR are set
```

Without this step, the variables expand to empty strings and SSH commands fail silently.

## Deployment Workflow

Execute these phases in order. Each phase checks for failure before proceeding.

### Phase 1: Connect & Assess

```bash
ssh -p $DEPLOY_SSH_PORT $DEPLOY_SSH_USER@$DEPLOY_SSH_HOST
```

Once connected, gather baseline state in a single SSH call:

```bash
cd $DEPLOY_REMOTE_DIR && \
  echo "=== GIT ===" && \
  git log --oneline -3 && \
  echo "=== DISK ===" && \
  df -h / | tail -1 && \
  echo "=== DOCKER ===" && \
  docker system df && \
  echo "=== CONTAINERS ===" && \
  docker compose ps --format 'table {{.Name}}\t{{.Status}}'
```

### Phase 2: Disk Space Check

**Critical threshold: 85% usage or < 2GB free.**

If disk is tight, clean up before deploying (cleaning during deployment fails with "No space left on device"):

```bash
# Clean Docker build cache first (usually 2-4GB)
docker builder prune -af

# Then clean unused images if still tight
docker image prune -af --filter "until=48h"
```

Verify with `df -h /` after cleanup. Abort if still < 1GB free.

### Phase 3: Pull Latest Code

```bash
cd $DEPLOY_REMOTE_DIR && git pull origin main
```

If there are conflicts, stop and report — don't try to resolve them on the server.

### Phase 4: Deploy Images

```bash
cd $DEPLOY_REMOTE_DIR && make deploy-images
```

This will:
1. Ensure GHCR image URLs are in `.env`
2. `docker compose pull` all 5 services
3. `docker compose down` then `up -d`
4. Wait for backend health check
5. Verify `/api/health` returns OK

If `make deploy-images` fails, check the output for:
- **Pull errors** → GHCR auth issue or network problem
- **Space errors** → go back to Phase 2, clean more aggressively
- **Health check timeout** → backend failed to start, check logs: `docker compose logs --tail 50 backend`

### Phase 5: Database Migration

The database is PostgreSQL (Supabase). The `alembic_version` table may be out of sync if the DB was originally bootstrapped from `Base.metadata` (tables exist but migration history is empty).

**Step 1: Check current state**

Write a helper script to the server and run it inside the backend container:

```bash
# Write check script
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

# Copy into container and run (discover container name dynamically)
CONTAINER=$(docker compose -f $DEPLOY_REMOTE_DIR/docker-compose.yml ps -q backend)
docker cp /tmp/check_db.py $CONTAINER:/tmp/check_db.py
docker compose -f $DEPLOY_REMOTE_DIR/docker-compose.yml exec -T backend sh -c 'cd /app && uv run python /tmp/check_db.py'
```

**Step 2: Decide migration strategy**

| `alembic_version` state | Action |
|------------------------|--------|
| Empty / no rows | DB was bootstrapped. `stamp` to current head, then check if any new tables/columns need manual creation. |
| At latest head | No migration needed. |
| Behind latest head | `alembic upgrade head` — but if intermediate migrations fail with "duplicate column/table", stamp to head instead (tables already exist from bootstrap). |

**Step 2b: Before stamping, check for genuinely new schema objects**

Stamping past a migration means its DDL never runs. If a migration creates a
table or column that the bootstrap didn't include, the app will crash at runtime.

To check, compare what the codebase expects vs what the server has:

```bash
# On the LOCAL machine — what tables/columns does the current codebase expect?
cd server/apps/backend && uv run python -c "
from app.database import Base
for t in sorted(Base.metadata.tables):
    cols = [c.name for c in Base.metadata.tables[t].columns]
    print(f'{t}: {cols}')
"
```

Compare against the server's `total_tables` output from Step 1. If a table
or column exists in the code but is absent on the server, you have two options:

1. **Run just that migration** — stamp to the migration *before* the new one,
   then `upgrade head` to apply only the genuinely new DDL.
2. **Create manually** — if only a column is missing, add it directly:
   ```bash
   docker compose exec -T backend sh -c "cd /app && uv run python -c \"
   from sqlalchemy import create_engine, text
   import os
   e = create_engine(os.environ['DATABASE_URL'])
   with e.begin() as c:
       c.execute(text('ALTER TABLE users ADD COLUMN username_change_history TEXT'))
   \""
   ```

Then stamp to head.

**Step 3: Execute**

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

**Why stamp instead of upgrade?** The bootstrap process (`b00t5trap0001`) creates all tables from `Base.metadata` directly, bypassing alembic history. This means the schema is already at the latest version but `alembic_version` has no record. Running `upgrade` tries to re-create existing tables/columns and fails. Stamping tells alembic "the DB is already at this version" without executing DDL.

### Phase 6: Health Check

Run all checks in a single SSH call:

```bash
cd $DEPLOY_REMOTE_DIR && \
  echo "=== CONTAINERS ===" && \
  docker compose ps --format 'table {{.Name}}\t{{.Status}}' && \
  echo "=== API HEALTH ===" && \
  curl -sf http://localhost/api/health && \
  echo && \
  echo "=== FRONTEND ===" && \
  curl -sf -o /dev/null -w "HTTP %{http_code}" http://localhost/ && \
  echo && \
  echo "=== DISK ===" && \
  df -h / | tail -1
```

**Success criteria:**
- All 6 containers running (backend, agent, scheduler_worker, frontend-main, frontend-child, nginx)
- Backend/agent/scheduler_worker/frontend-child show `(healthy)`
- `/api/health` returns `{"status":"ok"}`
- Frontend returns HTTP 200

## Quick Reference

| Task | Command |
|------|---------|
| Full deploy | Follow all phases above |
| Just pull images | Phase 4 only |
| Just run migrations | Phase 5 only |
| Check health | Phase 6 only |
| View backend logs | `docker compose logs --tail 100 -f backend` |
| Restart single service | `docker compose restart backend` |
| Emergency rollback | `git checkout <commit> && make deploy-images` — only works for commits pushed to main (CI must have built GHCR images) |

## Troubleshooting

### "No space left on device"
Disk is full. Run `docker builder prune -af && docker image prune -af`. Then retry.

### "DuplicateTable" / "DuplicateColumn" during migration
DB was bootstrapped, tables already exist. Use `stamp head` instead of `upgrade head`.

### Container unhealthy after deploy
Check logs: `docker compose logs --tail 50 <service>`. Common causes:
- Missing env var → check `.env`
- DB connection failure → check `DATABASE_URL`
- Port conflict → `ss -tlnp | grep <port>`

### GHCR pull fails
Check `.env` has correct `*_IMAGE` URLs. If auth needed:
```bash
echo "<GITHUB_TOKEN>" | docker login ghcr.io -u <username> --password-stdin
```
