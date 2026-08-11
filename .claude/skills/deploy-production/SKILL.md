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

**Docker permissions** — the deploy user may not be in the `docker` group. If you get "permission denied" on docker commands, prepend `sudo`.

**SSH proxy** — if `git` or `ssh` commands fail with "Connection closed by UNKNOWN port 65535", the global `core.sshcommand` may route through a SOCKS proxy that isn't running. Bypass with `GIT_SSH_COMMAND="ssh"` for git operations.

## Compose File

**Always use `docker-compose.production.yml`** for production deployments:

```bash
# Correct — uses production compose
docker compose -f docker-compose.production.yml pull
docker compose -f docker-compose.production.yml up -d

# WRONG — uses default compose (may not have production nginx config)
docker compose pull
docker compose up -d
```

The production compose:
- Pulls GHCR images via `image: ${*_IMAGE:-}` (falls back to build only if image var is empty)
- Uses `.env` (not `.env.production`)
- Mounts `nginx.production.conf` (HTTPS 443 + HTTP 80 + SSL certs)
- Mounts `.numina/data/secrets/` for SSL certificates
- Mounts `.numina/data/uploads/` for user uploads

## SSL Certificates

SSL certs are required for HTTPS (port 443). Place in `.numina/data/secrets/`:

```
.numina/data/secrets/origin.crt   # SSL certificate (PEM)
.numina/data/secrets/origin.key   # Private key (PEM)
```

**Options:**
- **Cloudflare Origin CA** (recommended) — generate from Cloudflare Dashboard → SSL/TLS → Origin Server. Works with "Full (Strict)" SSL mode.
- **Self-signed** — `openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout origin.key -out origin.crt -subj "/CN=your-domain"`. Works with Cloudflare "Full" mode (not "Full (Strict)").

**Cloudflare SSL mode:**
- **Flexible** → connects to origin via HTTP (port 80). Self-signed not needed but origin traffic unencrypted.
- **Full** → connects via HTTPS, accepts self-signed certs. ✅ Recommended with self-signed.
- **Full (Strict)** → connects via HTTPS, requires CA-signed cert. Use Cloudflare Origin CA.

## Deployment Checklist

Copy and track progress:

```
Deploy Progress:
- [ ] Phase 1: Connect & assess
- [ ] Phase 2: Disk space check (clean if >85% or <2GB free)
- [ ] Phase 3: Verify CI built images (ghcr.io/.../backend:latest exists)
- [ ] Phase 4: Pull latest code (git pull origin main)
- [ ] Phase 5: Deploy images (docker compose -f docker-compose.production.yml)
- [ ] Phase 6: Database migration (if new migrations exist)
- [ ] Phase 7: Health check (all 6 services healthy)
```

## Phase 1: Connect & Assess

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'cd ~/data/numina && \
   echo "=== GIT ===" && git log --oneline -3 && \
   echo "=== DISK ===" && df -h / | tail -1 && \
   echo "=== DOCKER ===" && sudo docker system df && \
   echo "=== CONTAINERS ===" && sudo docker compose -f docker-compose.production.yml ps --format "table {{.Name}}\t{{.Status}}" && \
   echo "=== COMPOSE FILE ===" && sudo docker inspect numina-nginx --format "{{index .Config.Labels \"com.docker.compose.project.config_files\"}}" 2>/dev/null'
```

**Important:** Verify the running containers use `docker-compose.production.yml`. If the label shows `docker-compose.yml`, the server is using the wrong compose file — switch with `docker compose down` then `docker compose -f docker-compose.production.yml up -d`.

## Phase 2: Disk Space Check

**Threshold: 85% usage or < 2GB free.** Clean before deploying (cleanup during deploy fails with "No space left on device"):

```bash
sudo docker builder prune -af                    # Build cache first (usually 2-4GB)
sudo docker image prune -af --filter "until=48h" # Unused images if still tight
df -h /                                           # Verify — abort if < 1GB free
```

## Phase 3: Verify CI Built Images

Images are built on push to `main` only. Verify before deploying:

```bash
# Check locally that CI completed — images must exist in GHCR
gh run list --limit 1 --workflow=ci.yml --json conclusion,headBranch
# Should show "SUCCESS" on "main". If not, wait for CI or push to main first.
```

**Waiting for CI:** If CI is still `in_progress`, poll until completed:

```bash
bash -c 'while true; do
  result=$(gh run list --limit 1 --workflow=ci.yml --json conclusion,status,headSha --jq ".[0] | \"\(.headSha[0:7])|\(.status)|\(.conclusion)\"")
  run_status=$(echo "$result" | cut -d"|" -f2)
  echo "[$(date +%H:%M:%S)] status=$run_status"
  [ "$run_status" = "completed" ] && break
  sleep 30
done'
```

**5 GHCR images** (tagged `:latest` + `:<sha>`):
`backend`, `agent`, `scheduler-worker`, `frontend-main`, `frontend-child`

## Phase 4: Pull Latest Code

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'cd ~/data/numina && GIT_SSH_COMMAND="ssh" git pull origin main'
```

If conflicts → stop and report. Never resolve conflicts on the server.

## Phase 5: Deploy Images

