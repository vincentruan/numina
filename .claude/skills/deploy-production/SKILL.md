---
name: deploy-production
description: >
  Use when deploying Numina to the production Linux Docker server.
  Three modes: (A) GHCR images — pull pre-built images, no git needed;
  (B) Source build — git pull + docker compose build on server;
  (C) Local build — build images locally, transfer, deploy remote.
  Triggers: "部署到生产", "deploy to production", "上线", "发布",
  "deploy prod", "服务器更新", "拉取最新镜像", "health check",
  "disk cleanup", "database migration", "rollback",
  "本地编译", "build local", "本地镜像", "CI 额度".
---

# Production Deployment

Deploy Numina to the production Docker server. Three modes:

| Mode | When | Git needed on server? | Build location |
|------|------|----------------------|----------------|
| **A: GHCR (default)** | CI built images on push to main | No | GitHub Actions |
| **B: Source build** | Custom changes not yet on main | Yes | Server |
| **C: Local build** | CI quota exhausted / server can't compile | No | Local machine |

## Prerequisites

SSH config in `.claude/deploy.env` (gitignored). If missing, ask the user and create it:

```bash
# .claude/deploy.env — DO NOT COMMIT
DEPLOY_SSH_HOST=<server-ip>
DEPLOY_SSH_PORT=<ssh-port>
DEPLOY_SSH_USER=<ssh-user>
DEPLOY_REMOTE_DIR=<absolute-path>   # 必须用绝对路径，不能用 ~
```

> **⚠️ `DEPLOY_REMOTE_DIR` 必须是绝对路径**（如 `/home/geek/data/numina`），不能用 `~`。
> Makefile 中 rsync 在本地 shell 展开变量，`~` 会被解析为本地 home 目录。

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

### Step 4: Pull Images & Check Migration

Pull new images first — migration must run with the new image that contains updated alembic files.

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd $DEPLOY_REMOTE_DIR &&
  echo "=== Pull GHCR images ===" &&
  sudo docker compose -f docker-compose.production.yml pull backend agent scheduler_worker frontend-main frontend-child
'
```

Then check migration state using the newly pulled image:

```bash
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd $DEPLOY_REMOTE_DIR &&
  echo "=== Check migration state ===" &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic -c apps/backend/alembic.ini current && echo \"---\" && uv run alembic -c apps/backend/alembic.ini heads
  "
'
```

### Step 5: Database Migration

If current ≠ head → run upgrade:

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd $DEPLOY_REMOTE_DIR &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic -c apps/backend/alembic.ini upgrade head 2>&1
  "
'
```

If it fails with DuplicateColumn/DuplicateTable → follow [db-migration.md](db-migration.md) §Handle Failures. **Never blindly `stamp head`** — it skips ALL pending migrations.

### Step 6: Recreate Services

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd $DEPLOY_REMOTE_DIR &&
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

### Step 7: Health Check

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

### Step 2: Database Migration

Same check as Mode A Step 4 — run migration on the server before rebuilding:

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd ~/data/numina &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic -c apps/backend/alembic.ini current && echo \"---\" && uv run alembic -c apps/backend/alembic.ini heads
  " &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic -c apps/backend/alembic.ini upgrade head 2>&1
  "
'
```

If upgrade fails → follow [db-migration.md](db-migration.md) §Handle Failures.

### Step 3: Build & Deploy

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

### Step 4: Health Check

Same as Mode A Step 6.

---

## Mode C: Local Build & Deploy

Use when CI quota is exhausted or the production server lacks resources to compile.
Build images on the local machine, transfer, and deploy. Verification happens on the
production server (health check after recreate) — local only builds, does NOT verify
(production has domain-specific config: SSL certs, Supabase PG, short URL, etc.).

### Prerequisites

- Docker with BuildKit enabled on the local machine
- `.claude/deploy.env` configured (same as Mode A)
- Production server architecture must match `DOCKER_PLATFORM` (default: `linux/amd64`)
  - Mac Apple Silicon → cross-compile: `DOCKER_PLATFORM=linux/amd64` (default)
  - Mac ARM server: `DOCKER_PLATFORM=linux/arm64`

### Configurable Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCAL_IMAGE_PREFIX` | `numina` | Image repository prefix |
| `LOCAL_IMAGE_TAG` | `latest` | Image tag |
| `DOCKER_PLATFORM` | `linux/amd64` | Target platform (empty = host arch) |

### Step 1: Build Images Locally

```bash
# Default: cross-compile for linux/amd64 (most production servers)
make build-local

# Same architecture as host (e.g. ARM server)
make build-local DOCKER_PLATFORM=linux/arm64

# Host architecture (no cross-compile)
make build-local DOCKER_PLATFORM=

# Custom tag
make build-local LOCAL_IMAGE_TAG=v2026.08.15
```

This uses `docker compose -f docker-compose.production.yml build` for all 5 services,
then re-tags them as `numina/<service>:latest`.

