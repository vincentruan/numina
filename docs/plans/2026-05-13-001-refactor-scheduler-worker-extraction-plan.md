---
title: "refactor: Extract Scheduler/Worker to Standalone Process"
type: refactor
status: active
date: 2026-05-13
origin: docs/brainstorms/2026-05-13-runtime-decomposition-scheduler-worker-requirements.md
---

# refactor: Extract Scheduler/Worker to Standalone Process

## Overview

Extract APScheduler + 7 background jobs from the backend into a standalone `scheduler_worker`
process. Backend becomes API-only. Shared business logic moves to `server/packages/` so both
apps import from the same source. Follows Strangler Fig — each unit is independently deployable
and backend tests must pass after every step before proceeding.

## Requirements Trace

- R1. Backend restarts must not interrupt scheduled jobs
- R2. All 7 jobs must execute on schedule in the new process
- R3. No cross-app Python imports (scheduler_worker ↔ backend)
- R4. All backend tests pass after each extraction step
- R5. scheduler_worker exposes `/health` endpoint for Docker healthcheck
- R6. scheduler_worker starts independently (does not import from `backend/app/`)

## Scope Boundaries

- Agent scheduler (dormant) — untouched
- Queue abstraction (Celery/RQ) — deferred to Phase 2
- Full apps+packages decomposition (agent_api, contracts, clients, observability) — Phase 2
- Job persistence / retry infrastructure — out of scope
- Horizontal scaling of scheduler_worker — out of scope

### Deferred to Separate Tasks

- `server/apps/backend_api/` full migration: separate Phase 2 effort; Unit 1 only creates a stub dir
- Agent scheduler activation: separate task after Phase 1 validated in production

## Implementation Units

- [ ] **Unit 1: Create directory skeleton** *(spec Step 0)*

  Create the target directory structure with `__init__.py` stubs and a `README.md` per package.
  No code moved. The `backend_api/` stub signals the future migration target but is not populated in Phase 1.

  `__init__.py` files (empty stubs):
  - Create: `server/__init__.py`
  - Create: `server/apps/__init__.py`
  - Create: `server/apps/backend_api/__init__.py` (stub — Phase 2 target)
  - Create: `server/apps/scheduler_worker/__init__.py`
  - Create: `server/packages/__init__.py`
  - Create: `server/packages/core/__init__.py`
  - Create: `server/packages/db/__init__.py`
  - Create: `server/packages/storage/__init__.py`
  - Create: `server/packages/security/__init__.py`
  - Create: `server/packages/domain/__init__.py`
  - Create: `server/packages/domain/exchange_rate/__init__.py`
  - Create: `server/packages/domain/audit/__init__.py`
  - Create: `server/packages/domain/device/__init__.py`
  - Create: `server/packages/domain/notification/__init__.py`
  - Create: `server/packages/domain/snapshot/__init__.py`

  `README.md` stubs (one per package, each containing: package name, one-line purpose, Phase 1/2 status):
  - Create: `server/packages/core/README.md` — "Config (settings) and logging (get_logger). Phase 1: active."
  - Create: `server/packages/db/README.md` — "SQLAlchemy engine, SessionLocal, Base, and shared models. Phase 1: active."
  - Create: `server/packages/storage/README.md` — "Storage backends (local/GitHub/WebDAV), factory, and crypto. Phase 1: active."
  - Create: `server/packages/security/README.md` — "Auth utilities: JWT revocation (revoke_jti). Phase 1: active."
  - Create: `server/packages/domain/exchange_rate/README.md` — "ExchangeRateService: fetch and store exchange rates. Phase 1: active."
  - Create: `server/packages/domain/audit/README.md` — "Audit log purge: purge_old_audit_logs. Phase 1: active."
  - Create: `server/packages/domain/device/README.md` — "Device session cleanup: cleanup_expired_device_sessions, delete_old_revoked_sessions. Phase 1: active."
  - Create: `server/packages/domain/notification/README.md` — "Notification dispatcher: run_scheduled_checks (reminders, alerts). Phase 1: active."
  - Create: `server/packages/domain/snapshot/README.md` — "Daily snapshot generation: auto_generate_daily_snapshots. Phase 1: active."
  - Create: `server/apps/backend_api/README.md` — "Backend API app entry point. Phase 1: stub only. Phase 2: full migration from backend/."
  - Create: `server/apps/scheduler_worker/README.md` — "Scheduler + worker combined process. Phase 1: active. Runs all 7 APScheduler jobs independently from backend."

  **Verification:** `find server/ -name "__init__.py" | wc -l` returns 15; `find server/ -name "README.md" | wc -l` returns 11; no existing backend tests broken.

