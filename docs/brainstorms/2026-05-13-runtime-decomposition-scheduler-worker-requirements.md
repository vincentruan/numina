---
date: 2026-05-13
topic: runtime-decomposition-scheduler-worker
focus: Extract scheduler + worker to standalone process; backend becomes API-only; shared domain packages
mode: repo-grounded
---

# Requirements: Runtime Decomposition — Scheduler/Worker Extraction (Phase 1)

## Problem

Backend mixes API serving and scheduled job execution in one process. When the backend restarts (deploy, crash, config change), all 7 active APScheduler jobs are interrupted mid-execution. Scheduler and API share the same lifecycle, making independent deployment impossible.

Agent has a dormant scheduler (`agent/app/scheduler.py`) with zero active jobs — Phase 1+ AI jobs are planned but blocked on this architectural separation.

## Goal

Extract scheduler + worker into a standalone `scheduler_worker` process. Backend becomes a pure API server. Shared business logic moves to `server/packages/` so both backend and scheduler_worker import from the same source.

This is Phase 1 of a broader runtime decomposition. Phase 2 (full apps+packages structure, agent_api decomposition) is deferred until Phase 1 is validated in production.

## Target Architecture

```
server/
  apps/
    backend_api/        ← existing backend, API endpoints only (no scheduler)
    agent_api/          ← existing agent, unchanged (dormant scheduler untouched)
    scheduler_worker/   ← new: combined scheduler + worker in one process
  packages/
    core/               ← config, logging
    db/                 ← SessionLocal, Base, models
    domain/             ← business services called by jobs
    security/           ← auth utilities (revoke_jti)
    storage/            ← storage backends, factory, crypto
```

## Scheduler/Worker Design

Scheduler and worker share one process. APScheduler triggers job functions directly (no HTTP, no queue). If the process restarts, in-flight jobs are interrupted; the next scheduled cycle re-runs them. No persistence or retry infrastructure is required for Phase 1.

The `scheduler_worker` app is a minimal FastAPI app with:
- A `/health` endpoint (for Docker healthcheck)
- APScheduler lifecycle in `lifespan` (start on startup, shutdown on shutdown)
- Job functions that import from `server/packages/domain/`

## Jobs to Migrate

All 7 jobs currently in `backend/app/scheduler.py`:

| Job ID | Schedule | Service dependency |
|--------|----------|--------------------|
| `exchange_rate` | Cron: 08:00–22:00 every 2h, 15 min jitter | `packages/domain/exchange_rate` |
| `file_sync` | Interval: every 5 min | `packages/storage` |
| `audit_log_purge` | Cron: daily | `packages/domain/audit` |
| `revoked_token_cleanup` | Interval: every hour | `packages/security` |
| `device_session_cleanup` | Interval: every hour | `packages/domain/device` |
| `reminder_daily` | Cron: daily | `packages/domain/notification` |
| `snapshot_daily` | Cron: daily | `packages/domain/snapshot` |

## Domain Packages to Extract

Services that jobs call must move to `server/packages/` before scheduler_worker can import them cleanly. Backend also updates its imports to use packages.

| Package | Contents | Source |
|---------|----------|--------|
| `packages/core/` | `settings` (config), `get_logger` (logging) | `backend/app/config.py`, `backend/app/core/logging_config.py` |
| `packages/db/` | `SessionLocal`, `Base`, models (`CachedFile`, `FileRemoteLocation`, `StorageBackend`) | `backend/app/database.py`, `backend/app/models/` |
| `packages/storage/` | `StorageError`, `decrypt_config`, `get_backend_for_type`, backend implementations | `backend/app/services/storage/` |
| `packages/security/` | `cleanup_expired_revoked_tokens` | `backend/app/auth/revoke_jti.py` |
| `packages/domain/exchange_rate/` | `ExchangeRateService` | `backend/app/services/exchange_rate.py` |
| `packages/domain/audit/` | `purge_old_audit_logs` | `backend/app/services/audit_log.py` |
| `packages/domain/device/` | `cleanup_expired_device_sessions`, `delete_old_revoked_sessions` | `backend/app/services/device.py` |
| `packages/domain/notification/` | `run_scheduled_checks` | `backend/app/services/notification/dispatcher.py` |
| `packages/domain/snapshot/` | `auto_generate_daily_snapshots` | `backend/app/services/snapshot.py` |

## Migration Sequence (Strangler Fig)

Each step is independently deployable. Backend tests must pass after every step before proceeding.

### Step 0: Create skeleton
- Create `server/apps/backend_api/`, `server/apps/scheduler_worker/`, `server/packages/` directory structure
- Add `__init__.py` and stub `README.md` per package
- No code moved yet

### Step 1: Extract `packages/core/`
- Move `settings` and `get_logger` to `packages/core/`
- Update all `from app.config import settings` and `from app.core.logging_config import get_logger` in backend
- Verify: `uv run pytest tests/ -v`, `uv run ruff check .`, `uv run mypy app/`

