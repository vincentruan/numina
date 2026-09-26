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

## Deploy Mode Selection

每次部署时按以下决策树选择模式。**不要假设 Mode A 一定可用** — 先验证再执行。

```
用户触发部署
  │
  ├─ 用户明确指定模式 → 直接用指定模式
  │
  └─ 未指定 → 尝试 Mode A (GHCR)
       │
       ├─ Step 1: 检查 CI 状态
       │    └─ gh run list → 最近一次 push to main 的 build-images job
       │         ├─ conclusion = success → 继续 Step 2
       │         ├─ conclusion = failure → 降级 Mode C（通知用户）
       │         └─ status = in_progress → 等待完成（最多 15 分钟），超时 → 降级 Mode C
       │
       ├─ Step 2: 同步配置文件（如有变更）
       │
       ├─ Step 3: 检查磁盘空间
       │
       ├─ Step 4: 拉取镜像
       │    └─ docker compose pull
       │         ├─ 全部成功 → 继续 Step 5
       │         └─ 任一失败（401/404/timeout/空镜像）→ 降级 Mode C（通知用户）
       │
       └─ Step 5-7: 迁移 + 重建 + 健康检查 → Done
```

### 降级到 Mode C 的触发条件

以下任一条件满足时，**自动降级到 Mode C**（无需等用户确认，但必须通知）：

| 条件 | 检测方式 | 说明 |
|------|---------|------|
| CI build-images 失败 | `gh run list` 显示 `failure` | LFS 问题、编译错误、GHCR 推送失败 |
| CI 未完成且等待超时 | 轮询 15 分钟仍未 `completed` | GitHub Actions 队列拥堵 |
| GHCR pull 失败 | `docker compose pull` 返回非 0 | 网络问题、GHCR 限流、镜像不存在 |
| 拉到的镜像为空/损坏 | `docker inspect` 无 `Architecture` 字段 | 极少见，通常是推送中断 |
| 用户明确说"CI 额度不够" / "本地编译" | 用户输入 | 直接走 Mode C |

### 降级执行流程

```
1. 通知用户: "GHCR 不可用（原因），降级到本地编译部署"
2. 进入 Mode C: Local Build & Deploy
3. 执行 make deploy-local (= build-local + package-images + deploy-remote)
4. 继续 Mode C Step 4 (migration) + Step 5 (health check)
```

## Prerequisites

SSH config in `.claude/skills/deploy-production/deploy.env` (gitignored). If missing, ask the user and create it:

```bash
# .claude/skills/deploy-production/deploy.env — DO NOT COMMIT
DEPLOY_SSH_HOST=<server-ip>
DEPLOY_SSH_PORT=<ssh-port>
DEPLOY_SSH_USER=<ssh-user>
DEPLOY_REMOTE_DIR=<absolute-path>   # 必须用绝对路径，不能用 ~
```

> **⚠️ `DEPLOY_REMOTE_DIR` 必须是绝对路径**（如 `/home/geek/data/numina`），不能用 `~`。
> Makefile 中 rsync 在本地 shell 展开变量，`~` 会被解析为本地 home 目录。

**Variable sourcing** — shell state does NOT persist between bash calls. Source in every command block:

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
```

**SSH quoting** — `$DEPLOY_REMOTE_DIR` 是**本地变量**，不在远程服务器上。SSH 命令必须用**双引号**包裹，让本地 shell 先展开变量：

```bash
# ✅ Correct — double quotes: local shell expands ${DEPLOY_REMOTE_DIR}
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ${DEPLOY_REMOTE_DIR} &&
  sudo docker compose -f docker-compose.production.yml ps
"

# ❌ Wrong — single quotes: $DEPLOY_REMOTE_DIR sent literally, remote has no such variable
ssh ... '
  cd $DEPLOY_REMOTE_DIR &&
  ...
'
```

> **例外：** `docker compose run ... bash -c '...'` 内部的单引号是正确的 — 那是在远程容器内执行，路径已硬编码（如 `/app`）。

**Docker permissions** — prepend `sudo` if the deploy user is not in the `docker` group.

### Database Architecture — Local Docker PostgreSQL + Supabase Backup

Production uses a **local Docker PostgreSQL** container (`numina-postgres-prod`) as the primary database, with **Supabase configured as a logical replication standby** for backup.

| Component | Container | Compose file | Purpose |
|-----------|-----------|-------------|---------|
| **Primary DB** | `numina-postgres-prod` | `docker-compose.production-pg.yml` | Application data, `wal_level=logical` for Supabase CDC |
| **Standby** | (remote Supabase) | — | Backup via logical replication (CDC) |

**Two databases** on the same PostgreSQL instance:

| Database | Env var | Used by | Purpose |
|----------|---------|---------|---------|
| `numina_prod` | `DATABASE_URL` | backend, agent, scheduler_worker | Application data (users, assets, families, alembic-managed) |
| `numina_prod_deerflow` | `DEERFLOW_DB_URL` | agent only | DeerFlow checkpoint data (checkpoints, blobs, writes) |

**Why separate:** Both use `alembic_version` table. Sharing one DB causes DeerFlow's `bootstrap.py` to read Numina's alembic revision and fail with `Can't locate revision identified by '...'`.

