---
title: Backend Module Extraction — apps + packages Workflow
date: 2026-05-14
category: workflow-issues
module: backend
problem_type: workflow_issue
component: development_workflow
severity: medium
applies_when:
  - Monolithic FastAPI with mixed runtime concerns (API + scheduler + domain logic)
  - Scheduled jobs importing FastAPI Depends() or request context
  - Domain logic embedded in route files with no clear package boundary
  - Deployment friction from coupling API and background worker processes
  - Test isolation difficulty requiring full FastAPI app fixture for job tests
tags:
  - python
  - refactoring
  - module-extraction
  - fastapi
  - architecture
  - apscheduler
  - sqlalchemy
---

# Backend Module Extraction — apps + packages Workflow

## Context

The Numina backend began as a monolithic FastAPI application with mixed runtime responsibilities: API server logic, scheduled jobs (APScheduler), domain services, and infrastructure code all coexisted in a single `backend/app/` directory. This created several friction points:

- **Deployment coupling**: Scheduler jobs ran in the same process as the API server, forcing monolithic deployments even when only one component needed updates
- **Import complexity**: Jobs imported FastAPI dependencies (`Depends`, request context) that are inappropriate for background worker contexts
- **Testing isolation**: Scheduled job tests required full FastAPI app setup, slowing test execution and complicating fixture management
- **Domain logic reuse**: Business services (audit, exchange_rate, notification) were embedded in app routes, making them difficult to reuse across different runtime contexts (API vs. worker vs. CLI tools)
- **Circular dependency risk**: No clear architectural boundaries between domain services and route handlers

The refactoring extracted 5 domain packages and 1 standalone worker app over 13 sequential implementation units, each verified by the full test suite before committing.

## Guidance

### Core Principle: Extract Packages First, Apps Last

Apps consume packages. Packages never import from apps. This constraint is enforced by directory structure, not convention.

```
server/
├── apps/
│   └── scheduler_worker/     # Runtime entrypoint — imports from packages only
└── packages/
    ├── core/                 # Config, logging, errors, settings
    ├── db/                   # SQLAlchemy engine, session, Base
    ├── security/             # JWT, auth, user identity
    ├── storage/              # Storage backend abstractions
    └── domain/               # Business services
        ├── audit/
        ├── device/
        ├── exchange_rate/
        ├── notification/
        └── snapshot/
```

### Extraction Workflow (per unit)

Each package extraction follows the same 5-step cycle:

1. **Create package directory structure**
   ```bash
   mkdir -p server/packages/<name>
   touch server/packages/<name>/__init__.py
   ```

2. **Move code from backend to package**
   - Move domain logic files (services, models, utilities)
   - Preserve file names and internal structure initially
   - Update package `__init__.py` to expose key exports

3. **Update imports across backend and all packages**
   - Replace `from app.<module>` with `from packages.<name>`
   - Fix transitive imports (packages importing other packages)

4. **Verify with tests — all must pass before committing**
   ```bash
   pytest server/tests/backend/ -v
   ```

5. **Commit with conventional message**
   ```bash
   git add server/packages/<name> backend/
   git commit -m "refactor(packages): extract <name> package from backend"
   ```

Repeat for each domain package, then extract apps.

### Import Direction Rules

```python
# ✅ Backend imports packages
from packages.domain.exchange_rate import ExchangeRateService

# ✅ Packages import other packages
from packages.db.session import SessionLocal

# ❌ Packages NEVER import backend
from app.routers import ...  # forbidden

# ❌ Apps NEVER import other apps
from apps.backend_api import ...  # forbidden
```

### Job Isolation: SessionLocal, not Depends(get_db)

Jobs run outside request context. `Depends(get_db)` requires a FastAPI request — use `SessionLocal()` directly:

```python
# apps/scheduler_worker/jobs/__init__.py
from packages.db.session import SessionLocal
from packages.domain.snapshot.service import auto_generate_daily_snapshots

def snapshot_job() -> None:
    db = SessionLocal()
    try:
        auto_generate_daily_snapshots(db)
    except Exception as e:
        logger.exception(f"snapshot job failed: {e}")
    finally:
        db.close()
```

### Pythonpath Configuration

Since `server/` is at the repo root and backend's `pythonpath = ["."]` resolves relative to `backend/`, add `"../server"` to `pythonpath` in `backend/pyproject.toml` so `from packages.*` imports resolve from within the backend test suite:

```toml
# backend/pyproject.toml
[tool.pytest.ini_options]
pythonpath = [".", "../server"]
```

### Alembic: Models Travel with Their Domain Package

Each domain unit migrates both the service and its SQLAlchemy models together. Models are placed in `packages/db/models/` (not inside the domain package) to keep the db package as the single source of truth for Alembic. Update `alembic/env.py` incrementally — one import block added per unit:

```python
# backend/alembic/env.py
from packages.db.models.security_audit_log import SecurityAuditLog  # added in Unit 6
from packages.db.models.exchange_rate import ExchangeRate            # added in Unit 7
```

### Thin Wrapper Pattern for Deeply Coupled Services

Some domain services are deeply coupled to backend models (`Asset`, `Family`, `User`). Moving them fully to `packages/` would require pulling in the entire backend. Use thin wrappers that delegate to `app.services.*` via the shim chain, and defer full extraction to a later phase:

```python
# server/packages/domain/notification/service.py
def run_scheduled_checks(db) -> None:
    """Thin wrapper — delegates to backend service until Phase 2 extraction."""
    from app.services.notification import run_scheduled_checks as _impl
    return _impl(db)
```

## Why This Matters

### Testability

Domain packages can be tested independently of FastAPI — no app fixture, no `Depends` mocking:

```python
# packages/domain/exchange_rate/tests/test_service.py
from packages.db.session import SessionLocal
from packages.domain.exchange_rate.service import ExchangeRateService

def test_fetch_rates(db):
    service = ExchangeRateService(db)
    rates = service.fetch_latest_rates()
    assert rates is not None
```

### Deployment Isolation

Scheduler worker can deploy independently:

```bash
# Fix a broken job without touching the API server
docker-compose up -d scheduler_worker
```

### Maintainability

- **Clear boundaries**: New developers see `packages/domain/` and know where business logic lives
- **No circular imports**: Import direction is enforced by directory structure
- **Reuse paths**: A future CLI tool can import `packages.domain.snapshot` without FastAPI baggage

## When to Apply

- Monolithic FastAPI with mixed runtime concerns (API + scheduler + domain logic in one `app/`)
- Scheduled tasks using `Depends(get_db)` or `Depends(get_current_user)`
- Business services defined inside router files or `app/services/` with route coupling
- "I need to redeploy the entire app to fix a cron job"
- Job tests requiring full FastAPI app fixture setup
- Wanting to call business logic from CLI tools, scripts, or multiple apps

**Prerequisites:**
- Existing backend tests pass (`pytest backend/tests/`)
- Clear domain boundaries identified (audit, exchange_rate, notification, etc.)
- Alembic migrations independent of app structure (migrations stay in `backend/alembic/`)

## Examples

### Example 1: Extract core config package

```python
# Before — backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    UPLOAD_DIR: str

# After — server/packages/core/settings.py (same content, new location)
# backend/app/config.py becomes a re-export shim:
from packages.core.settings import Settings, settings  # noqa: F401
```

### Example 2: Extract db package with SessionLocal

```python
# Before — backend/app/database.py
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# After — server/packages/db/session.py
SessionLocal = sessionmaker(bind=engine)
# get_db() stays in backend/app/database.py (FastAPI-specific dependency)
```

### Example 3: Extract domain service