- [ ] **Unit 2: Extract packages/core** *(spec Step 1)*

  Move `settings` and `get_logger` to `packages/core/`. Update all backend imports.
  This is the lowest-risk extraction — no DB, no models, no external calls.

  - Move: `backend/app/config.py` → `server/packages/core/settings.py`
  - Move: `backend/app/core/logging_config.py` → `server/packages/core/logging.py`
  - Modify: all `from app.config import settings` → `from packages.core.settings import settings` in backend
  - Modify: all `from app.core.logging_config import get_logger` → `from packages.core.logging import get_logger` in backend
  - Add: re-export shims in `backend/app/config.py` and `backend/app/core/logging_config.py` if needed to avoid touching every file at once

  **Verification:** `uv run pytest tests/ -v` passes; `uv run ruff check .` passes; `uv run mypy app/` passes.

- [ ] **Unit 3: Extract packages/db** *(spec Step 2)*

  Move `SessionLocal`, `Base`, and the **3 models the scheduler directly queries** to `packages/db/`.
  Other models (RevokedToken, DeviceSession, AssetSnapshot, etc.) migrate with their domain packages
  in Units 5–10. Moving only these 3 now minimises the blast radius.

  Models to move (storage-layer models used by `file_sync_job`):
  - `backend/app/models/cached_file.py` → `server/packages/db/models/cached_file.py`
  - `backend/app/models/file_remote_location.py` → `server/packages/db/models/file_remote_location.py`
  - `backend/app/models/storage_backend.py` → `server/packages/db/models/storage_backend.py`

  Files:
  - Move: `backend/app/database.py` → `server/packages/db/session.py`
  - Move: above 3 model files → `server/packages/db/models/`
  - Create: `server/packages/db/models/__init__.py`
  - Modify: backend imports to use `packages.db.session` and `packages.db.models.*`
  - Modify: `backend/alembic/env.py` — import models from `packages.db.models` (in addition to remaining `backend/app/models/`)

  **Verification:** `uv run pytest tests/ -v` passes; `uv run alembic check` passes (no pending migrations detected); backend starts cleanly.

- [ ] **Unit 4: Extract packages/storage** *(spec Step 3)*

  Move the entire `services/storage/` directory to `packages/storage/`. This package depends on
  the 3 models already in `packages/db/` (Unit 3 must be complete first).

  - Move: `backend/app/services/storage/base.py` → `server/packages/storage/base.py`
  - Move: `backend/app/services/storage/factory.py` → `server/packages/storage/factory.py`
  - Move: `backend/app/services/storage/config_crypto.py` → `server/packages/storage/config_crypto.py`
  - Move: `backend/app/services/storage/local.py` → `server/packages/storage/local.py`
  - Move: `backend/app/services/storage/github.py` → `server/packages/storage/github.py`
  - Move: `backend/app/services/storage/webdav.py` → `server/packages/storage/webdav.py`
  - Modify: backend imports (`from app.services.storage.*` → `from packages.storage.*`)

  **Verification:** `uv run pytest tests/ -v` passes (including `test_file_sync.py`); file upload/download endpoints work.