**Key facts:**
- `numina-postgres-prod` runs as a **separate container** from the app compose stack — it is NOT defined in `docker-compose.production.yml`
- App services connect via `172.17.0.1:5432` (Docker host bridge IP) — set in `.env` as `DATABASE_URL` / `DEERFLOW_DB_URL`
- `wal_level=logical` + replication slots configured for Supabase CDC backup
- Data stored at `/home/geek/data/numina-prod-db/data` (bind mount)
- `DEERFLOW_DB_URL` must use **direct connection port 5432** — pooler transaction mode doesn't support the prepared statements DeerFlow needs
- DeerFlow self-initializes its schema on agent startup via `init_engine()` — **no manual migration step needed** for the DeerFlow DB
- If the `numina_prod_deerflow` database doesn't exist yet, create it via: `CREATE DATABASE numina_prod_deerflow;`

> **⚠️ `--remove-orphans` 危险**：`numina-postgres-prod` 不在 `docker-compose.production.yml` 中。使用 `docker compose up -d --remove-orphans` 会**删除 PG 容器**。永远不要对 app compose 使用 `--remove-orphans`；PG 容器由 `docker-compose.production-pg.yml` 独立管理。

### Single-Instance Architecture (No Redis)

生产环境以**单实例模式**运行，不依赖 Redis：

| 组件 | 模式 | 环境变量 | 说明 |
|------|------|----------|------|
| StreamBridge (事件缓冲) | `memory` | `STREAM_BRIDGE_TYPE=memory` | 进程内 asyncio.Condition，agent↔backend 通过 HTTP SSE 通信 |
| Cache (限流/验证码) | `memory` | `CACHE_BACKEND=memory` | 进程内 dict，单实例足够 |

- **Agent** 始终使用 in-memory bridge（硬编码），无需配置
- **Scheduler worker** 不使用 Redis 或 StreamBridge
- `docker-compose.production.yml` 中**不包含 Redis 服务**
- **仅当扩展到多实例**（多个 backend 进程）时，才需要启用 Redis：设 `STREAM_BRIDGE_TYPE=redis` + `CACHE_BACKEND=redis` + 添加 Redis 容器

### Supabase Logical Replication (DDL Alignment)

Supabase standby 通过逻辑复制订阅主库变更。**PostgreSQL 逻辑复制不复制 DDL** — 只复制 DML（INSERT/UPDATE/DELETE）。

**DDL 对齐规则：** 任何 alembic migration（`upgrade head`）运行后，必须在 Supabase 端同步执行等效 DDL。**如果 Supabase 备库 DDL 未对齐，不发布新镜像。**

原因：备库 schema 落后 → 复制的 DML 可能引用不存在的列/表 → 复制中断 → 数据丢失风险。

**当前限制：** Supabase 域名只有 AAAA (IPv6) 记录，无 IPv4。Docker IPv6 已配置（`daemon.json` + compose `networks.default.enable_ipv6`）。如果 subscriptions 连接失败，参见 [references/ipv6-disk-recovery.md](references/ipv6-disk-recovery.md) §Enabling Docker IPv6。

**DDL 同步方法：** 容器内无法解析 Supabase IPv6 域名，必须在服务器主机用 Python (`pip3 install psycopg[binary]`) 直连执行 DDL。完整流程见 [references/supabase-ddl-sync.md](references/supabase-ddl-sync.md)。

**检查 DDL 一致性：**
```bash
# 查看本地表数量
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"

# 查看 subscription 状态
sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c \
  "SELECT subname, subenabled FROM pg_subscription;"
```

## Production Config vs Local

生产服务器的 `.env` 与本地开发有显著差异。**不要将本地 `.env` 同步到服务器** — 服务器 `.env` 是手动维护的。

### 必要配置项（生产 vs 本地）

| 配置项 | 本地开发 | 生产服务器 | 验证方式 |
|--------|----------|------------|----------|
| `ENVIRONMENT` | `development` (默认) | **`production`** | 启动日志 |
| `CAPTCHA_ENABLED` | `false` (默认) | **`true`** | `curl -sk /api/v1/captcha/config` → `captcha_enabled: true` |
| `DATABASE_URL` | SQLite 或 localhost PG | `postgresql://...@172.17.0.1:5432/numina_prod` | backend 日志 |
| `DEERFLOW_DB_URL` | SQLite 或 localhost PG | `postgresql://...@172.17.0.1:5432/numina_prod_deerflow` | agent 日志 |
| SSL/TLS | 无 | Origin CA cert (`origin.crt` + `origin.key`) | `curl -sk https://localhost/` |
| `*_IMAGE` | 无 (compose 默认) | `ghcr.io/...` (Mode A) 或 `numina/...` (Mode C) | `docker inspect` |
| `CORS_ORIGINS` | `localhost` | 实际域名 JSON 数组 | 浏览器 CORS 头 |

### 连接池配置（per-service 独立）

Compose 通过独立变量映射到代码读取的 `DB_POOL_SIZE`，每个服务互不干扰：

| 服务 | Compose 变量 | 默认值 | max_overflow |
|------|-------------|--------|-------------|
| backend | `${BACKEND_DB_POOL_SIZE:-20}` | 20 | `${BACKEND_DB_MAX_OVERFLOW:-5}` |
| agent | `${AGENT_DB_POOL_SIZE:-10}` | 10 | `${AGENT_DB_MAX_OVERFLOW:-5}` |
| scheduler_worker | `${SCHEDULER_DB_POOL_SIZE:-5}` | 5 | `${SCHEDULER_DB_MAX_OVERFLOW:-2}` |

单实例默认值总计最大连接：(20+5) + (10+5) + (5+2) = **47**，远低于 `max_connections=200`。如需调整，在服务器 `.env` 中设置：
```bash
BACKEND_DB_POOL_SIZE=25
AGENT_DB_POOL_SIZE=15
```