**Always use `-f docker-compose.production.yml`:**

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'cd ~/data/numina && \
   echo "=== Pull GHCR images ===" && \
   sudo docker compose -f docker-compose.production.yml pull backend agent scheduler_worker frontend-main frontend-child && \
   echo "=== Recreate services ===" && \
   sudo docker compose -f docker-compose.production.yml up -d && \
   echo "=== Wait for backend healthy ===" && \
   for i in $(seq 1 30); do \
     if sudo docker compose -f docker-compose.production.yml ps backend 2>/dev/null | grep -q "healthy"; then echo "✓ Backend healthy"; break; fi; \
     sleep 2; \
   done && \
   sudo docker compose -f docker-compose.production.yml ps backend 2>/dev/null | grep -q "healthy" || { echo "✗ Backend startup timeout"; exit 1; }'
```

**If it fails:**
- **Pull errors** → GHCR auth or network. Check `.env` has correct `*_IMAGE` URLs.
- **Space errors** → return to Phase 2, clean more aggressively.
- **Health timeout** → `sudo docker compose -f docker-compose.production.yml logs --tail 50 backend`
- **SSL/cert errors** → check `.numina/data/secrets/origin.crt` and `origin.key` exist.
- **Building instead of pulling** → `.env` is missing `*_IMAGE` vars. Add them (see Prerequisites).

## Phase 6: Database Migration

Only needed when new alembic migrations exist (check `server/apps/backend/alembic/versions/` for new files since last deploy):

```bash
# Check for new migrations
git log --oneline <last-deploy-sha>..HEAD -- server/apps/backend/alembic/versions/
```

**Full guide:** See [db-migration.md](db-migration.md) for the complete decision tree.

**Quick path** — if DB was bootstrapped (tables exist but `alembic_version` empty):

```bash
sudo docker compose -f docker-compose.production.yml exec -T backend sh -c \
  'cd /app && uv run alembic -c /app/apps/backend/alembic.ini stamp head'
```

If new tables/columns were added after bootstrap, check and create them manually before stamping (see db-migration.md Step 2).

## Phase 7: Health Check

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'cd ~/data/numina && \
   echo "=== CONTAINERS ===" && \
   sudo docker compose -f docker-compose.production.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" && \
   echo "" && \
   echo "=== HTTPS HEALTH ===" && \
   curl -sk https://localhost/api/health && echo "" && \
   echo "" && \
   echo "=== HTTP HEALTH ===" && \
   curl -sf http://localhost/api/health && echo "" && \
   echo "" && \
   echo "=== FRONTEND ===" && \
   curl -sk -o /dev/null -w "HTTP %{http_code}" https://localhost/ && echo "" && \
   echo "" && \
   echo "=== DISK ===" && \
   df -h / | tail -1'
```

**Success criteria:**
- 6 services running: backend, agent, scheduler_worker, frontend-main, frontend-child, nginx
- backend/agent/scheduler_worker/frontend-child show `(healthy)`
- nginx shows ports `0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp`
- `/api/health` returns `{"status":"ok"}` on both HTTP and HTTPS
- Frontend HTTPS 200
- Test from external: `curl -sI https://numina.xiaoshutiao.space/` should return HTTP 200 (not 526)

## Rollback

Only works for commits pushed to main (CI must have built GHCR images):

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'cd ~/data/numina && \
   GIT_SSH_COMMAND="ssh" git checkout <commit-sha> && \
   sudo docker compose -f docker-compose.production.yml pull && \
   sudo docker compose -f docker-compose.production.yml up -d'
```

Then restore main: `GIT_SSH_COMMAND="ssh" git checkout main`.

## Quick Reference

| Task | Command |
|------|---------|
| Full deploy | Phases 1–7 above |
| Pull images only | Phase 5 only |
| Run migrations | Phase 6 (see [db-migration.md](db-migration.md)) |
| Health check | Phase 7 only |
| View logs | `sudo docker compose -f docker-compose.production.yml logs --tail 100 -f <service>` |
| Restart service | `sudo docker compose -f docker-compose.production.yml restart <service>` |
| Emergency rollback | `git checkout <sha>` + Phase 5 |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No space left on device` | `sudo docker builder prune -af && sudo docker image prune -af` |
| `DuplicateTable`/`DuplicateColumn` | DB bootstrapped → use `stamp head` (see db-migration.md) |
| Container unhealthy | `sudo docker compose -f docker-compose.production.yml logs --tail 50 <service>` |
| GHCR pull fails | Verify `*_IMAGE` in `.env`. Auth: `echo "$TOKEN" \| docker login ghcr.io -u <user> --password-stdin` |
| CI didn't build images | Only builds on push to `main`. Check `gh run list --workflow=ci.yml` |
| Cloudflare 526 (Invalid SSL) | SSL mode is "Full (Strict)" but cert is self-signed → change to "Full" in Cloudflare dashboard, or use Cloudflare Origin CA cert |
| Wrong compose file running | Check: `sudo docker inspect numina-nginx --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}'` — if not `docker-compose.production.yml`, do `docker compose down` then `docker compose -f docker-compose.production.yml up -d` |
| SSH connection refused / proxy error | Bypass proxy: `GIT_SSH_COMMAND="ssh" git pull` |
| Services building instead of pulling | `.env` missing `*_IMAGE` vars — add `BACKEND_IMAGE=ghcr.io/vincentruan/numina/backend:latest` etc. |