### Step 2: Extract `packages/db/`
- Move `SessionLocal`, `Base`, and the 3 models scheduler uses to `packages/db/`
- Update backend imports
- Verify: backend starts, Alembic can still generate migrations, tests pass

### Step 3: Extract `packages/storage/`
- Move `services/storage/` to `packages/storage/`
- Update backend imports
- Verify: file upload/download endpoints work, file_sync job logic still importable

### Step 4: Extract `packages/security/`
- Move `auth/revoke_jti.py` to `packages/security/`
- Update backend imports
- Verify: auth endpoints work, token revocation tests pass

### Step 5: Extract `packages/domain/exchange_rate/`
- Move `ExchangeRateService` to `packages/domain/exchange_rate/`
- Update backend imports
- Verify: exchange rate endpoints work, tests pass

### Step 6: Extract `packages/domain/audit/`
- Move `purge_old_audit_logs` to `packages/domain/audit/`
- Update backend imports
- Verify: audit log endpoints work, tests pass

### Step 7: Extract `packages/domain/device/`
- Move device session cleanup functions to `packages/domain/device/`
- Update backend imports
- Verify: device session endpoints work, tests pass

### Step 8: Extract `packages/domain/notification/`
- Move `run_scheduled_checks` to `packages/domain/notification/`
- Update backend imports
- Verify: notification endpoints work, tests pass

### Step 9: Extract `packages/domain/snapshot/`
- Move `auto_generate_daily_snapshots` to `packages/domain/snapshot/`
- Update backend imports
- Verify: snapshot endpoints work, tests pass

### Step 10: Create `scheduler_worker` app
- Create `server/apps/scheduler_worker/main.py` with FastAPI app + APScheduler lifespan
- Move job functions from `backend/app/scheduler.py` to `scheduler_worker/jobs/`
- Job functions import from `server/packages/domain/`, `server/packages/storage/`, etc.
- Add `/health` endpoint
- Verify: `scheduler_worker` starts independently, all 7 jobs register

### Step 11: Remove scheduler from backend
- Remove `setup_*_schedule()` calls and `scheduler.start()` from `backend/app/main.py`
- Remove `from app.scheduler import ...` imports
- Delete `backend/app/scheduler.py`
- Verify: backend starts without APScheduler, all backend tests pass

### Step 12: Update deployment
- Add `scheduler_worker` service to `docker-compose.yml` and `docker-compose.dev.yml`
- `scheduler_worker` depends on `backend` (service_healthy) — needs DB to be ready
- Add healthcheck on `http://localhost:8002/health`
- Verify: `docker compose up` starts all services, scheduler_worker logs show jobs registered

## Deployment Configuration

```yaml
# docker-compose.yml addition
scheduler_worker:
  build: ./server/apps/scheduler_worker
  container_name: numina-scheduler-worker
  restart: unless-stopped
  volumes:
    - ./data:/app/data
  env_file:
    - .env
  environment:
    - TZ=Asia/Shanghai
    - DATABASE_URL=${DATABASE_URL:-sqlite:////app/data/numina.db}
    - AI_ENCRYPTION_KEY=${AI_ENCRYPTION_KEY:-}
  depends_on:
    backend:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 15s
```

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Circular imports during migration (backend imports packages, packages imports backend) | Packages must never import from `backend/app/`. Enforce via ruff import rules or manual review. |
| SQLAlchemy `Base.metadata` doesn't know about models in packages | `scheduler_worker/main.py` must import all models before creating tables or running migrations. |
| Snowflake ID generator not initialized in scheduler_worker | Call `init_snowflake()` in scheduler_worker lifespan before any DB operations. |
| Config duplication (backend settings vs scheduler_worker settings) | Both import from `packages/core/settings`. Single source of truth. |
| File sync job interrupted mid-upload on restart | Accepted: `FileRemoteLocation.sync_status = "pending"` rows are retried on next cycle. |
| Alembic migration path broken after model moves | Keep Alembic in `backend/` but import models from `packages/db/`. Update `env.py` import path. |
| Scheduler_worker needs same env vars as backend | Document required env vars in `scheduler_worker/README.md`. Share `.env` file via Docker volume. |

## Success Criteria

- Backend starts without APScheduler in lifespan
- Scheduler_worker starts independently and registers all 7 jobs
- Backend restart does not interrupt scheduler_worker
- All 7 jobs execute on schedule (verify via scheduler_worker logs)
- All backend tests pass (`uv run pytest tests/ -v`)
- Scheduler_worker health check responds at `/health`
- No cross-app Python imports (`scheduler_worker` does not import `backend/app/`, `backend/app/` does not import `scheduler_worker/`)

## Out of Scope (Phase 2)

- Agent scheduler activation (dormant jobs remain dormant)
- Worker queue abstraction (Celery/RQ/Redis)
- Full apps+packages decomposition (agent_api, contracts, clients, observability packages)
- Horizontal scaling of scheduler_worker
- Job persistence or retry infrastructure
- Distributed locking for multi-instance scheduler_worker