### 限流配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LOGIN_RATE_LIMIT_MAX_ATTEMPTS` | 5 | 登录失败最大次数 |
| `LOGIN_RATE_LIMIT_LOCKOUT_SECONDS` | 900 | 锁定时长（15 分钟） |
| `GLOBAL_RATE_LIMIT_PER_MINUTE` | 600 | 全局限流（每 IP 每分钟） |
| `REGISTER_RATE_LIMIT_PER_HOUR` | 5 | 注册限流（每 IP 每小时） |

默认值对家庭应用足够。如果频繁误触发，在 `.env` 中覆盖。

### 缓存与事件（单实例）

| 配置项 | 生产值 | 说明 |
|--------|--------|------|
| `STREAM_BRIDGE_TYPE` | `memory` | 单实例进程内事件缓冲，已在 compose 中硬编码 |
| `CACHE_BACKEND` | `memory` | 单实例进程内缓存（限流/验证码），已在 compose 中硬编码 |

> 这些变量已在 `docker-compose.production.yml` 中固定为 `memory`，无需在 `.env` 中设置。

### Health Check 验证清单

每次部署后验证以下项目（详见 Step 7 完整流程）：
```bash
# 1. 容器状态
sudo docker ps --format "table {{.Names}}\t{{.Status}}" | grep numina
# 期望: 7 (app) + 1 (postgres-prod) = 8 个容器，backend/agent/scheduler (healthy)

# 2. 各服务健康
curl -sk https://localhost/api/health              # → {"status":"ok"}
# Agent + Scheduler 通过 docker exec 检查（见 Step 7a）

# 3. 验证码
curl -sk https://localhost/api/v1/captcha/config   # → captcha_enabled: true

# 4. 前端
curl -sk -o /dev/null -w "%{http_code}" https://localhost/        # → 200
curl -sk -o /dev/null -w "%{http_code}" https://localhost/child/  # → 200

# 5. 启动日志（缓存预热 + bootstrap 完成确认）
sudo docker compose -f docker-compose.production.yml logs --tail 100 backend | \
  grep -E '初始化|bootstrap|reconcile|汇率|MCP|ERROR' | tail -10

# 6. Nginx 已 reload（upstream DNS 刷新）
sudo docker exec numina-nginx nginx -s reload
```

## Server Directory Layout

The production server's deploy directory needs only these files (not a full git clone for Mode A):

```
~/data/numina/
├── .env                              # Secrets + *_IMAGE vars + DATABASE_URL + DEERFLOW_DB_URL (manual, not in git)
├── docker-compose.production.yml     # App services only (synced from repo)
├── docker-compose.production-pg.yml     # Production PostgreSQL (synced from repo)
├── nginx.production.conf             # Nginx config (synced from repo)
├── system-config.yaml                # AI model metadata (synced from repo)
├── scripts/
│   └── init-prod-databases.sql       # DB init script (synced from repo)
└── .numina/data/
    ├── uploads/                      # User uploads (persistent)
    └── secrets/
        ├── origin.crt                # SSL cert
        └── origin.key                # SSL key

~/data/numina-prod-db/
└── data/                             # PostgreSQL data (bind mount, persistent)
```

---

## Mode A: GHCR Deploy (Default)

No git on the server. CI builds images on push to `main`; server just pulls them.

### Step 0: Ensure Production PostgreSQL is Running