```python
# Before — backend/app/services/exchange_rate.py
from app.database import SessionLocal
from app.models import ExchangeRate

class ExchangeRateService:
    def fetch_and_store_rates(self, db) -> bool: ...

# After — server/packages/domain/exchange_rate/service.py
from packages.db.session import SessionLocal
from packages.db.models.exchange_rate import ExchangeRate

class ExchangeRateService:
    def fetch_and_store_rates(self, db) -> bool: ...  # same implementation

# backend/app/services/exchange_rate.py becomes a shim:
from packages.domain.exchange_rate.service import ExchangeRateService  # noqa: F401
```

### Example 4: Worker app entrypoint

```python
# apps/scheduler_worker/main.py
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from packages.core.logging import get_logger

app = FastAPI(title="Numina Scheduler Worker")
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
logger = get_logger(__name__)

@app.on_event("startup")
async def startup():
    from apps.scheduler_worker.jobs import (
        fetch_rates_job, file_sync_job, audit_log_purge_job,
        revoked_token_cleanup_job, device_session_cleanup_job,
        reminder_job, snapshot_job,
    )
    scheduler.add_job(fetch_rates_job, "cron", hour=6, minute=0)
    scheduler.add_job(file_sync_job, "interval", minutes=5)
    # ... other jobs
    scheduler.start()

@app.get("/health")
def health():
    return {"status": "ok", "jobs": len(scheduler.get_jobs())}
```

## Pitfalls Encountered (session history)

### Plan file write failures on large content
During planning, Write tool calls failed 8 consecutive times when the plan content was too large. Fix: request a minimal plan with only headers, task items, and acceptance criteria. That succeeds immediately.

### Over-scoped unit design
The first plan draft merged all 5 domain packages into a single unit. This was corrected to one unit per package — the Strangler Fig step-by-step verification requirement means each extraction must be independently verified before proceeding.

### Test patching paths break after extraction
After moving `revoke_jti` to `packages/security/`, tests that patched `app.auth.revoke_jti.SessionLocal` failed because the module was now a shim with no `SessionLocal` attribute. Fix: update test patches to target the new canonical location:
```python
# Before
with patch("app.auth.revoke_jti.SessionLocal", ...):

# After
with patch("packages.security.revoke_jti.SessionLocal", ...):
```

### Behavioral regression when rewriting jobs
When rewriting `file_sync_job` for the new worker app, two behaviors from the original were accidentally dropped: (1) the `retry_count < 3` query filter, and (2) explicit `TimeoutError` and `FileNotFoundError` exception handlers. The generic `except Exception` produced empty error strings for `TimeoutError`. Fix: read the original implementation from git history before rewriting:
```bash
git show HEAD~N:backend/app/scheduler.py
```

### Session lifecycle in extracted audit service
After extracting `write_audit_log` to `packages/domain/audit/service.py`, the function created its own `SessionLocal()` and called `db.close()` in a `finally` block. In tests, `SessionLocal` is patched to return the shared test session — calling `close()` on it invalidated the entire test transaction. Fix: use the session-as-argument pattern with `flush()` instead of `commit()` when a caller session is provided. See [audit-service-session-closure-test-isolation-2026-05-14.md](../test-failures/audit-service-session-closure-test-isolation-2026-05-14.md).

## Related

- [audit-service-session-closure-test-isolation-2026-05-14.md](../test-failures/audit-service-session-closure-test-isolation-2026-05-14.md) — Session lifecycle pitfall when extracting services that previously owned their own session
- [file-storage-abstraction-2026-04-10.md](../best-practices/file-storage-abstraction-2026-04-10.md) — APScheduler background job patterns and session lifecycle in async jobs
- [monorepo-module-level-lint-format-typecheck-2026-04-12.md](../developer-experience/monorepo-module-level-lint-format-typecheck-2026-04-12.md) — Module-level tooling setup for the monorepo structure
- Plan: `docs/plans/2026-05-13-001-refactor-scheduler-worker-extraction-plan.md`
- Requirements: `docs/brainstorms/2026-05-13-runtime-decomposition-scheduler-worker-requirements.md`