**Images produced:**

```
numina/backend:latest
numina/agent:latest
numina/scheduler-worker:latest
numina/frontend-main:latest
numina/frontend_child:latest
```

### Step 2: Package Images

```bash
make package-images
# Output: dist/images.tar.gz
```

Exports all 5 images into a compressed tarball for transfer.

### One-Command Pipeline

```bash
# Full: build → package → deploy (验证在生产服务器自动完成)
make deploy-local
```

> **Note:** `deploy-local` runs Steps 1-3 automatically but does NOT run database migration. If new migrations exist, run Step 4 manually after.

### Production Server `.env` Setup

When switching from Mode A (GHCR) to Mode C for the first time, update the server's `.env`:

```bash
# Replace GHCR image references with local tags:
BACKEND_IMAGE=numina/backend:latest
AGENT_IMAGE=numina/agent:latest
SCHEDULER_WORKER_IMAGE=numina/scheduler-worker:latest
FRONTEND_MAIN_IMAGE=numina/frontend-main:latest
FRONTEND_CHILD_IMAGE=numina/frontend-child:latest
```

**Switching back to Mode A:** restore the `ghcr.io/...` values (or remove the `*_IMAGE` lines to use defaults).

### Step 3: Deploy to Remote

```bash
make deploy-remote
```

This single target handles:
1. **Sync config files** — rsync compose/nginx/system-config to server
2. **Transfer images** — rsync `dist/images.tar.gz` to server
3. **Remote load** — `docker load -i images.tar.gz` on server
4. **Recreate services** — `docker compose up -d` with existing `.env`
5. **Health check** — wait for backend `(healthy)`

> **Note:** `deploy-remote` loads images and recreates in one shot. Backend may crash-loop if new columns are missing — Step 4 fixes this.

### Step 4: Database Migration + Restart

Always run after `deploy-remote`. The new image is already loaded:

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd $DEPLOY_REMOTE_DIR &&
  echo "=== Check migration state ===" &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic -c apps/backend/alembic.ini current && echo \"---\" && uv run alembic -c apps/backend/alembic.ini heads
  "
'
```

If current ≠ head → run upgrade:

```bash
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd $DEPLOY_REMOTE_DIR &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c "
    cd /app && uv run alembic -c apps/backend/alembic.ini upgrade head 2>&1
  " &&
  echo "=== Restart backend ===" &&
  sudo docker compose -f docker-compose.production.yml restart backend
'
```

If upgrade fails → follow [db-migration.md](db-migration.md) §Handle Failures.

### Step 5: Health Check

Same as Mode A Step 6.

### Step 6: Verify Frontend Content (Post-Deploy)

After recreating containers, verify the frontend actually contains the new code:

```bash
set -a && source .claude/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  echo "=== Search for feature-specific strings in JS bundles ===" &&
  sudo docker exec numina-frontend-main sh -c "grep -rl \"<unique-string-from-your-change>\" /usr/share/nginx/html/assets/*.js 2>/dev/null | head -3"
'
```

If grep returns empty → **the container is running stale code**. Rebuild with `--no-cache` (see Gotchas below).

### ⚠️ Mode C Gotchas (Mac → amd64 server)

These are pitfalls discovered from real deployments. Read before every Mode C deploy.

#### 1. `make build-local` uses Docker cache — frontend may not rebuild

`docker compose build` caches layers. If only `.vue`/`.ts` files changed but `package.json`/`pnpm-lock.yaml` didn't, the frontend build layer is served from cache — **new code is NOT in the image**.

**Detection:** Container "Up" time stays the same after `docker compose up -d`, or grep for new feature strings returns empty.

**Fix:** Force rebuild frontend only:
```bash
export DOCKER_DEFAULT_PLATFORM=linux/amd64
DOCKER_BUILDKIT=1 docker compose -f docker-compose.production.yml build --no-cache frontend-main frontend-child
```

Then re-tag and re-deploy:
```bash
docker tag ghcr.io/vincentruan/numina/frontend-main:latest numina/frontend-main:latest
docker tag ghcr.io/vincentruan/numina/frontend-child:latest numina/frontend-child:latest
docker save numina/frontend-main:latest numina/frontend-child:latest | gzip > dist/frontend-amd64.tar.gz
# rsync + docker load + docker compose up -d (same as deploy-remote steps)
```

#### 2. `DOCKER_DEFAULT_PLATFORM` is mandatory on Apple Silicon

`make build-local` sets `DOCKER_PLATFORM=linux/amd64` via Makefile env. But if you manually run `docker compose build` (e.g. to add `--no-cache`), the env var is **NOT inherited** — you get arm64 images that silently fail on amd64 servers.

**Symptom:** Container restarts with `exec format error` or stays in restart loop. Check with:
```bash
docker inspect numina/frontend-main:latest --format '{{.Architecture}}'
# Must say "amd64", NOT "arm64"
```

**Rule:** Every manual `docker compose build` on Mac MUST prefix with:
```bash
export DOCKER_DEFAULT_PLATFORM=linux/amd64
```

#### 3. `make build-local` re-tag fallback may fail

The Makefile re-tags compose-generated images (e.g. `numina_backend`) as `numina/backend:latest`. If the compose project name differs from the directory name, the fallback `numina_backend` image won't exist. The build succeeded — images are at `ghcr.io/vincentruan/numina/<service>:latest`. Just re-tag manually:
```bash
for svc in backend agent scheduler-worker frontend-main frontend-child; do
  docker tag ghcr.io/vincentruan/numina/$svc:latest numina/$svc:latest