The production database (`numina-postgres-prod`) runs as a **separate container** from the app stack. It must be healthy before deploying app services.

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  if sudo docker ps --format '{{.Names}}' | grep -q 'numina-postgres-prod'; then
    echo '✓ numina-postgres-prod is running'
  else
    echo '=== Starting production postgres ===' &&
    cd ${DEPLOY_REMOTE_DIR} &&
    sudo docker compose -f docker-compose.production-pg.yml up -d &&
    for i in \$(seq 1 30); do
      if sudo docker compose -f docker-compose.production-pg.yml ps 2>/dev/null | grep -q 'healthy'; then
        echo '✓ numina-postgres-prod healthy'; break
      fi
      [ \"\$i\" = \"30\" ] && echo '✗ Postgres startup timeout' && exit 1
      sleep 10
    done
  fi
"
```

> **First-time setup:** If `numina-postgres-prod` has never been started, ensure `docker-compose.production-pg.yml` and `scripts/init-prod-databases.sql` are synced to the server first (Step 1b). The init script creates `numina_prod` and `numina_prod_deerflow` databases on first boot.

### Step 1: Verify CI Completed (Build-Images)

```bash
# 检查最近一次 push to main 的 CI run 状态
gh run list --limit 1 --workflow=ci.yml --json conclusion,status,headBranch --jq '.[0] | "\(.headBranch) \(.status) \(.conclusion)"'
```

Must show `main completed success`. If `in_progress`, poll:

```bash
bash -c 'for i in $(seq 1 30); do
  result=$(gh run list --limit 1 --workflow=ci.yml --json conclusion,status --jq ".[0] | \"\(.status)|\(.conclusion)\"")
  status=$(echo $result | cut -d"|" -f1)
  conclusion=$(echo $result | cut -d"|" -f2)
  [ "$status" = "completed" ] && [ "$conclusion" = "success" ] && echo "✓ CI success" && exit 0
  [ "$status" = "completed" ] && [ "$conclusion" != "success" ] && echo "✗ CI failed ($conclusion) → 降级 Mode C" && exit 1
  echo "[$(date +%H:%M:%S)] waiting for CI... ($status)"; sleep 30
done
echo "✗ CI 等待超时 (15min) → 降级 Mode C" && exit 1'
```

> **降级判断：** 如果上述命令 exit 1（CI failure 或超时），**立即降级到 Mode C**（见上方"降级执行流程"）。不要继续 Mode A 后续步骤。

### Step 2: Sync Config Files

Push config changes from local repo to server (skip if no config file changes since last deploy):

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
rsync -avz --progress -e "ssh -p ${DEPLOY_SSH_PORT:-22}" \
  docker-compose.production.yml \
  docker-compose.production-pg.yml \
  nginx.production.conf \
  system-config.yaml \
  ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST}:${DEPLOY_REMOTE_DIR}/ && \
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  "mkdir -p ${DEPLOY_REMOTE_DIR}/scripts" && \
rsync -avz --progress -e "ssh -p ${DEPLOY_SSH_PORT:-22}" \
  scripts/init-prod-databases.sql \
  ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST}:${DEPLOY_REMOTE_DIR}/scripts/
```

**What to sync:** App compose + production-pg compose + nginx/system config + DB init script. Never sync `.env` (secrets) or source code.

**When to skip:** If the only changes are Python/Vue code (no config file changes), skip this step and go directly to Step 3.

### Step 3: Check Disk Space

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
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

> **降级判断：** 如果 pull 失败（401/404/timeout/镜像不存在），**立即降级到 Mode C**。通知用户原因后执行 `make deploy-local`。

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ${DEPLOY_REMOTE_DIR} &&
  echo '=== Pull GHCR images ===' &&
  sudo docker compose -f docker-compose.production.yml pull backend agent scheduler_worker frontend-main frontend-child || {
    echo '✗ GHCR pull 失败 → 降级 Mode C'
    exit 2
  }
"
```

Then check migration state using the newly pulled image:

```bash
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ${DEPLOY_REMOTE_DIR} &&
  echo '=== Check migration state ===' &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c '
    cd /app && uv run alembic -c apps/backend/alembic.ini current && echo \"---\" && uv run alembic -c apps/backend/alembic.ini heads
  '
"
```

### Step 5: Database Migration

If current ≠ head → run upgrade:

> **Note:** This only applies to the **Numina database** (`DATABASE_URL`). The **DeerFlow checkpoint database** (`DEERFLOW_DB_URL`) is self-managing — DeerFlow's `init_engine()` creates/updates its own schema on agent startup. No manual migration step needed for DeerFlow.

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ${DEPLOY_REMOTE_DIR} &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c '
    cd /app && uv run alembic -c apps/backend/alembic.ini upgrade head 2>&1
  '
"
```

If it fails with DuplicateColumn/DuplicateTable → follow [references/db-migration.md](references/db-migration.md) §Handle Failures. **Never blindly `stamp head`** — it skips ALL pending migrations.

### Step 5b: DDL Alignment Gate (主库 + 备库)

> **⚠️ 发布门禁：** 如果 Step 5 执行了 migration（current ≠ head），**必须**在发布新镜像前确认 Supabase 备库 DDL 已对齐。PostgreSQL 逻辑复制不复制 DDL — 备库 schema 落后会导致复制中断和数据不一致。

**检查流程：**
1. 确认主库 migration 完成（`alembic current` = `alembic heads`）
2. 确认**两个** subscription 状态正常（`numina_sub` + `deerflow_sub`）
3. 确认复制延迟在可接受范围（`last_msg_send_time` 不超过 5 分钟）
4. 如果 Supabase 连接不可达（如 IPv6 问题），**暂停发布**，手动在 Supabase 端执行等效 DDL

```bash
# 检查 subscription 状态 + 复制延迟
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c '
    SELECT s.subname, s.subenabled,
           stat.last_msg_send_time,
           EXTRACT(EPOCH FROM (now() - stat.last_msg_send_time))::int AS lag_seconds
    FROM pg_subscription s
    LEFT JOIN pg_stat_subscription stat ON stat.subname = s.subname;
  '
"
```

**判定标准：**

| 状态 | 判定 | 操作 |
|------|------|------|
| `subenabled=t` + `lag_seconds < 300` | ✅ 正常 | 继续部署 |
| `subenabled=t` + `lag_seconds ≥ 300` | ⚠️ 延迟过大 | 检查 Supabase 端负载/连接，等待追赶 |
| `subenabled=f` | ❌ 已禁用 | 在 Supabase 端手动执行 DDL，恢复 subscription |
| `last_msg_send_time` 为 NULL | ❌ 从未连接 | 检查 IPv6 连通性 + subscription 配置 |
| subscription 已废弃 | — | 如果不再需要 Supabase 备份，可跳过此步骤 |

**表数量对比（可选但推荐）：**

如果执行了 migration，快速对比主库和备库表数量确认一致：

```bash
# 主库表数量
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -t -c \
    \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';\"
"

# Supabase 表数量（需主机 Python — 容器无法解析 IPv6）
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "python3 -c '
import psycopg
conn = psycopg.connect(host=\"db.vywwletyvrzyoozhsfqu.supabase.co\", port=5432,
    user=\"postgres\", password=\"<SUPABASE_PASSWORD>\",
    dbname=\"postgres\", sslmode=\"require\")
print(conn.execute(\"SELECT count(*) FROM pg_tables WHERE schemaname=\\\"public\\\"\").fetchone()[0])
conn.close()
'"
# 差异 ≤ 1 为正常（_cdc_test 是 Supabase 内部表，不计入）
```

**如何对齐 Supabase DDL：** 在 Supabase Dashboard → SQL Editor 中执行与 alembic migration 等效的 DDL 语句。每个 migration 文件的 `upgrade()` 函数内容即为需要执行的 SQL。完整流程见 [references/supabase-ddl-sync.md](references/supabase-ddl-sync.md)。

### Step 6: Recreate Services

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ${DEPLOY_REMOTE_DIR} &&
  echo '=== Recreate services ===' &&
  sudo docker compose -f docker-compose.production.yml up -d &&
  echo '=== Reload nginx (refresh upstream DNS) ===' &&
  sudo docker exec numina-nginx nginx -s reload 2>/dev/null &&
  echo '=== Wait for backend healthy ===' &&
  for i in \$(seq 1 30); do
    if sudo docker compose -f docker-compose.production.yml ps backend 2>/dev/null | grep -q 'healthy'; then
      echo '✓ Backend healthy'; break
    fi
    sleep 2
  done &&
  sudo docker compose -f docker-compose.production.yml ps backend 2>/dev/null | grep -q 'healthy' || { echo '✗ Backend startup timeout'; exit 1; }
"
```

> **⚠️ 不要加 `--remove-orphans`！** 该参数会删除 `numina-postgres-prod`（它不在 app compose 中但属于同一 project）。PG 容器由 `docker-compose.production-pg.yml` 独立管理。

> **⚠️ 必须 reload nginx！** `docker compose up -d` 会重建 backend/agent/scheduler_worker 容器，容器 IP 可能变化。Nginx 缓存了 upstream DNS 解析结果，不 reload 会导致 502 Bad Gateway（直到缓存过期）。这是已知陷阱，参见 `docs/solutions/integration-issues/nginx-stale-dns-upstream-cache.md`。使用 `nginx -s reload` 而非 `docker compose restart nginx`，因为前者是 graceful reload 无停机。

### Step 7: Health Check + Smoke Test

每次部署后**按顺序**验证以下 4 个层级。任一层级失败需立即排查，不要跳到下一层。

#### 7a. 容器状态 + 各服务独立健康

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  echo "=== CONTAINERS ===" &&
  sudo docker ps --format "table {{.Names}}\t{{.Status}}" | grep numina &&
  echo "" &&
  echo "=== BACKEND HEALTH ===" &&
  curl -sk https://localhost/api/health && echo "" &&
  echo "" &&
  echo "=== AGENT HEALTH ===" &&
  curl -sk https://localhost/api/health-agent 2>/dev/null || \
    sudo docker exec numina-agent python -c "import urllib.request,json; print(json.loads(urllib.request.urlopen(\"http://localhost:8001/health\").read()))" &&
  echo "" &&
  echo "=== SCHEDULER HEALTH ===" &&
  sudo docker exec numina-scheduler-worker python -c "import urllib.request,json; r=json.loads(urllib.request.urlopen(\"http://localhost:8002/health\").read()); print(f\"status={r[\"status\"]} jobs={r[\"job_count\"]}\")" &&
  echo "" &&
  echo "=== CAPTCHA ===" &&
  curl -sk https://localhost/api/v1/captcha/config && echo "" &&
  echo "" &&
  echo "=== FRONTEND ===" &&
  curl -sk -o /dev/null -w "main: HTTP %{http_code}\n" https://localhost/ &&
  curl -sk -o /dev/null -w "child: HTTP %{http_code}\n" https://localhost/child/
'
```

**Success criteria:**

| 检查项 | 期望值 | 失败时排查 |
|--------|--------|-----------|
| 容器数 | 7 (app) + 1 (postgres-prod) = 8 | `docker ps` 查看哪些未启动 |
| Backend `(healthy)` | Docker status 显示 `(healthy)` | `docker compose logs --tail 50 backend` |
| Agent `(healthy)` | Docker status 显示 `(healthy)` | `docker compose logs --tail 50 agent` |
| `/api/health` | `{"status":"ok"}` | 检查 DB 连接、bootstrap 错误 |
| Agent `/health` | `{"status":"ok","service":"numina-agent"}` | 检查 DeerFlow init、DB 连接 |
| Scheduler `/health` | `status=ok jobs=7` | 检查 scheduler 日志 |
| `captcha_enabled` | `true` | 检查 `.env` 中 `CAPTCHA_ENABLED=true` |
| Frontend main | HTTP 200 | 检查 nginx 日志 |
| Frontend child | HTTP 200 | 检查 nginx 日志 |

#### 7b. 启动日志验证（缓存预热 + Bootstrap）

容器重启后内存缓存为空。后端 lifespan 会自动执行以下初始化，需确认日志中无错误：

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  echo '=== Backend startup init ===' &&
  sudo docker compose -f docker-compose.production.yml logs --tail 100 backend 2>/dev/null | grep -E '初始化|bootstrap|reconcile|汇率|MCP|orphan|event.persistence|schema|迁移|启动|ERROR|WARNING' | tail -20 &&
  echo '' &&
  echo '=== Agent startup init ===' &&
  sudo docker compose -f docker-compose.production.yml logs --tail 50 agent 2>/dev/null | grep -E 'init|startup|DeerFlow|checkpointer|MCP|cache|ERROR|WARNING' | tail -10
"
```

**需要确认的关键初始化项：**

| 初始化项 | 日志关键词 | 说明 |
|----------|-----------|------|
| DB schema 对齐 | `数据库结构已完整` 或 `新增表/字段/索引` | `run_schema_migration()` 自动检查 |
| Bootstrap 数据 | `系统初始化数据检查完成` | categories, currencies, agents, skills, invitation codes |
| Reconcile 状态 | 无 `系统状态协调失败` 错误 | `DesiredStateRunner` 验证期望状态 |
| 汇率数据 | `首次启动，立即获取汇率数据` 或无此日志 | 仅在 DB 无汇率时触发；后续由 scheduler_worker 定期刷新 |
| MCP registry | `MCP tool registry validated` | 工具注册表完整性验证 |
| Orphan detector | `Orphan task detector started` | 后台孤儿任务检测循环 |
| Event persistence | 无 `Event persistence init failed` | DeerFlow 事件持久化（非致命，失败则降级） |

**如果看到 `系统状态协调失败`：** reconcile 检测到关键资源未就绪，服务会拒绝启动。查看日志中的 `report.summary_text()` 获取具体缺失项。

#### 7c. 功能冒烟测试（可选但推荐）

在关键版本升级后，建议执行快速冒烟测试验证核心流程：

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  echo "=== 1. HTTPS + CORS ===" &&
  curl -sk -o /dev/null -w "HTTPS: %{http_code}\n" https://localhost/api/health &&
  curl -sk -o /dev/null -w "CORS preflight: %{http_code}\n" -X OPTIONS \
    -H "Origin: https://numina.xiaoshutiao.space" \
    -H "Access-Control-Request-Method: GET" \
    https://localhost/api/health &&
  echo "" &&
  echo "=== 2. Captcha challenge ===" &&
  curl -sk https://localhost/api/v1/captcha/config | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"captcha_enabled: {d.get(\"captcha_enabled\")}\")" &&
  echo "" &&
  echo "=== 3. Login endpoint reachable ===" &&
  curl -sk -o /dev/null -w "POST /auth/login: HTTP %{http_code}\n" \
    -X POST https://localhost/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"_probe_\",\"password\":\"_probe_\"}" &&
  echo "(401=reachable, 429=rate-limited, 502=broken)" &&
  echo "" &&
  echo "=== 4. Scheduler jobs ===" &&
  sudo docker exec numina-scheduler-worker python -c "
import urllib.request, json
r = json.loads(urllib.request.urlopen(\"http://localhost:8002/health\").read())
print(f\"scheduler: {r[\"status\"]}, jobs: {r[\"job_count\"]}\")
for j in r.get(\"jobs\", []):
    print(f\"  {j[\"id\"]}: next={j[\"next_run\"]}\")
"
'
```

**冒烟测试判定：**

| 测试 | 期望 | 含义 |
|------|------|------|
| HTTPS health | 200 | SSL + nginx + backend 通路正常 |
| CORS preflight | 200/204 | CORS 配置正确，前端可跨域请求 |
| Captcha config | `captcha_enabled: true` | 生产安全配置生效 |
| Login endpoint | 401 (非 502/500) | Auth 路由可达，DB 连接正常 |
| Scheduler jobs | `jobs: 7`，所有 job 有 next_run | 定时任务已注册 |

---

## Mode B: Source Build

Use when you need custom changes not yet merged to main, or CI hasn't built images.

### Step 1: Pull Latest Code on Server

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} \
  'cd ~/data/numina && GIT_SSH_COMMAND="ssh" git fetch origin && GIT_SSH_COMMAND="ssh" git checkout main && GIT_SSH_COMMAND="ssh" git pull origin main'
