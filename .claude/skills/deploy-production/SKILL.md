---
name: deploy-production
description: >
  Use when deploying Numina to the production Linux Docker server.
  Two modes: (A) GHCR images — pull pre-built images, no git needed;
  (B) Source build — git pull + docker compose build.
  Triggers: "部署到生产", "deploy to production", "上线", "发布",
  "deploy prod", "服务器更新", "拉取最新镜像", "health check",
  "disk cleanup", "database migration", "rollback".
---

# Production Deployment

Deploy Numina to the production Docker server. Two modes:

| Mode | When | Git needed on server? |
|------|------|----------------------|
| **A: GHCR (default)** | CI built images on push to main | No |
| **B: Source build** | Custom changes not yet on main | Yes |

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

**Docker permissions** — prepend `sudo` if the deploy user is not in the `docker` group.

## Server Directory Layout

The production server's deploy directory needs only these files (not a full git clone for Mode A):

```
~/data/numina/
├── .env                              # Secrets + *_IMAGE vars (manual, not in git)
├── docker-compose.production.yml     # Compose config (synced from repo)
├── nginx.production.conf             # Nginx config (synced from repo)
├── system-config.yaml                # AI model metadata (synced from repo)
└── .numina/data/
    ├── uploads/                      # User uploads (persistent)
    └── secrets/
        ├── origin.crt                # SSL cert
        └── origin.key                # SSL key
```

---

## Mode A: GHCR Deploy (Default)

No git on the server. CI builds images on push to `main`; server just pulls them.

### Step 1: Verify CI Completed

```bash
gh run list --limit 1 --workflow=ci.yml --json conclusion,status,headBranch --jq '.[0] | "\(.headBranch) \(.status) \(.conclusion)"'
```

Must show `main completed success`. If `in_progress`, poll:

```bash
bash -c 'while true; do
  result=$(gh run list --limit 1 --workflow=ci.yml --json conclusion,status --jq ".[0] | \"\(.status)|\(.conclusion)\"")
  [ "$(echo $result | cut -d"|" -f1)" = "completed" ] && echo "✓ CI done" && break
  echo "[$(date +%H:%M:%S)] waiting for CI..."; sleep 30
done'
```

### Step 2: Sync Config Files

Push config changes from local repo to server (skip if no config file changes since last deploy):

```bash
set -a && source .claude/deploy.env && set +a
rsync -avz --progress -e "ssh -p ${DEPLOY_SSH_PORT:-22}" \
  docker-compose.production.yml \
  nginx.production.conf \
  system-config.yaml \
  ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST}:${DEPLOY_REMOTE_DIR}/
```

**What to sync:** Only config files that compose/nginx/system need. Never sync `.env` (secrets) or source code.

**When to skip:** If the only changes are Python/Vue code (no config file changes), skip this step and go directly to Step 3.

### Step 3: Check Disk Space

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'df -h / | tail -1 && echo "---" && sudo docker system df'
```

**Threshold: 85% usage or < 2GB free.** Clean before deploying:

```bash
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'sudo docker builder prune -af && sudo docker image prune -af --filter "until=48h"'
```

### Step 4: Pull Images & Recreate

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd $DEPLOY_REMOTE_DIR &&
  echo "=== Pull GHCR images ===" &&
  sudo docker compose -f docker-compose.production.yml pull backend agent scheduler_worker frontend-main frontend-child &&
  echo "=== Recreate services ===" &&
  sudo docker compose -f docker-compose.production.yml up -d &&
  echo "=== Wait for backend healthy ===" &&
  for i in $(seq 1 30); do
    if sudo docker compose -f docker-compose.production.yml ps backend 2>/dev/null | grep -q "healthy"; then
      echo "✓ Backend healthy"; break
    fi
    sleep 2
  done &&
  sudo docker compose -f docker-compose.production.yml ps backend 2>/dev/null | grep -q "healthy" || { echo "✗ Backend startup timeout"; exit 1; }
'
```

### Step 5: Database Migration (if needed)

Check for new migrations since last deploy:

```bash
git log --oneline <last-deploy-sha>..HEAD -- server/apps/backend/alembic/versions/
```

If new migrations exist → follow [db-migration.md](db-migration.md).

### Step 6: Health Check

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  echo "=== CONTAINERS ===" &&
  sudo docker compose -f docker-compose.production.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" &&
  echo "" &&
  echo "=== HTTPS HEALTH ===" &&
  curl -sk https://localhost/api/health && echo "" &&
  echo "" &&
  echo "=== FRONTEND ===" &&
  curl -sk -o /dev/null -w "HTTP %{http_code}" https://localhost/ && echo ""
'
```

**Success:** 6 services running, backend `(healthy)`, `/api/health` returns `{"status":"ok"}`.

---

## Mode B: Source Build

Use when you need custom changes not yet merged to main, or CI hasn't built images.

### Step 1: Pull Latest Code on Server

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'cd ~/data/numina && GIT_SSH_COMMAND="ssh" git fetch origin && GIT_SSH_COMMAND="ssh" git checkout main && GIT_SSH_COMMAND="ssh" git pull origin main'
```

If conflicts → **stop and report**. Never resolve conflicts on the server.

### Step 2: Build & Deploy

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd ~/data/numina &&
  echo "=== Build images ===" &&
  sudo docker compose -f docker-compose.production.yml build &&
  echo "=== Recreate services ===" &&
  sudo docker compose -f docker-compose.production.yml up -d &&
  echo "=== Wait for backend ===" &&
  sleep 15 &&
  sudo docker compose -f docker-compose.production.yml ps --format "table {{.Name}}\t{{.Status}}"
'
```

### Step 3: Health Check

Same as Mode A Step 6.

---

## Rollback

### Mode A Rollback (GHCR — pin to specific SHA)

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd ~/data/numina &&
  # Temporarily pin images to previous SHA in .env
  # e.g. BACKEND_IMAGE=ghcr.io/vincentruan/numina/backend:<old-sha>
  sudo docker compose -f docker-compose.production.yml pull &&
  sudo docker compose -f docker-compose.production.yml up -d
'
```

Then restore `.env` image tags to `:latest` after verifying.

### Mode B Rollback (source)

```bash
ssh ... 'cd ~/data/numina && git checkout <commit-sha> && sudo docker compose -f docker-compose.production.yml build && sudo docker compose -f docker-compose.production.yml up -d'
```

Then restore: `git checkout main`.

---

## Quick Reference

| Task | Mode A (GHCR) | Mode B (Source) |
|------|---------------|-----------------|
| Full deploy | Steps 1-6 | Steps 1-3 |
| Config change only | Step 2 + Step 4 | Step 1 + Step 2 |
| Code change only | Step 4 (skip Step 2) | Steps 1-2 |
| Health check | Step 6 | Step 3 |
| View logs | `sudo docker compose -f docker-compose.production.yml logs --tail 100 -f <service>` |
| Restart service | `sudo docker compose -f docker-compose.production.yml restart <service>` |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No space left on device` | `sudo docker builder prune -af && sudo docker image prune -af` |
| `DuplicateTable`/`DuplicateColumn` | DB bootstrapped → use `stamp head` (see [db-migration.md](db-migration.md)) |
| Container unhealthy | `sudo docker compose -f docker-compose.production.yml logs --tail 50 <service>` |
| GHCR pull fails | Verify `*_IMAGE` in `.env`. Auth: `echo "$TOKEN" \| docker login ghcr.io -u <user> --password-stdin` |
| CI didn't build images | Only builds on push to `main`. Check `gh run list --workflow=ci.yml` |
| Cloudflare 526 (Invalid SSL) | SSL mode "Full (Strict)" + self-signed cert → change to "Full" in Cloudflare, or use Origin CA cert |
| Services building instead of pulling | `.env` missing `*_IMAGE` vars — add `BACKEND_IMAGE=ghcr.io/vincentruan/numina/backend:latest` etc. |
| Double CSP headers (browser console) | Outer nginx must NOT add CSP — inner nginx (frontend container) handles it with nonce injection |