done
```

#### 4. Alembic path inside backend container

The backend container has `alembic.ini` at `/app/apps/backend/alembic.ini` with `script_location = apps/backend/alembic` (relative). Run alembic from `/app` with explicit config:
```bash
sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c '
  cd /app && uv run alembic -c apps/backend/alembic.ini current &&
  uv run alembic -c apps/backend/alembic.ini heads
'
```

Running from `/app/apps/backend` fails because the relative `script_location` resolves to a non-existent nested path.

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

### Mode C Rollback (local build)

Re-build from the previous commit and re-deploy:

```bash
git checkout <previous-commit>
make deploy-local
git checkout -  # return to previous branch
```

If the previous image tarball is still available in `dist/images.tar.gz`, skip the build:

```bash
make deploy-remote  # uses existing dist/images.tar.gz
```

---

## Quick Reference

| Task | Mode A (GHCR) | Mode B (Source) | Mode C (Local Build) |
|------|---------------|-----------------|----------------------|
| Full deploy | Steps 1-7 | Steps 1-4 | `make deploy-local` + Step 4 |
| Config change only | Step 2 + Step 6 | Step 1 + Step 3 | Sync config + `make deploy-remote` |
| Code change only | Steps 4-6 | Steps 2-3 | `make deploy-local` + Step 4 |
| DB migration only | Steps 4-5 | Step 2 | Step 4 |
| Build images | (CI does this) | (server does this) | `make build-local` |
| Health check | Step 7 | Step 4 | (automatic in `deploy-remote`) |
| View logs | `sudo docker compose -f docker-compose.production.yml logs --tail 100 -f <service>` |
| Restart service | `sudo docker compose -f docker-compose.production.yml restart <service>` |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No space left on device` | `sudo docker builder prune -af && sudo docker image prune -af` |
| `DuplicateTable`/`DuplicateColumn` | Object already exists → stamp that revision, then `upgrade head` for remaining. **Never `stamp head` blindly** — it skips pending migrations with genuinely new DDL. See [db-migration.md](db-migration.md) §Handle Failures |
| Container unhealthy | `sudo docker compose -f docker-compose.production.yml logs --tail 50 <service>` |
| GHCR pull fails | Verify `*_IMAGE` in `.env`. Auth: `echo "$TOKEN" \| docker login ghcr.io -u <user> --password-stdin` |
| CI didn't build images | Only builds on push to `main`. Check `gh run list --workflow=ci.yml` |
| Cloudflare 526 (Invalid SSL) | SSL mode "Full (Strict)" + self-signed cert → change to "Full" in Cloudflare, or use Origin CA cert |
| `docker tag` fails (image not found) | Run `docker images` to find the actual compose-generated name (e.g. `numina_backend`). Update fallback in `build-local` if project dir name differs |
| Cross-compile slow on Mac | First build downloads base images + installs deps. Subsequent builds use BuildKit cache. `DOCKER_BUILDKIT=1` is auto-set |
| `docker load` fails on server | Check disk space: `df -h`. Prune old images: `sudo docker image prune -af --filter "until=48h"` |
| Services building instead of pulling (Mode C) | Server `.env` missing `*_IMAGE` vars — set them to `numina/<service>:latest` |
| Services building instead of pulling | `.env` missing `*_IMAGE` vars — add `BACKEND_IMAGE=ghcr.io/vincentruan/numina/backend:latest` etc. |
| Double CSP headers (browser console) | Outer nginx must NOT add CSP — inner nginx (frontend container) handles it with nonce injection |
| Frontend unchanged after Mode C deploy | Docker cache served stale layers. Rebuild with `--no-cache` + `DOCKER_DEFAULT_PLATFORM=linux/amd64`. Verify by grepping feature strings in container JS bundles |
| Container restarts / `exec format error` | Architecture mismatch: arm64 image on amd64 server. Rebuild with `export DOCKER_DEFAULT_PLATFORM=linux/amd64`. Verify: `docker inspect --format '{{.Architecture}}' numina/<svc>:latest` |
| `alembic current` fails with "No 'script_location' key" | Wrong working directory. Must run from `/app` with `-c apps/backend/alembic.ini`, not from `/app/apps/backend` |