- [ ] **Unit 5: Extract packages/security** *(spec Step 4)*

  Move `revoke_jti.py` to `packages/security/`. This module has no model dependencies beyond
  `RevokedToken` which stays in `backend/app/models/` for now (migrates with domain in Unit 7).
  `cleanup_expired_revoked_tokens(db)` is the only function the scheduler calls.

  - Move: `backend/app/auth/revoke_jti.py` → `server/packages/security/revoke_jti.py`
  - Modify: backend imports (`from app.auth.revoke_jti import ...` → `from packages.security.revoke_jti import ...`)

  **Verification:** `uv run pytest tests/ -v` passes; auth endpoints work; token revocation tests pass.

- [ ] **Unit 6: Extract packages/domain/exchange_rate** *(spec Step 5)*

  Move `ExchangeRateService` to `packages/domain/exchange_rate/`. Depends on `ExchangeRate` and
  `Currency` models — migrate those models to `packages/db/models/` as part of this unit.

  Models to migrate alongside:
  - `backend/app/models/exchange_rate.py` → `server/packages/db/models/exchange_rate.py`
  - `backend/app/models/currency.py` → `server/packages/db/models/currency.py`

  Files:
  - Move: `backend/app/services/exchange_rate.py` → `server/packages/domain/exchange_rate/service.py`
  - Move: above 2 model files → `server/packages/db/models/`
  - Modify: backend imports; update `backend/alembic/env.py` for moved models

  **Verification:** `uv run pytest tests/ -v` passes (including `test_exchange_rate.py`); exchange rate endpoints work.

- [ ] **Unit 7: Extract packages/domain/audit** *(spec Step 6)*

  Move `purge_old_audit_logs` to `packages/domain/audit/`. Depends on `SecurityAuditLog` model.
  Note: `purge_old_audit_logs` creates its own `SessionLocal()` internally — this is acceptable
  and documented; do not refactor the session pattern during this migration.

  Models to migrate alongside:
  - `backend/app/models/security_audit_log.py` → `server/packages/db/models/security_audit_log.py`

  Files:
  - Move: `backend/app/services/audit_log.py` → `server/packages/domain/audit/service.py`
  - Move: above model file → `server/packages/db/models/`
  - Modify: backend imports; update `backend/alembic/env.py`

  **Verification:** `uv run pytest tests/ -v` passes; audit log endpoints work.

- [ ] **Unit 8: Extract packages/domain/device** *(spec Step 7)*

  Move device session cleanup functions to `packages/domain/device/`. Depends on `DeviceSession`
  model. Also migrate `RevokedToken` model here (used by `packages/security/revoke_jti.py`
  which was extracted in Unit 5).

  Models to migrate alongside:
  - `backend/app/models/device_session.py` → `server/packages/db/models/device_session.py`
  - `backend/app/models/revoked_token.py` → `server/packages/db/models/revoked_token.py`

  Files:
  - Move: `backend/app/services/device.py` → `server/packages/domain/device/service.py`
  - Move: above 2 model files → `server/packages/db/models/`
  - Modify: backend imports; update `backend/alembic/env.py`

  **Verification:** `uv run pytest tests/ -v` passes; device session endpoints work.

- [ ] **Unit 9: Extract packages/domain/notification** *(spec Step 8)*

  Move `run_scheduled_checks` and its dispatcher to `packages/domain/notification/`. This is the
  most complex domain — `run_scheduled_checks` uses `asyncio.get_running_loop().create_task()` for
  Telegram dispatch, so it **must** run inside an active event loop (AsyncIOScheduler provides this).

  Models to migrate alongside (all notification-related models):
  - `backend/app/models/reminder.py` → `server/packages/db/models/reminder.py`
  - `backend/app/models/notification_channel.py` → `server/packages/db/models/notification_channel.py`
  - `backend/app/models/notification_channel_config.py` → `server/packages/db/models/notification_channel_config.py`
  - `backend/app/models/notification_subscription.py` → `server/packages/db/models/notification_subscription.py`
  - `backend/app/models/notification_config.py` → `server/packages/db/models/notification_config.py`
  - `backend/app/models/reminder_notification.py` → `server/packages/db/models/reminder_notification.py`
  - `backend/app/models/ai_allocation_target.py` → `server/packages/db/models/ai_allocation_target.py`

  Files:
  - Move: `backend/app/services/notification/dispatcher.py` → `server/packages/domain/notification/dispatcher.py`
  - Move: other files in `backend/app/services/notification/` as needed (check for helpers)
  - Move: above model files → `server/packages/db/models/`
  - Modify: backend imports; update `backend/alembic/env.py`

  **Verification:** `uv run pytest tests/ -v` passes; notification endpoints work.