```

If conflicts → **stop and report**. Never resolve conflicts on the server.

### Step 2: Database Migration

Same check as Mode A Step 4 — run migration on the server before rebuilding:

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ~/data/numina &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c '
    cd /app && uv run alembic -c apps/backend/alembic.ini current && echo \"---\" && uv run alembic -c apps/backend/alembic.ini heads
  ' &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c '
    cd /app && uv run alembic -c apps/backend/alembic.ini upgrade head 2>&1
  '
"
```

If upgrade fails → follow [references/db-migration.md](references/db-migration.md) §Handle Failures.

> **DDL 对齐：** 如果执行了 migration，参见 Mode A Step 5b — 确认 Supabase 备库 DDL 已对齐（含复制延迟检查）后再发布。

### Step 3: Build & Deploy

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} '
  cd ~/data/numina &&
  echo "=== Build images ===" &&
  sudo docker compose -f docker-compose.production.yml build &&
  echo "=== Recreate services ===" &&
  sudo docker compose -f docker-compose.production.yml up -d &&
  echo "=== Reload nginx (refresh upstream DNS) ===" &&
  sudo docker exec numina-nginx nginx -s reload 2>/dev/null &&
  echo "=== Wait for backend ===" &&
  sleep 15 &&
  sudo docker compose -f docker-compose.production.yml ps --format "table {{.Name}}\t{{.Status}}"
