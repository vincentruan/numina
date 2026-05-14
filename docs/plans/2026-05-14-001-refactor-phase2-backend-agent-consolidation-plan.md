---
title: "refactor: Phase 2 — Consolidate backend/ and agent/ into server/ monorepo"
type: refactor
status: active
date: 2026-05-14
origin: docs/brainstorms/2026-05-13-runtime-decomposition-scheduler-worker-requirements.md
---

# refactor: Phase 2 — Consolidate backend/ and agent/ into server/ monorepo

## Pre-migration Problem List

Before Phase 2, the repo exhibits these structural issues:

### P0: Python Version Conflict
- **backend/**: `requires-python = ">=3.11"` (backend/pyproject.toml)
- **agent/**: `requires-python = ">=3.12"` (agent/pyproject.toml, DeerFlow constraint)
- **Conflict**: Both directories cannot merge into a single `server/pyproject.toml` without resolving version mismatch
- **Resolution**: Adopt `>=3.12` as unified version (agent/DeerFlow hard constraint)

### P1: Duplicate Project Management
- backend/pyproject.toml + uv.lock + .venv (57 models, 38 routers, 3122 files)
- agent/pyproject.toml + uv.lock + .venv (14 routers, DeerFlow harness, 33514 files)
- server/apps/scheduler_worker/pyproject.toml + uv.lock + .venv (Phase 1 orphan)
- **Total**: 4 separate Python projects, 4 lockfiles, 4 venvs
- **Risk**: Dependency drift, version conflicts, duplicated infrastructure

### P1: Incomplete Phase 1 Stub
- server/apps/backend_api/ exists as empty stub (README: "Phase 1: stub only. Phase 2: full migration from backend/")
- Actual backend code still in root backend/ directory
- **Inconsistency**: packages/domain/* import from backend/app.models but backend not in server/apps

### P2: Import Path Instability
- packages/domain/audit imports from backend/app.services.audit_log (shim pattern)
- packages/domain/notification imports from backend/app.services.notification (shim pattern)
- packages/db/models imports from backend/app.utils.snowflake (via PYTHONPATH hack)
- **Risk**: If backend/ moves without import updates, packages break

### P2: DeerFlow Workspace Coupling
- agent/vendor/deerflow-harness is a uv workspace member (agent/pyproject.toml declares it)
- Workspace path: `members = ["vendor/deerflow-harness"]` (relative to agent/)
- **Risk**: If agent/ moves to server/apps/agent/, workspace member path must update to `"apps/agent/vendor/deerflow-harness"` relative to server/

### P3: Alembic Import Paths
- backend/alembic/env.py imports models from backend/app.models
- packages/db/models contains SecurityAuditLog, ExchangeRate (Phase 1 migrations)
- **Hybrid state**: Some models in backend, some in packages
- **Resolution**: Incremental model moves with env.py updates per unit

## Overview

Phase 1 extracted scheduler_worker and domain packages from backend into `server/`. Phase 2 completes the consolidation: backend/ and agent/ migrate into `server/apps/`, all Python dependencies unify under a single `server/pyproject.toml` + `uv.lock` (with DeerFlow as partial workspace member), and shared capabilities are reorganized in `server/packages/` following clear ownership rules.

Target architecture:

```
server/
├── pyproject.toml          ← single unified project config
├── uv.lock                 ← single lockfile
├── apps/                   ← runtime entry points (deployed processes)
│   ├── backend/            ← application service (family asset management)
│   │   ├── app/            ← current backend/app structure (routers, services, models)
│   │   ├── alembic/        ← backend DB migrations
│   │   ├── Dockerfile
│   │   └── main.py
│   ├── agent/              ← AI service (DeerFlow-powered)
│   │   ├── app/            ← agent code
│   │   ├── vendor/         ← DeerFlow harness
│   │   ├── core/           ← agent core adapters
│   │   ├── deerflow_config/
│   │   ├── skills/
│   │   ├── alembic/        ← agent DB migrations (if needed)
│   │   ├── Dockerfile
│   │   └── main.py
│   └── scheduler_worker/   ← task service (APScheduler + long-running jobs)
│       ├── jobs/
│       ├── alembic/        ← scheduler DB migrations (if needed)
│       ├── Dockerfile
│       └── main.py
├── packages/               ← shared capabilities (≥2 apps use)
│   ├── core/               ← non-business utilities (logging, settings, errors)
│   ├── db/                 ← unified DAO layer
│   │   ├── models/         ← all SQLAlchemy models (Family, User, AITask, etc.)
│   │   ├── session.py      ← SessionLocal, Base
│   │   └── engine.py       ← SQLite/PostgreSQL factory
│   ├── domain/             ← shared business domains
│   │   ├── audit/          ← audit logging (backend + scheduler_worker)
│   │   ├── device/         ← device management
│   │   ├── exchange_rate/  ← exchange rate service
│   │   ├── notification/   ← notification dispatch
│   │   ├── snapshot/       ← daily snapshot generation
│   │   ├── tasks/          ← task management (backend + agent + scheduler_worker)
│   │   ├── tenancy/        ← family tenant management (quota, features)
│   │   └── ...             ← future shared domains
│   ├── security/           ← authentication services
│   │   ├── frontend_auth/  ← user → backend/agent auth (JWT, WebAuthn)
│   │   ├── service_auth/   ← backend → agent/scheduler_worker auth (internal token)
│   │   └── revoke_jti.py   ← JWT revocation
│   └── storage/            ← file management (local, GitHub, WebDAV)
└── tests/                  ← unified test directory
    ├── backend/
    ├── agent/
    └── scheduler_worker/
```

## Requirements Trace

- R1. backend/ and agent/ directories **deleted from repo root** after migration
- R2. `server/pyproject.toml` and `server/uv.lock` are the **only** Python project files
- R3. Backend starts from `server/apps/backend/` with `uv run uvicorn apps.backend.app.main:app`
- R4. Agent starts from `server/apps/agent/` with `uv run uvicorn apps.agent.app.main:app`
- R5. Scheduler_worker continues working unchanged
- R6. All backend and agent tests pass from `server/tests/`
- R7. Docker Compose builds all three services from `server/` with correct build contexts
- R8. Alembic migrations apply from each app's `alembic/` directory
- R9. Family/User/AITask models accessible from `packages/db/models/`
- R10. No cross-app Python imports (`backend ↔ agent ↔ scheduler_worker`)
- R11. packages only contain code used by ≥2 apps (single-app code stays in apps)

## Scope Boundaries

### In Scope

- Move backend/ → server/apps/backend/ (directory move, minimal import changes)
- Move agent/ → server/apps/agent/ (directory move, preserve DeerFlow vendor)
- Consolidate pyproject.toml: merge backend + agent + scheduler_worker into server/pyproject.toml
- Delete scheduler_worker/pyproject.toml + uv.lock
- Move backend/tests/ → server/tests/backend/
- Move agent/tests/ → server/tests/agent/ (if exists)
- Reorganize packages/:
  - Move Family/User models to packages/db/models/
  - Create packages/domain/tenancy/ (family tenant services)
  - Create packages/domain/tasks/ (AITask service)
  - Reorganize packages/security/ into frontend_auth/ + service_auth/
- Update Docker Compose: backend and agent build from server/

### Out of Scope

- Rename internal directories (routers/ → api/, services/ → core/) — separate Phase 3
- Activate dormant agent scheduler jobs
- Introduce Celery/RQ queue abstraction
- Rename packages namespace to src layout
- Refactor business logic during migration
- Move single-app code to packages (only ≥2-app shared code migrates)

### Deferred to Separate Tasks

- Internal restructuring: routers/ → api/, services/ → core/ — separate task after Phase 2 stabilizes
- Agent scheduler activation — separate task after production validation
- Queue abstraction (Celery/RQ) — separate task if horizontal scaling needed

## Context & Research

### Relevant Code and Patterns

**Phase 1 extraction workflow** (docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md):
- Core principle: Extract packages first, apps last
- Import direction: apps import packages, packages never import apps
- Strangler Fig verification: Each unit passes full test suite before committing
- Pythonpath configuration: `"../server"` in backend pytest to resolve packages.*
- Thin wrapper pattern: For deeply coupled services, create shim that delegates to backend, defer full extraction

**Session lifecycle pattern** (docs/solutions/test-failures/audit-service-session-closure-test-isolation-2026-05-14.md):
- Never close a session you did not open
- Optional-session pattern: `db: Session | None = None` for dual-mode functions
- Use `flush()` not `commit()` when participating in caller's transaction

**Incremental formatting policy** (docs/solutions/developer-experience/monorepo-module-level-lint-format-typecheck-2026-04-12.md):
- Format only files you touch, not entire modules — prevents massive diffs obscuring blame

### Institutional Learnings

- **Strangler Fig discipline**: Each extraction unit verified independently before next unit starts
- **Import path test patches**: After extraction, test mocks must target new canonical locations
- **Snowflake ID generator**: backend/app/utils/snowflake.py imported by packages/db/models — must remain accessible
- **DeerFlow vendor workspace**: agent/vendor/deerflow-harness must remain uv workspace member
- **Alembic env.py**: Import models from both apps/backend/app/models and packages/db/models during transition

### Technology Stack

| Component | Framework | Dependencies |
|-----------|-----------|--------------|
| Backend | FastAPI 0.115+ | SQLAlchemy 2.0.36+, Alembic 1.14+, APScheduler 3.11.2, Pydantic 2.10+, Redis 5.0+ |
| Agent | FastAPI 0.115+, DeerFlow | LangChain 0.3+, Anthropic 0.40+, OpenAI 1.50+ |
| Scheduler_worker | FastAPI 0.115+, APScheduler 3.11.2 | SQLAlchemy 2.0.36+, httpx 0.28+ |

**Current state**:
- backend/: 57 models, 38 routers, 25 Alembic migrations, 3122 Python files
- agent/: 14 routers, DeerFlow harness, 33514 files (including vendor)
- scheduler_worker/: Phase 1成果，imports from packages.*

## Key Technical Decisions

### Decision 1: Single pyproject.toml with partial uv workspace

**Rationale**: backend, agent, scheduler_worker are runtime entry points, not independently published packages. DeerFlow vendor must remain a workspace member to preserve its build relationship.

**Configuration**:
```toml
[tool.uv.workspace]
members = ["apps/agent/vendor/deerflow-harness"]

[project.optional-dependencies]
backend = ["python-jose", "bcrypt", "webauthn", "redis", ...]
agent = ["langchain", "anthropic", "openai", ...]
worker = ["apscheduler", "cryptography"]
```

### Decision 2: Mass rewrite of `from app.*` → `from apps.backend.app.*`

**Rationale**: PYTHONPATH hacks (`pythonpath = [".", "apps/backend", "apps/agent"]`) create invisible import ambiguity — `from app.models.user import User` could resolve to either `apps/backend/app/models/user.py` or a future `apps/agent/app/models/user.py`. This ambiguity is undetectable at import time and causes silent failures in tests and production. Mass rewrite is the correct approach.

**Scope**: ~3000 `from app.*` imports in backend files, ~500 `from app.*` imports in agent files.

**Strategy**: Automated sed/ruff rewrite per unit, not manual. Each unit rewrites only the files it moves.

**Pattern**:
```python
# Before (backend files)
from app.models.user import User
from app.services.auth import login
from app.database import get_db

# After (backend files in server/apps/backend/)
from apps.backend.app.models.user import User
from apps.backend.app.services.auth import login
from apps.backend.app.database import get_db
```

```python
# Before (agent files)
from app.routers.tasks import router
from app.services.deerflow import run_flow

# After (agent files in server/apps/agent/)
from apps.agent.app.routers.tasks import router
from apps.agent.app.services.deerflow import run_flow
```

**Rewrite command per unit** (run from server/ after moving files):
```bash
# Rewrite backend app.* imports
find apps/backend -name "*.py" | xargs sed -i 's/from app\./from apps.backend.app./g'
find apps/backend -name "*.py" | xargs sed -i 's/import app\./import apps.backend.app./g'

# Rewrite agent app.* imports
find apps/agent -name "*.py" | xargs sed -i 's/from app\./from apps.agent.app./g'
find apps/agent -name "*.py" | xargs sed -i 's/import app\./import apps.agent.app./g'
```

**Exceptions** (do not rewrite):
- `from app.schemas.base import SnowflakeBase` — stays as-is within backend files
- `from packages.*` — already correct, no change needed
- `from apps.backend.app.*` — already rewritten, skip

**pytest pythonpath**: Minimal — only `["."]` to resolve `packages.*` from server root. No `apps/backend` or `apps/agent` in pythonpath.

### Decision 3: Alembic per app, independent migration paths

**Rationale**: User confirmed all three apps allow persistent DB schema. Independent migration paths prevent coupling between app schema evolutions.

**Structure**:
- server/apps/backend/alembic/ (moved from backend/alembic/)
- server/apps/agent/alembic/ (new, if agent needs schema)
- server/apps/scheduler_worker/alembic/ (new, if scheduler needs schema)

**Execution**: `uv run alembic -c apps/backend/alembic.ini upgrade head`

### Decision 4: packages ownership rules

**Rule**: Only code used by ≥2 apps migrates to packages. Single-app code stays in apps.

**Examples**:
- Family/User models → packages/db/models/ (backend + agent + scheduler_worker all query)
- AITask service → packages/domain/tasks/ (backend creates, scheduler_worker updates, agent queries)
- Family tenant quota → packages/domain/tenancy/ (backend + agent check quotas)
- Backend-specific AI reports → stay in apps/backend/app/services/
- Agent-specific DeerFlow adapters → stay in apps/agent/core/

### Decision 5: packages/domain/tenancy/ for tenant management

**Scope**: Family tenant management (quota allocation, feature flags, family/user queries).

**Structure**:
```
packages/domain/tenancy/
├── quota_service.py        ← check_family_quota, allocate_family_resources
├── features_service.py     ← get_enabled_features, check_feature_flag
├── family_service.py       ← get_family_by_id, validate_family_membership
├── user_service.py         ← get_user_by_id, get_family_members
```

**Note**: Family/User models live in packages/db/models/, services in packages/domain/tenancy/.

### Decision 6: packages/domain/tasks/ for task management

**Scope**: AITask model + service functions (create, update_status, query). Used by backend (create), scheduler_worker (execute), agent (monitor).

**Structure**:
```
packages/domain/tasks/
├── service.py              ← create_task, update_task_status, get_task_by_id
├── __init__.py
```

AITask model in packages/db/models/ai_task.py.

### Decision 7: packages/security/ reorganization

**Split**: frontend_auth (user authentication) vs. service_auth (internal service authentication).

**Structure**:
```
packages/security/
├── frontend_auth/
│   ├── jwt_service.py      ← create_access_token, verify_jwt
│   ├── webauthn_service.py ← WebAuthn registration/verification
│   └── password_service.py ← bcrypt hashing, verification
├── service_auth/
│   ├── internal_token.py   ← AGENT_INTERNAL_TOKEN validation
│   └── agent_jwt.py        ← backend → agent JWT creation (from backend/app/auth/ai_deps.py)
└── revoke_jti.py           ← JWT revocation (already exists)
```

## Implementation Units

### Unit 1: Consolidate pyproject.toml + rename stub

**Goal**: Single server/pyproject.toml, delete scheduler_worker orphan files, rename backend_api stub.

**Files**:
- Create: server/pyproject.toml (merge backend + agent + scheduler_worker dependencies)
- Delete: server/apps/scheduler_worker/pyproject.toml
- Delete: server/apps/scheduler_worker/uv.lock
- Delete: server/apps/scheduler_worker/.venv/
- Rename: server/apps/backend_api/ → server/apps/backend/
- Run: `uv lock` in server/

**server/pyproject.toml structure**:
```toml
[project]
name = "numina-server"
version = "1.0.0"
requires-python = ">=3.12"  # ← DeerFlow constraint from agent/
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "sqlalchemy>=2.0.36",
    "alembic>=1.14.0",
    "pydantic[email]>=2.10.0",
    "pydantic-settings>=2.7.0",
    "httpx>=0.28.0",
    "psycopg2-binary>=2.9.9",
]

[project.optional-dependencies]
backend = [
    "python-jose[cryptography]>=3.3.0",
    "bcrypt>=4.0.0",
    "python-multipart>=0.0.18",
    "apscheduler>=3.11.2",
    "altcha>=1.0.0",
    "filelock>=3.13.0",
    "pyyaml>=6.0.0",
    "webauthn>=2.7.1",
    "lunardate>=0.2.2",
    "user-agents>=2.2.0",
    "pdfplumber>=0.11",
    "redis>=5.0.0",
]
agent = [
    "langchain>=0.3.0",
    "anthropic>=0.40.0",
    "openai>=1.50.0",
    # langgraph, deerflow-harness (workspace member)
]
worker = [
    "apscheduler>=3.11.2",
    "cryptography>=44.0.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.9.0",
    "mypy>=1.13.0",
    "fakeredis>=2.0.0",
    "docker>=7.0.0",
    "playwright>=1.58.0",
]

[tool.uv.workspace]
members = ["apps/agent/vendor/deerflow-harness"]  # ← Note: workspace member path declared here, but vendor directory moved in Unit 4. Path resolves after Unit 4 completes.

[tool.pytest.ini_options]
pythonpath = ["."]  # ← Minimal: resolve packages.* from server root. Import mass rewrite handles app.* → apps.backend.app.*
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"  # ← Match requires-python
line-length = 88
```

**Verification**:
- `uv lock` succeeds in server/
- `uv sync --extra dev` succeeds
- scheduler_worker imports still resolve: `uv run python -c "from packages.core.settings import settings"`

### Unit 2: Move backend app code

**Goal**: Move backend/app/ and backend/alembic/ to server/apps/backend/.

**Files**:
- Move: backend/app/ → server/apps/backend/app/
- Move: backend/alembic/ → server/apps/backend/alembic/
- Move: backend/alembic.ini → server/apps/backend/alembic.ini
- Move: backend/Dockerfile → server/apps/backend/Dockerfile
- Move: backend/.env.example → server/apps/backend/.env.example
- Move: backend/app/utils/snowflake.py → server/packages/core/utils/snowflake.py
- Create: server/packages/core/utils/__init__.py
- Update: server/apps/backend/alembic.ini — `script_location = alembic` (relative path)
- Update: server/apps/backend/alembic/env.py — add `sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))` to resolve server root
- Update: all imports of `app.utils.snowflake` → `packages.core.utils.snowflake` (packages/db/models/ and backend files)

**Why**: packages/db/models/ imports SnowflakeGenerator from backend/app/utils/snowflake.py. After mass rewrite, that path becomes `apps.backend.app.utils.snowflake`, which packages cannot import (forbidden import direction: packages never import apps). Moving to packages/core/ makes it accessible to all packages and apps.

**Verification**:
- `cd server && uv run python -c "from packages.core.utils.snowflake import SnowflakeGenerator"` succeeds
- `cd server && uv run python -c "import apps.backend.app.main"` succeeds
- `cd server && uv run alembic -c apps/backend/alembic.ini check` passes

### Unit 3: Move backend tests

**Goal**: Move backend/tests/ to server/tests/backend/.

**Files**:
- Create: server/tests/__init__.py
- Create: server/tests/backend/__init__.py
- Move: backend/tests/ → server/tests/backend/
- Update: server/tests/backend/conftest.py — update paths if hardcoded

**Verification**: `cd server && uv run pytest tests/backend/ -v` — all tests pass.

### Unit 4: Move agent code

**Goal**: Move agent/ to server/apps/agent/.

**Files**:
- Move: agent/app/ → server/apps/agent/app/
- Move: agent/core/ → server/apps/agent/core/
- Move: agent/vendor/ → server/apps/agent/vendor/
- Move: agent/deerflow_config/ → server/apps/agent/deerflow_config/
- Move: agent/skills/ → server/apps/agent/skills/
- Move: agent/Dockerfile → server/apps/agent/Dockerfile
- Update: server/apps/agent/app/main.py — update deerflow_config paths if relative to agent root

**Verification**:
- `cd server && uv run python -c "import apps.agent.app.main"` succeeds
- DeerFlow imports resolve

### Unit 5: Move agent tests

**Goal**: Move agent tests to server/tests/agent/.

**Files**:
- Create: server/tests/agent/__init__.py
- Move: agent/tests/ → server/tests/agent/ (if exists)
- Update: conftest.py paths

**Verification**: `cd server && uv run pytest tests/agent/ -v` passes.

### Unit 6: Move scheduler_worker tests

**Goal**: Move scheduler-related tests to server/tests/scheduler_worker/.

**Files**:
- Create: server/tests/scheduler_worker/__init__.py
- Move: backend/tests/test_file_sync.py → server/tests/scheduler_worker/test_file_sync.py
- Move: backend/tests/test_jti_revocation.py → server/tests/scheduler_worker/ (if scheduler-related)

**Verification**: `cd server && uv run pytest tests/scheduler_worker/ -v` passes.

### Unit 7: Extract packages/domain/tasks/

**Goal**: Move AITask model to packages/db/models/, create packages/domain/tasks/ service.

**Files**:
- Move: backend/app/models/ai_task.py → server/packages/db/models/ai_task.py
- Create: server/packages/domain/tasks/__init__.py
- Create: server/packages/domain/tasks/service.py (create_task, update_task_status, get_task)
- Update: server/apps/backend/alembic/env.py — add AITask import:
  ```python
  # apps/backend/alembic/env.py
  from packages.db.models.ai_task import AITask  # added in Unit 7
  ```
- Update: backend imports for AITask → `from packages.domain.tasks.service import create_task`

**Verification**:
- `cd server && uv run pytest tests/backend/ -v` passes
- `uv run alembic -c apps/backend/alembic.ini check` passes

### Unit 8: Extract packages/domain/tenancy/

**Goal**: Move Family/User models to packages/db/models/, create packages/domain/tenancy/ services.

**Files**:
- Move: backend/app/models/family.py → server/packages/db/models/family.py
- Move: backend/app/models/user.py → server/packages/db/models/user.py
- Create: server/packages/domain/tenancy/__init__.py
- Create: server/packages/domain/tenancy/quota_service.py
- Create: server/packages/domain/tenancy/features_service.py
- Create: server/packages/domain/tenancy/family_service.py
- Create: server/packages/domain/tenancy/user_service.py
- Update: server/apps/backend/alembic/env.py — add Family/User imports:
  ```python
  # apps/backend/alembic/env.py
  from packages.db.models.family import Family  # added in Unit 8
  from packages.db.models.user import User      # added in Unit 8
  ```
- Update: backend imports for Family/User → `from packages.db.models.family import Family`, `from packages.db.models.user import User`

**Shim import resolution**: packages/domain/snapshot/service.py and packages/domain/notification/service.py currently shim to `from app.services.snapshot import ...` and `from app.services.notification.dispatcher import ...`. After Unit 2 moves backend to apps/backend/, these shims must be updated to `from apps.backend.app.services.snapshot import ...` etc. — or the underlying services extracted to packages/domain/ and shims deleted. Evaluate during Unit 8:
- If snapshot/notification services have no backend-only dependencies (no FastAPI Depends, no request context): extract to packages/domain/snapshot/ and packages/domain/notification/ and delete shims.
- If still coupled to backend models: update shim paths to `apps.backend.app.services.*` and defer full extraction to Phase 3.

**Verification**:
- `cd server && uv run pytest tests/backend/ -v` passes
- `uv run alembic -c apps/backend/alembic.ini check` passes
- `grep -r "from app\.services" server/packages/` returns empty (shims updated or deleted)

### Unit 9: Reorganize packages/security/

**Goal**: Split security into frontend_auth/ and service_auth/.

**Files**:
- Create: server/packages/security/frontend_auth/__init__.py
- Move: backend/app/auth/jwt_utils.py → server/packages/security/frontend_auth/jwt_service.py
- Move: backend/app/auth/webauthn.py → server/packages/security/frontend_auth/webauthn_service.py
- Create: server/packages/security/service_auth/__init__.py
- Move: backend/app/auth/ai_deps.py → server/packages/security/service_auth/agent_jwt.py (extract create_agent_token, verify_agent_token)
- Update: backend imports for auth functions → packages.security.frontend_auth.jwt_service, packages.security.service_auth.agent_jwt

**Verification**:
- `cd server && uv run pytest tests/backend/ -v` passes
- Auth endpoints work (login, token refresh, agent service-to-service)

### Unit 10: Update Docker Compose

**Goal**: Update docker-compose.yml to build backend and agent from server/.

**Files**:
- Modify: docker-compose.yml
  ```yaml
  backend:
    build:
      context: ./server
      dockerfile: apps/backend/Dockerfile
  agent:
    build:
      context: ./server
      dockerfile: apps/agent/Dockerfile
  ```
- Modify: server/apps/backend/Dockerfile — update COPY paths for server/ context
  ```dockerfile
  WORKDIR /app
  COPY pyproject.toml uv.lock ./
  RUN uv sync --frozen --no-dev --extra backend
  COPY apps/backend/ ./apps/backend/
  COPY packages/ ./packages/
  ```
- Modify: server/apps/agent/Dockerfile — similar pattern for agent

**Verification**:
- `docker compose build` succeeds for all services
- `docker compose up` starts all services healthy

### Unit 11: Delete root directories + update documentation

**Goal**: Remove backend/ and agent/ from repo root, update all docs.

**Files**:
- Delete: backend/ (entire directory)
- Delete: agent/ (entire directory)
- Update: root CLAUDE.md — remove backend/ and agent/ module entries, add server/ unified entry
  ```markdown
  | Module | CLAUDE.md | README |
  |--------|-----------|--------|
  | Server | [`server/CLAUDE.md`](./server/CLAUDE.md) | — |
  ```
- Create: server/CLAUDE.md (thin root: Quality Commands, Key Invariants, Don't Do)
  ```markdown
  # server/CLAUDE.md

  Module-specific guidance for the unified server monorepo.

  ## Quality Commands

  ```bash
  uv run ruff check packages/ apps/          # lint all code
  uv run ruff format packages/ apps/         # format touched files only
  uv run mypy packages/ apps/backend/app/    # type check backend
  uv run pytest tests/backend/ -v            # backend tests
  uv run pytest tests/agent/ -v              # agent tests
  uv run pytest tests/ -v                    # all tests
  uv run alembic -c apps/backend/alembic.ini upgrade head  # backend migrations
  ```

  ## Key Invariants

  - **packages ownership**: Only code used by ≥2 apps. Single-app code stays in apps.
  - **Import direction**: apps import packages, packages never import apps, apps never import apps.
  - **Incremental formatting**: Format only files you touch.
  ```
- Create: server/apps/backend/CLAUDE.md (backend-specific invariants)
- Create: server/apps/agent/CLAUDE.md (agent-specific DeerFlow guardrails)

**Verification**:
- `find . -name "pyproject.toml" | grep -v node_modules | grep -v .venv` returns only server/pyproject.toml
- `cd server && uv run pytest tests/ -v` passes (all 653+ tests)
- `docker compose up` works

## Import Adjustment Strategy

### Mass Rewrite Approach

Phase 2 rewrites all `from app.*` imports to fully qualified `from apps.<app_name>.app.*` paths. This eliminates PYTHONPATH ambiguity and makes import resolution explicit.

**Why mass rewrite over PYTHONPATH**:
- PYTHONPATH creates invisible ambiguity: `from app.models.user` could resolve to multiple locations
- Mass rewrite makes imports explicit and IDE-friendly
- Aligns with Python best practice: absolute imports from project root
- Prevents future import path conflicts as apps evolve

**Rewrite execution per unit**:

Each unit that moves files also rewrites imports in those files. Pattern:

```bash
# Unit 2: Move backend → rewrite backend imports
mv backend/app server/apps/backend/app
mv backend/alembic server/apps/backend/alembic
cd server
find apps/backend -name "*.py" | xargs sed -i 's/from app\./from apps.backend.app./g'
find apps/backend -name "*.py" | xargs sed -i 's/import app\./import apps.backend.app./g'

# Unit 4: Move agent → rewrite agent imports
mv agent/app server/apps/agent/app
mv agent/vendor server/apps/agent/vendor
cd server
find apps/agent -name "*.py" | xargs sed -i 's/from app\./from apps.agent.app./g'
find apps/agent -name "*.py" | xargs sed -i 's/import app\./import apps.agent.app./g'
```

**Exceptions** (no rewrite):
- Imports already using `apps.*` paths
- Imports using `packages.*` paths (already correct)
- Third-party imports (stdlib, FastAPI, SQLAlchemy)

**Verification after rewrite**:
```bash
# Verify no app.* imports remain in moved files
grep -r "from app\." server/apps/backend/ server/apps/agent/ | grep -v "__pycache__"
# Expected: empty (all rewritten)
```

### Cross-package Import Rules

Import direction remains unchanged from Phase 1:

```python
# ✅ Apps import packages
from packages.db.models.family import Family
from packages.domain.tasks.service import create_task

# ✅ Packages import other packages
from packages.db.session import SessionLocal
from packages.core.logging import get_logger

# ❌ Packages NEVER import apps
from apps.backend.app.models import ...  # forbidden

# ❌ Apps NEVER import other apps
from apps.agent.app.services import ...  # forbidden
```

**Enforcement**: ruff check after each unit flags forbidden imports.

## pyproject.toml Merge Strategy

### Dependency Classification

Merge backend, agent, scheduler_worker dependencies into unified server/pyproject.toml:

**Base dependencies** (all apps need):
```
fastapi, uvicorn[standard], sqlalchemy, alembic, pydantic[email], pydantic-settings, httpx, psycopg2-binary
```

**Backend extra** (backend-only):
```
python-jose[cryptography], bcrypt, python-multipart, apscheduler, altcha, filelock, pyyaml, webauthn, lunardate, user-agents, pdfplumber, redis
```

**Agent extra** (agent-only):
```
langchain, anthropic, openai, langgraph, deerflow-harness (workspace member)
```

**Worker extra** (scheduler_worker-only):
```
apscheduler, cryptography
```

**Dev dependencies** (all tests/lint/typecheck):
```
pytest, pytest-asyncio, pytest-cov, ruff, mypy, fakeredis, docker, playwright
```

### Lockfile Unification

**Before**: 4 lockfiles (backend/uv.lock, agent/uv.lock, scheduler_worker/uv.lock, root uv.lock if exists)

**After**: Single server/uv.lock

**Process**:
```bash
cd server
uv lock  # resolves all dependencies across extras
uv sync --extra dev  # install dev dependencies
uv sync --extra backend  # install backend runtime deps
uv sync --extra agent  # install agent runtime deps
```

**DeerFlow workspace member**: Declared in `[tool.uv.workspace]`, not in agent extra dependencies. Path: `"apps/agent/vendor/deerflow-harness"` (relative to server/).

### Orphan pyproject.toml Cleanup

Delete scheduler_worker orphan files (Phase 1 leftovers):
```bash
rm server/apps/scheduler_worker/pyproject.toml
rm server/apps/scheduler_worker/uv.lock
rm -rf server/apps/scheduler_worker/.venv
```

## Directory Structure Verification

### Pre-migration State

```
repo root/
├── backend/
│   ├── app/             # 3122 files
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .venv/
│   └── Dockerfile
├── agent/
│   ├── app/
│   ├── vendor/
│   ├── tests/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── .venv/
│   └── Dockerfile
├── server/
│   ├── apps/
│   │   ├── backend_api/    # stub only
│   │   └── scheduler_worker/
│   │       ├── pyproject.toml  # orphan
│   │       ├── uv.lock         # orphan
│   │       └── .venv/          # orphan
│   └── packages/
│       ├── core/
│       ├── db/
│       ├── domain/
│       ├── security/
│       └── storage/
└── docs/
```

### Post-migration State

```
repo root/
├── server/
│   ├── pyproject.toml     # ← single unified config
│   ├── uv.lock            # ← single lockfile
│   ├── apps/
│   │   ├── backend/
│   │   │   ├── app/       # moved from root backend/
│   │   │   ├── alembic/
│   │   │   ├── Dockerfile
│   │   │   └── .env.example
│   │   ├── agent/
│   │   │   ├── app/       # moved from root agent/
│   │   │   ├── vendor/    # DeerFlow harness
│   │   │   ├── deerflow_config/
│   │   │   ├── skills/
│   │   │   ├── Dockerfile
│   │   │   └── main.py
│   │   └── scheduler_worker/
│   │       ├── jobs/
│   │       ├── Dockerfile
│   │       └── main.py
│   ├── packages/
│   │   ├── core/
│   │   ├── db/
│   │   │   └── models/    # Family, User, AITask, SecurityAuditLog, ExchangeRate
│   │   ├── domain/
│   │   │   ├── audit/
│   │   │   ├── device/
│   │   │   ├── exchange_rate/
│   │   │   ├── notification/
│   │   │   ├── snapshot/
│   │   │   ├── tasks/     # new in Phase 2
│   │   │   └── tenancy/   # new in Phase 2
│   │   ├── security/
│   │   │   ├── frontend_auth/   # new in Phase 2
│   │   │   ├── service_auth/    # new in Phase 2
│   │   │   └── revoke_jti.py
│   │   └── storage/
│   └── tests/
│       ├── backend/
│       ├── agent/
│       └── scheduler_worker/
└── docs/
```

**Verification command**:
```bash
# Verify no orphan pyproject.toml
find . -name "pyproject.toml" | grep -v node_modules | grep -v .venv | grep -v server/
# Expected: empty

# Verify backend/ and agent/ deleted
ls backend/ agent/
# Expected: "No such file or directory"
```

## System-Wide Impact

- **Import resolution**: Backend and agent use `from apps.backend.app.*` / `from apps.agent.app.*` — resolved via mass rewrite, no PYTHONPATH hacks
- **Test discovery**: All tests under server/tests/ with `pythonpath = ["."]` (server root only)
- **Alembic migrations**: Each app runs migrations independently from its alembic/ directory
- **Docker builds**: All services share server/ build context, COPY packages/ for shared code
- **DeerFlow workspace**: apps/agent/vendor/deerflow-harness is uv workspace member (path declared in server/pyproject.toml, resolves after Unit 4)
- **Snowflake ID**: apps/backend/app/utils/snowflake.py accessible via `from apps.backend.app.utils.snowflake import SnowflakeGenerator`

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Circular imports during extraction | Medium | High | Enforce import direction: packages never import apps; ruff check after each unit |
| Pythonpath confusion in production | Medium | Medium | Document PYTHONPATH explicitly in Dockerfile; test runtime imports |
| DeerFlow vendor workspace breaks | Low | High | Preserve workspace member path; test agent startup after move |
| Alembic env.py import paths stale | Medium | High | Update env.py incrementally per model move; run `alembic check` after each unit |
| Test patch paths outdated | Medium | Medium | Update test mocks/patches to new canonical locations (packages.domain.tasks.service not app.services.ai_task) |
| Docker build context mismatch | Low | Medium | Verify COPY paths match server/ context; test docker compose build |
| Snowflake ID generator unreachable | Medium | High | Ensure pythonpath includes apps/backend so app.utils resolves from packages/db/models |

## Verification (Success Criteria)

- [ ] Backend starts without APScheduler in lifespan (Phase 1 already done)
- [ ] `server/pyproject.toml` and `server/uv.lock` are the only Python project files
  - **Expected**: `find . -name "pyproject.toml" | grep -v node_modules | grep -v .venv` returns only `./server/pyproject.toml`
- [ ] `cd server && uv run pytest tests/backend/ -v` passes
  - **Expected**: 653+ tests pass, 0 failures
- [ ] `cd server && uv run pytest tests/agent/ -v` passes
  - **Expected**: All agent tests pass (or "no tests collected" if agent has no tests)
- [ ] `cd server && uv run pytest tests/scheduler_worker/ -v` passes
  - **Expected**: All scheduler tests pass
- [ ] `cd server && uv run pytest tests/ -v` passes (all tests)
  - **Expected**: All tests pass, no import errors
- [ ] Backend starts: `cd server && uv run uvicorn apps.backend.app.main:app --reload`
  - **Expected**: Uvicorn starts on port 8000, no ImportError
- [ ] Agent starts: `cd server && uv run uvicorn apps.agent.app.main:app --reload`
  - **Expected**: Uvicorn starts on port 8001, DeerFlow harness loads
- [ ] Scheduler_worker health endpoint: `GET http://localhost:8002/health` returns 200
  - **Expected**: `{"status": "ok", "jobs": N}` where N ≥ 1
- [ ] `docker compose build` succeeds for all services
  - **Expected**: backend, agent, scheduler_worker images build without error
- [ ] `docker compose up` starts all services healthy
  - **Expected**: All containers reach healthy state, no restart loops
- [ ] Backend migrations apply: `cd server && uv run alembic -c apps/backend/alembic.ini upgrade head`
  - **Expected**: All 25+ migrations apply, no `OperationalError`
- [ ] No cross-app imports: `grep -r "from apps.backend.app" server/apps/agent/` returns nothing
  - **Expected**: Empty output
- [ ] No cross-app imports: `grep -r "from apps.agent.app" server/apps/backend/` returns nothing
  - **Expected**: Empty output
- [ ] No residual `from app.` imports: `grep -r "from app\." server/apps/backend/ server/apps/agent/` returns nothing
  - **Expected**: Empty output (all rewritten to `from apps.<name>.app.*`)
- [ ] Packages ownership: `grep -r "from app.models.family" server/packages/` returns nothing
  - **Expected**: Empty (Family in packages/db/models/)
- [ ] backend/ and agent/ directories deleted from repo root
  - **Expected**: `ls backend/ agent/` → "No such file or directory"

## Remaining Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Circular imports during extraction | Medium | High | Enforce import direction: packages never import apps; ruff check after each unit |
| Mass rewrite misses edge cases | Medium | Medium | Verify with grep after rewrite: `grep -r "from app\." apps/backend/ apps/agent/` must return empty |
| DeerFlow workspace path breaks after Unit 4 | Low | High | Workspace member path in pyproject.toml must match post-move location `apps/agent/vendor/deerflow-harness`; test `uv lock` after Unit 4 |
| Alembic env.py import paths stale | Medium | High | Update env.py incrementally per model move; run `alembic check` after each unit |
| Test patch paths outdated | Medium | Medium | Update test mocks/patches to new canonical locations (e.g. `apps.backend.app.services.ai_task` not `app.services.ai_task`) |
| Docker build context mismatch | Low | Medium | Verify COPY paths match server/ context; test `docker compose build` after Unit 10 |
| Snowflake ID generator unreachable | Medium | High | After mass rewrite, `from apps.backend.app.utils.snowflake import SnowflakeGenerator` must resolve from packages/db/models/ — verify with `uv run python -c "from packages.db.models.user import User"` |
| Python 3.12 compatibility regressions | Low | Medium | backend was developed on >=3.11; run full test suite after Unit 1 to catch any 3.12-specific issues before proceeding |
| DeerFlow vendor dependency conflicts | Low | High | DeerFlow pins specific LangChain/LangGraph versions; run `uv lock` after Unit 1 to verify no conflicts with backend deps |

## Follow-up Recommendations

These items are out of scope for Phase 2 but should be addressed in subsequent tasks:

### Phase 3: Internal Restructuring (Separate Task)
- Rename `routers/` → `api/`, `services/` → `core/` within apps/backend/ and apps/agent/
- Consolidate duplicate utility code between backend and agent
- Rationale: Phase 2 is a structural move; internal cleanup is a separate concern

### Phase 3: Agent Scheduler Activation (Separate Task)
- Activate dormant agent scheduler jobs (currently disabled in agent/app/scheduler.py)
- Wire agent jobs into scheduler_worker or create agent-specific scheduler
- Rationale: Requires production validation of Phase 2 migration first

### Migrate to src Layout (Optional, Long-term)
- Current: `server/apps/`, `server/packages/`
- Future: `server/src/numina/apps/`, `server/src/numina/packages/`
- Benefit: Standard Python packaging, cleaner namespace
- Cost: Another mass import rewrite; defer until Phase 2 is stable

### uv Workspace Expansion (Optional, Long-term)
- Current: Partial workspace (DeerFlow only)
- Future: Full workspace with each app as independent member
- Trigger: If apps need independent versioning or publishing
- Cost: Significantly more complex dependency management

### Alembic Consolidation (Optional)
- Current: Per-app independent migration paths
- Future: Single Alembic config with multiple heads
- Benefit: Atomic cross-app schema changes
- Cost: Couples app schema evolutions; only worthwhile if cross-app transactions needed

### CI/CD Pipeline Update (Required after Phase 2)
- Update CI to run tests from `server/` not `backend/` or `agent/`
- Update Docker build commands in CI to use `server/` context
- Update deployment scripts to use new startup commands

## Sources & References

- **Origin document**: [docs/brainstorms/2026-05-13-runtime-decomposition-scheduler-worker-requirements.md](docs/brainstorms/2026-05-13-runtime-decomposition-scheduler-worker-requirements.md)
- **Phase 1 workflow**: [docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md](docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md)
- **Phase 1 plan**: [docs/plans/2026-05-13-001-refactor-scheduler-worker-extraction-plan.md](docs/plans/2026-05-13-001-refactor-scheduler-worker-extraction-plan.md)
- **Session lifecycle pattern**: [docs/solutions/test-failures/audit-service-session-closure-test-isolation-2026-05-14.md](docs/solutions/test-failures/audit-service-session-closure-test-isolation-2026-05-14.md)
- **Monorepo tooling**: [docs/solutions/developer-experience/monorepo-module-level-lint-format-typecheck-2026-04-12.md](docs/solutions/developer-experience/monorepo-module-level-lint-format-typecheck-2026-04-12.md)
- **Backend CLAUDE.md**: backend/CLAUDE.md (current structure)
- **Agent CLAUDE.md**: agent/CLAUDE.md (DeerFlow guardrails)
- **Root CLAUDE.md**: CLAUDE.md (cross-cutting conventions)