- [ ] **Unit 10: Extract packages/domain/snapshot** *(spec Step 9)*

  Move `auto_generate_daily_snapshots` to `packages/domain/snapshot/`. Depends on `Family`, `User`,
  `Asset`, `Liability`, `AssetSnapshot` models and calls `ExchangeRateService.convert` (already in
  `packages/domain/exchange_rate/` from Unit 6).

  Models to migrate alongside:
  - `backend/app/models/snapshot.py` (AssetSnapshot) → `server/packages/db/models/snapshot.py`
  - `backend/app/models/family.py` → `server/packages/db/models/family.py`
  - `backend/app/models/user.py` → `server/packages/db/models/user.py`
  - `backend/app/models/asset.py` → `server/packages/db/models/asset.py`
  - `backend/app/models/liability.py` → `server/packages/db/models/liability.py`

  Files:
  - Move: `backend/app/services/snapshot.py` → `server/packages/domain/snapshot/service.py`
  - Move: above model files → `server/packages/db/models/`
  - Modify: backend imports; update `backend/alembic/env.py`

  **Verification:** `uv run pytest tests/ -v` passes; snapshot endpoints work.

- [ ] **Unit 11: Create scheduler_worker app** *(spec Step 10)*

  Create the standalone FastAPI app with AsyncIOScheduler lifespan. Job functions import from
  `server/packages/*`. Schedules must match `backend/app/scheduler.py` exactly.
  Call `init_snowflake()` and `setup_logging()` in lifespan before any DB operations.

  - Create: `server/apps/scheduler_worker/main.py` — FastAPI app + AsyncIOScheduler lifespan + `/health`
  - Create: `server/apps/scheduler_worker/jobs/__init__.py`
  - Create: `server/apps/scheduler_worker/jobs/exchange_rate.py` — `fetch_rates_job`, `setup_exchange_rate_schedule`
  - Create: `server/apps/scheduler_worker/jobs/file_sync.py` — `file_sync_job`, `setup_file_sync_schedule`
  - Create: `server/apps/scheduler_worker/jobs/audit.py` — `audit_log_purge_job`, `setup_audit_log_purge_schedule`
  - Create: `server/apps/scheduler_worker/jobs/security.py` — `revoked_token_cleanup_job`, `setup_revoked_token_cleanup_schedule`
  - Create: `server/apps/scheduler_worker/jobs/device.py` — `device_session_cleanup_job`, `setup_device_session_cleanup_schedule`
  - Create: `server/apps/scheduler_worker/jobs/notification.py` — `_reminder_job`, `setup_reminder_schedule`
  - Create: `server/apps/scheduler_worker/jobs/snapshot.py` — `snapshot_job`, `setup_snapshot_schedule`
  - Create: `server/apps/scheduler_worker/pyproject.toml` — mirrors `backend/pyproject.toml` structure; depends on `server/packages/*`
  - Create: `server/apps/scheduler_worker/Dockerfile`
  - Create: `server/apps/scheduler_worker/CLAUDE.md` — Quality Commands, Key Invariants, env vars table

  **Verification:** `scheduler_worker` starts independently; all 7 jobs register in logs; `GET /health` returns 200; no imports from `backend/app/`.