'
```

### Step 4: Health Check + Smoke Test

Same as Mode A Step 7 (7a 容器状态 + 7b 启动日志 + 7c 功能冒烟测试).

---

## Mode C: Local Build & Deploy

Use when CI quota is exhausted, GHCR 不可用, 或 the production server lacks resources to compile.
Build images on the local machine, transfer, and deploy. Verification happens on the
production server (health check after recreate) — local only builds, does NOT verify
(production has domain-specific config: SSL certs, Supabase PG, short URL, etc.).

### 快速部署（推荐）

当 GHCR 降级或明确需要本地编译时，一键完成：

```bash
# 完整流程: build → package → transfer → load → recreate → health check
make deploy-local
```

> `deploy-local` 不执行 migration。如果有新 migration，完成后继续 Step 4。

### LFS Icon 验证（首次 Mode C 或怀疑 icon 缺失时）

本地 build 也需要 LFS 文件才能正确生成 icon 缩略图。确认本地 LFS 已拉取：

```bash
# 检查 icon 文件是否是真实 PNG（而非 LFS pointer）
file frontend/packages/assets/src/icons/3d-things/animals/$(ls frontend/packages/assets/src/icons/3d-things/animals/ | head -1)
# 应输出: PNG image data, ...
# 如果输出: ASCII text → LFS 未拉取，先执行: git lfs pull
```

如果 icon 缺失或为 pointer 文件：
```bash
git lfs pull --include="frontend/packages/assets/src/icons/3d-things/**"
```

### Prerequisites

- Docker with BuildKit enabled on the local machine
- `.claude/skills/deploy-production/deploy.env` configured (same as Mode A)
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

# Local Docker PostgreSQL (numina-postgres-prod via host bridge):
DATABASE_URL=postgresql://numina:numinapass@172.17.0.1:5432/numina_prod
DEERFLOW_DB_URL=postgresql://numina:numinapass@172.17.0.1:5432/numina_prod_deerflow
```

