---
name: deploy-production
description: >
  Use when deploying Numina to the production Linux Docker server, pulling
  latest GHCR images, running database migrations, or performing server
  maintenance (health check, disk cleanup, rollback). Triggers: "部署到生产",
  "deploy to production", "上线", "发布", "deploy prod", "服务器更新",
  "make deploy-images", "拉取最新镜像", "health check", "disk cleanup",
  "database migration", "rollback".
---

# Production Deployment

Deploy Numina to the production Docker server via pre-built GHCR images.
The server never builds locally — it pulls images built by GitHub Actions CI on push to `main`.

## Prerequisites

SSH config in `.claude/deploy.env` (gitignored). If missing, ask the user and create it:

```bash
# .claude/deploy.env — DO NOT COMMIT
DEPLOY_SSH_HOST=<server-ip>
DEPLOY_SSH_PORT=<ssh-port>
DEPLOY_SSH_USER=<ssh-user>
DEPLOY_REMOTE_DIR=~/data/numina
```

**Variable sourcing** — shell state does NOT persist between bash calls. Source in every command block:

```bash
set -a && source .claude/deploy.env && set +a
```

Without this, variables expand to empty strings and SSH fails silently.

## Deployment Checklist

Copy and track progress:

```
Deploy Progress:
- [ ] Phase 1: Connect & assess
- [ ] Phase 2: Disk space check (clean if >85% or <2GB free)
- [ ] Phase 3: Verify CI built images (ghcr.io/.../backend:latest exists)
- [ ] Phase 4: Pull latest code (git pull origin main)
- [ ] Phase 5: Deploy images (make deploy-images)
- [ ] Phase 6: Database migration (if new migrations exist)
- [ ] Phase 7: Health check (all 6 services healthy)
```

## Phase 1: Connect & Assess

```bash
cd $DEPLOY_REMOTE_DIR && \
  echo "=== GIT ===" && git log --oneline -3 && \
  echo "=== DISK ===" && df -h / | tail -1 && \
  echo "=== DOCKER ===" && docker system df && \
  echo "=== CONTAINERS ===" && docker compose ps --format 'table {{.Name}}\t{{.Status}}'
```

## Phase 2: Disk Space Check

**Threshold: 85% usage or < 2GB free.** Clean before deploying (cleanup during deploy fails with "No space left on device"):

```bash
docker builder prune -af                    # Build cache first (usually 2-4GB)
docker image prune -af --filter "until=48h" # Unused images if still tight
df -h /                                      # Verify — abort if < 1GB free
```

## Phase 3: Verify CI Built Images

Images are built on push to `main` only. Verify before deploying:

```bash
# Check locally that CI completed — images must exist in GHCR
gh run list --limit 1 --workflow=ci.yml --json conclusion,headBranch
# Should show "SUCCESS" on "main". If not, wait for CI or push to main first.
```

**5 GHCR images** (tagged `:latest` + `:<sha>`):
`backend`, `agent`, `scheduler-worker`, `frontend-main`, `frontend-child`

## Phase 4: Pull Latest Code

```bash
cd $DEPLOY_REMOTE_DIR && git pull origin main
```

If conflicts → stop and report. Never resolve conflicts on the server.

## Phase 5: Deploy Images

```bash
cd $DEPLOY_REMOTE_DIR && make deploy-images
```

This does: `.env` image URL setup → `docker compose pull` (5 services) → `down` → `up -d` → wait for backend health → verify `/api/health`.

**If it fails:**
- **Pull errors** → GHCR auth or network. Check `.env` has correct `*_IMAGE` URLs.
- **Space errors** → return to Phase 2, clean more aggressively.
- **Health timeout** → `docker compose logs --tail 50 backend`

## Phase 6: Database Migration

Only needed when new alembic migrations exist (check `server/apps/backend/alembic/versions/` for new files since last deploy).

**Full guide:** See [db-migration.md](db-migration.md) for the complete decision tree.

**Quick path** — if DB was bootstrapped (tables exist but `alembic_version` empty):

```bash
# Stamp to current head (tables already exist from bootstrap)
docker compose exec -T backend sh -c \
  'cd /app && uv run alembic -c /app/apps/backend/alembic.ini stamp head'
```

If new tables/columns were added after bootstrap, check and create them manually before stamping (see db-migration.md Step 2).

## Phase 7: Health Check

```bash
cd $DEPLOY_REMOTE_DIR && \
  echo "=== CONTAINERS ===" && \
  docker compose ps --format 'table {{.Name}}\t{{.Status}}' && \
  echo "=== API ===" && curl -sf http://localhost/api/health && echo && \
  echo "=== FRONTEND ===" && curl -sf -o /dev/null -w "HTTP %{http_code}" http://localhost/ && echo && \
  echo "=== DISK ===" && df -h / | tail -1
```

**Success criteria:**
- 6 services running: backend, agent, scheduler_worker, frontend-main, frontend-child, nginx
- backend/agent/scheduler_worker/frontend-child show `(healthy)`
- `/api/health` returns `{"status":"ok"}`
- Frontend HTTP 200

## Rollback

Only works for commits pushed to main (CI must have built GHCR images):

```bash
cd $DEPLOY_REMOTE_DIR && \
  git checkout <commit-sha> && \
  make deploy-images
```

Then restore main: `git checkout main`.

## Quick Reference

| Task | Command |
|------|---------|
| Full deploy | Phases 1–7 above |
| Pull images only | Phase 5 only |
| Run migrations | Phase 6 (see [db-migration.md](db-migration.md)) |
| Health check | Phase 7 only |
| View logs | `docker compose logs --tail 100 -f <service>` |
| Restart service | `docker compose restart <service>` |
| Emergency rollback | `git checkout <sha> && make deploy-images` |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No space left on device` | `docker builder prune -af && docker image prune -af` |
| `DuplicateTable`/`DuplicateColumn` | DB bootstrapped → use `stamp head` (see db-migration.md) |
| Container unhealthy | `docker compose logs --tail 50 <service>`. Check `.env`, `DATABASE_URL`, ports |
| GHCR pull fails | Verify `*_IMAGE` in `.env`. Auth: `echo "$TOKEN" \| docker login ghcr.io -u <user> --password-stdin` |
| CI didn't build images | Only builds on push to `main`. Check `gh run list --workflow=ci.yml` |