- [ ] **Unit 12: Remove scheduler from backend** *(spec Step 11)*

  Remove APScheduler from the backend process. Backend becomes API-only.

  - Modify: `backend/app/main.py` — remove all `setup_*_schedule()` calls, `scheduler.start()`, `scheduler.shutdown()`, and scheduler imports
  - Delete: `backend/app/scheduler.py`
  - Modify: `backend/pyproject.toml` — remove `apscheduler` dependency if no longer needed by backend

  **Verification:** `uv run pytest tests/ -v` passes; backend starts without APScheduler in logs; no `apscheduler` import in `backend/app/main.py`.

- [ ] **Unit 13: Update deployment** *(spec Step 12)*

  Add `scheduler_worker` service to both compose files. Service depends on `backend` being healthy
  so the DB is ready before jobs run.

  - Modify: `docker-compose.yml` — add `scheduler_worker` service:
    ```
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
  - Modify: `docker-compose.dev.yml` — add same `scheduler_worker` service block

  **Verification:** `docker compose up` starts all services; `scheduler_worker` logs show all 7 jobs registered; `docker compose ps` shows `scheduler_worker` healthy.

## Key Technical Decisions

- **AsyncIOScheduler** — kept (required: `file_sync_job` is async coroutine; `_reminder_job` calls `asyncio.get_running_loop().create_task()` for Telegram dispatch — must run inside active event loop)
- **Combined scheduler+worker process** — no queue, no HTTP between scheduler and worker; APScheduler triggers job functions directly in-process
- **Strangler Fig sequence** — one package per unit; backend tests must pass after every unit before proceeding to the next
- **Models migrate with their domain** — each domain unit migrates its own models to `packages/db/models/`; Unit 3 only moves the 3 storage models needed by `file_sync_job`
- **Alembic stays in backend** — `backend/alembic/env.py` imports models from both `backend/app/models/` (remaining) and `packages.db.models` (migrated); updated incrementally per unit
- **`init_snowflake()` in scheduler_worker lifespan** — must call before any DB operations that generate IDs
- **`setup_logging()` in scheduler_worker lifespan** — explicit call at startup; not inherited from backend
- **`purge_old_audit_logs` session pattern** — creates its own `SessionLocal()` internally; acceptable, not refactored during migration
- **`server/apps/backend_api/`** — stub only in Phase 1; full migration deferred to Phase 2

## Risks

| Risk | Mitigation |
|------|-----------|
| Circular imports during migration | packages must never import from `backend/app/`; enforce via `uv run ruff check` after each unit |
| SQLAlchemy `Base.metadata` missing models in scheduler_worker | `scheduler_worker/main.py` imports all models from `packages.db.models` before DB ops |
| Alembic broken after model moves | Update `backend/alembic/env.py` per unit; run `uv run alembic check` after each model migration |
| `_reminder_job` requires active event loop | Use `AsyncIOScheduler` (not `BackgroundScheduler`); do not switch scheduler type |
| `purge_old_audit_logs` creates its own session | Acceptable; document in `packages/domain/audit/service.py` docstring |
| Config validation raises `RuntimeError` in production | scheduler_worker needs same env vars as backend; document in `scheduler_worker/CLAUDE.md` |
| File sync job interrupted mid-upload on restart | Accepted: `FileRemoteLocation.sync_status = "pending"` rows retried on next cycle |

## Verification (Success Criteria)

- [ ] Backend starts without APScheduler in lifespan
- [ ] scheduler_worker starts independently and registers all 7 jobs
- [ ] Backend restart does not interrupt scheduler_worker
- [ ] `GET http://localhost:8002/health` returns 200
- [ ] `uv run pytest tests/ -v` passes in backend after each unit
- [ ] No cross-app imports: `grep -r "from backend.app" server/apps/scheduler_worker/` returns nothing
- [ ] All 7 jobs execute on schedule (verify via scheduler_worker logs)
- [ ] `docker compose up` starts all services; `scheduler_worker` shows healthy in `docker compose ps`