> **⚠️ `DEERFLOW_DB_URL` must use direct connection port (5432), NOT the pooler port (6543).** Pooler transaction mode doesn't support the prepared statements DeerFlow needs.

**Switching back to Mode A:** restore the `ghcr.io/...` image values (or remove the `*_IMAGE` lines to use defaults). Database URLs stay the same regardless of deploy mode.

### Step 3: Deploy to Remote

```bash
make deploy-remote
```

This single target handles:
1. **Sync config files** — rsync compose/nginx/system-config to server
2. **Transfer images** — rsync `dist/images.tar.gz` to server
3. **Remote load** — `docker load -i images.tar.gz` on server
4. **Recreate services** — `docker compose up -d` with existing `.env`
5. **Restart nginx** — refresh upstream DNS cache (避免 502)
6. **Health check** — wait for backend `(healthy)`

> **Note:** `deploy-remote` loads images and recreates in one shot. Backend may crash-loop if new columns are missing — Step 4 fixes this.

### Step 4: Database Migration + Restart

Always run after `deploy-remote`. The new image is already loaded:

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ${DEPLOY_REMOTE_DIR} &&
  echo '=== Check migration state ===' &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c '
    cd /app && uv run alembic -c apps/backend/alembic.ini current && echo \"---\" && uv run alembic -c apps/backend/alembic.ini heads
  '
"
```

If current ≠ head → run upgrade:

```bash
ssh -p ${DEPLOY_SSH_PORT:-22} ${DEPLOY_SSH_USER}@${DEPLOY_SSH_HOST} "
  cd ${DEPLOY_REMOTE_DIR} &&
  sudo docker compose -f docker-compose.production.yml run --rm --no-deps backend bash -c '
    cd /app && uv run alembic -c apps/backend/alembic.ini upgrade head 2>&1
  ' &&
  echo '=== Restart backend ===' &&
  sudo docker compose -f docker-compose.production.yml restart backend
"
```

If upgrade fails → follow [references/db-migration.md](references/db-migration.md) §Handle Failures.

> **DDL 对齐：** 如果执行了 migration，参见 Mode A Step 5b — 确认 Supabase 备库 DDL 已对齐（含复制延迟检查）后再发布。

### Step 5: Health Check + Smoke Test

Same as Mode A Step 7 (7a 容器状态 + 7b 启动日志 + 7c 功能冒烟测试).

### Step 6: Verify Frontend Content (Post-Deploy)

After recreating containers, verify the frontend actually contains the new code:

```bash
set -a && source .claude/skills/deploy-production/deploy.env && set +a
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

The Makefile re-tags compose-generated images as `numina/<service>:latest`. The compose project name produces images with **hyphens** (e.g. `numina-backend`, `numina-agent`, `numina-scheduler_worker`), but the Makefile looks for **underscores** after the project prefix (e.g. `numina_backend`) — so `scheduler_worker` succeeds but `backend`/`agent`/`frontend-main`/`frontend-child` fail.

**Detection:** `make build-local` prints `✗ 标记失败: numina_backend` even though all 5 images built successfully.

**Fix:** Re-tag manually from the actual compose-generated names:
```bash
docker tag numina-backend:latest numina/backend:latest
docker tag numina-agent:latest numina/agent:latest
docker tag numina-scheduler_worker:latest numina/scheduler-worker:latest
docker tag numina-frontend-main:latest numina/frontend-main:latest
docker tag numina-frontend-child:latest numina/frontend-child:latest
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
set -a && source .claude/skills/deploy-production/deploy.env && set +a
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
| Full deploy | Steps 1-7 | Steps 1-4 | `make deploy-local` + Steps 4-5 |
| Config change only | Step 2 + Step 7 | Step 1 + Step 3 | Sync config + `make deploy-remote` |
| Code change only | Steps 4-7 | Steps 2-3 | `make deploy-local` + Steps 4-5 |
| DB migration only | Steps 4-5b | Step 2 | Step 4 |
| DDL alignment check | Step 5b | Step 2 (+ 5b gate) | Step 4 (+ 5b gate) |
| Build images | (CI does this) | (server does this) | `make build-local` |
| Health check + smoke | Step 7 (7a+7b+7c) | Step 4 | (automatic in `deploy-remote`) |
| Startup log verify | Step 7b | Step 4 (+ 7b) | Step 5 (+ 7b) |
| View logs | `sudo docker compose -f docker-compose.production.yml logs --tail 100 -f <service>` |
| Restart service | `sudo docker compose -f docker-compose.production.yml restart <service>` |
| Restart nginx (DNS) | `sudo docker exec numina-nginx nginx -s reload` |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No space left on device` | `sudo docker builder prune -af && sudo docker image prune -af` |
| `DuplicateTable`/`DuplicateColumn` | Object already exists → stamp that revision, then `upgrade head` for remaining. **Never `stamp head` blindly** — it skips pending migrations with genuinely new DDL. See [references/db-migration.md](references/db-migration.md) §Handle Failures |
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
| Agent unhealthy / DeerFlow init failed | Check `DEERFLOW_DB_URL` in `.env` — must point to `numina_prod_deerflow` database on port 5432 (not pooler 6543). Check agent logs: `sudo docker compose -f docker-compose.production.yml logs --tail 50 agent` |
| `Can't locate revision identified by '...'` | DeerFlow reading Numina's `alembic_version` — `DEERFLOW_DB_URL` and `DATABASE_URL` point to the same database. Fix: ensure `DEERFLOW_DB_URL` targets the separate `numina_prod_deerflow` database |
| DeerFlow checkpoint data lost after deploy | Check `DEERFLOW_DB_URL` hasn't reverted to SQLite default — verify `.env` has the PostgreSQL URL. SQLite path: `.numina/data/db/deerflow-checkpoints.db` |
| `numina-postgres-prod` not running | Start with: `ssh ... "cd ${DEPLOY_REMOTE_DIR} && sudo docker compose -f docker-compose.production-pg.yml up -d"`. Data is in bind mount `/home/geek/data/numina-prod-db/data` — survives container restart. Check logs: `sudo docker compose -f docker-compose.production-pg.yml logs --tail 30` |
| Backend can't reach postgres | `DATABASE_URL` in `.env` must use `172.17.0.1:5432` (Docker host bridge). Verify: `sudo docker exec numina-postgres-prod psql -U numina -d numina_prod -c "SELECT 1"`. If using compose defaults (no `.env` override), host is `postgres` which requires a postgres service in the compose stack — **not** the production-pg architecture |
| `docker-compose.production-pg.yml` uses named volume but server uses bind mount | The local `docker-compose.production-pg.yml` uses `${PROD_PG_DATA_DIR:-/home/geek/data/numina-prod-db/data}` bind mount. If the server has a different data path, set `PROD_PG_DATA_DIR` on the server or override in a `.env` for the production-pg compose |
| SSH: `cd: $DEPLOY_REMOTE_DIR: No such file or directory` | 单引号内 `$DEPLOY_REMOTE_DIR` 不会在远程展开（它是本地变量）。SSH 命令必须用双引号包裹，让本地 shell 先展开变量。见上方 "SSH quoting" 说明 |
| `--remove-orphans` 误删 PG 容器 | 永远不要对 `docker-compose.production.yml` 使用 `--remove-orphans`，它会删除 `numina-postgres-prod`。恢复：`sudo docker compose -f docker-compose.production-pg.yml up -d` |
| PG PANIC: `No space left on device` | 磁盘满导致 PG crash loop + 复制槽损坏。完整恢复流程见 [references/ipv6-disk-recovery.md](references/ipv6-disk-recovery.md) §Disk-Full Crash Recovery。快速修复：`sudo docker image prune -af`，PG 自动恢复 |
| PG replication `Network unreachable` | Supabase 只有 IPv6，需 Docker IPv6。完整配置流程见 [references/ipv6-disk-recovery.md](references/ipv6-disk-recovery.md) §Enabling Docker IPv6。临时：`ALTER SUBSCRIPTION xxx DISABLE;` |
| PG `can no longer get changes from replication slot` | 复制槽损坏（通常因磁盘满 crash）。修复流程见 [references/ipv6-disk-recovery.md](references/ipv6-disk-recovery.md) §Replication Slot Corruption |
| PG `the database system is not yet accepting connections` | PG 处于 recovery 模式，通常因磁盘满 crash 后重启。先清理磁盘空间，PG 自动恢复。如持续报错，检查 `pg_logical/replorigin_checkpoint.tmp` 写入权限 |
| `captcha_enabled: false` in health check | 见上方 "Production Config vs Local" §Health Check 验证清单。确认 `.env` 含 `CAPTCHA_ENABLED=true`，然后 `restart backend` |
| 部署后 502 Bad Gateway | Nginx upstream DNS 缓存了旧容器 IP。修复：`sudo docker exec numina-nginx nginx -s reload`。根因：容器重建后 IP 变化，nginx 不自动刷新 DNS。参见 `docs/solutions/integration-issues/nginx-stale-dns-upstream-cache.md` |
| 部署后 `/api/health` 返回 `{"status":"ok"}` 但功能异常 | 检查启动日志：`docker compose logs --tail 100 backend`。可能原因：(1) reconcile 失败但服务降级运行；(2) 汇率数据为空（首次启动外部 API 超时）；(3) MCP registry 验证失败。详见 Step 7b |
| Scheduler `jobs=0` | Scheduler 未注册任务。检查 scheduler_worker 日志，确认 `setup_all_jobs()` 执行成功。重启：`sudo docker compose -f docker-compose.production.yml restart scheduler_worker` |
| GHCR pull 失败 / CI build-images failure | 自动降级 Mode C：`make deploy-local`。常见原因：LFS 未拉取（CI 无 `lfs: true`）、GHCR 限流、GitHub Actions 额度耗尽 |
| 前端 icon 缩略图 404 / 空白 | 镜像内 icon 文件缺失。验证：`docker exec numina-frontend-main ls /usr/share/nginx/html/icons/3d-thumbs/`。根因：CI checkout 未拉取 LFS → sharp 生成缩略图失败。修复：确认 ci.yml `build-images` job 有 `lfs: true` |
| Supabase 备库 `relation "xxx" does not exist` | DDL 未同步到备库。逻辑复制不复制 DDL，需手动执行。完整流程见 [references/supabase-ddl-sync.md](references/supabase-ddl-sync.md) |
| 容器内 `failed to resolve host ...supabase.co` | Supabase 只有 IPv6 AAAA 记录，Docker 容器无法解析。必须在主机用 Python 直连：`pip3 install psycopg[binary]`，然后 `python3 script.py`。详见 [references/supabase-ddl-sync.md](references/supabase-ddl-sync.md) §Network Constraint |
