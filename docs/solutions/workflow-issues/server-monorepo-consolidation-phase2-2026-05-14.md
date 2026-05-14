---
title: Phase 2 Server Monorepo Consolidation — agent + backend into server/
date: 2026-05-14
category: workflow-issues
module: server
problem_type: workflow_issue
component: development_workflow
severity: high
applies_when:
  - Two sibling FastAPI apps (agent/, backend/) need to be unified under a single server/ monorepo
  - Import paths, Docker configs, and CI references must be updated atomically across 700+ files
  - Dead rule-engine services predating a framework migration need to be removed during consolidation
  - A Vue 3 frontend feature is being added in the same phase
related_components:
  - tooling
  - documentation
tags: monorepo, refactoring, fastapi, deerflow, python, docker, vue3, import-paths, structural-migration
---

# Phase 2 Server Monorepo Consolidation — agent + backend into server/

## Context

The Numina project originally kept its FastAPI backend and DeerFlow agent as two sibling top-level directories:

```
numina/
├── backend/          # FastAPI app — app/ package
│   └── app/
├── agent/            # DeerFlow agent — apps/agent/ package
│   └── apps/agent/
└── frontend/
```

This split created friction as the project matured:

- Docker Compose referenced two separate build contexts, two separate dependency files, and two separate working directories.
- CI pipelines had to be duplicated or conditionally branched per app.
- The agent imported backend models via `sys.path` hacks or environment-variable injection rather than clean package imports.
- Dead rule-engine services (`disposal_advisor.py`, `aging_alert.py`) had accumulated in the agent with zero callers, predating the DeerFlow migration.
- Python version requirements diverged: backend required `>=3.11`, agent required `>=3.12` (DeerFlow hard constraint).

Phase 2 consolidated both apps under a single `server/` monorepo root, giving them a shared Python environment, a single Docker build context, and clean intra-server imports. The same phase also added a slash command palette to the Vue 3 frontend chat interface.

## Guidance

### Target structure

```
numina/
├── server/
│   ├── apps/
│   │   ├── backend/   # was backend/app/
│   │   └── agent/     # was agent/apps/agent/
│   ├── pyproject.toml
│   └── Dockerfile
└── frontend/
```

### Step-by-step pattern

**1. Resolve Python version conflicts first**

When merging two apps with different Python version requirements, adopt the stricter constraint in the unified `pyproject.toml`:

```toml
# server/pyproject.toml
[project]
requires-python = ">=3.12"   # agent's DeerFlow constraint wins
```

**2. Establish the new root**

Create `server/` with a single `pyproject.toml` that merges the dependencies of both former apps. Add a top-level `server/Dockerfile` with a single build context.

**3. Move source trees**

```bash
# backend: app/ → server/apps/backend/
mv backend/app server/apps/backend

# agent: apps/agent/ → server/apps/agent/
mv agent/apps/agent server/apps/agent
```

**4. Update all import paths**

Every `from app.` import in the backend becomes `from apps.backend.`. A project-wide sed pass covers most of it:

```bash
# macOS/BSD sed requires '' after -i; Linux sed accepts bare -i
# Inside server/apps/backend — update self-referential imports
find server/apps/backend -name "*.py" \
  -exec sed -i '' 's/^from app\./from apps.backend./' {} +
find server/apps/backend -name "*.py" \
  -exec sed -i '' 's/^import app\./import apps.backend./' {} +

# Agent imports that referenced the backend (^ anchor prevents rewriting
# string literals, comments, or docstrings that contain "from app.")
find server/apps/agent -name "*.py" \
  -exec sed -i '' 's/^from app\./from apps.backend./' {} +
```

Verify with a grep sweep after:

```bash
grep -rn "^from app\." server/   # should return nothing
grep -rn "^import app\." server/ # should return nothing
```

**5. Update DeerFlow workspace member path**

The agent's `vendor/deerflow-harness` is a uv workspace member. After moving to `server/apps/agent/`, the workspace member path must update relative to the new `server/pyproject.toml`:

```toml
# Before (relative to agent/pyproject.toml)
[tool.uv.workspace]
members = ["vendor/deerflow-harness"]

# After (relative to server/pyproject.toml)
[tool.uv.workspace]
members = ["apps/agent/vendor/deerflow-harness"]
```

**6. Update Docker Compose**

Before (two separate services with separate build contexts):

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    working_dir: /app

  agent:
    build:
      context: ./agent
      dockerfile: Dockerfile
    working_dir: /app/apps/agent
```

After (single build context, two services sharing one image — build once, reference twice):

```yaml
services:
  backend:
    build:
      context: ./server
      dockerfile: Dockerfile
    image: numina-server          # name the image so agent can reuse it
    working_dir: /server
    command: uvicorn apps.backend.main:app --host 0.0.0.0 --port 8000

  agent:
    image: numina-server          # reuses the image built above — no second build
    working_dir: /server
    command: python -m apps.agent.main
```

**7. Update CI references**

Replace path filters, working-directory overrides, and test commands that referenced `backend/` or `agent/` with `server/`:

```yaml
# Before
- name: Run backend tests
  working-directory: backend
  run: pytest app/

# After
- name: Run server tests
  working-directory: server
  run: pytest apps/backend/ apps/agent/
```

**8. Update Alembic**

`alembic.ini` and `env.py` reference the model import path:

```python
# Before
from app.models import Base

# After
from apps.backend.models import Base
```

Also update `script_location` in `alembic.ini` if the migrations folder moved.

### Dead code deletion pattern

Before deleting any service file, confirm zero imports across the entire codebase:

```bash
# Check Python imports
grep -r "disposal_advisor\|aging_alert" server/ --include="*.py"

# Check dynamic references (config keys, YAML, TOML)
grep -r "disposal_advisor\|aging_alert" . --include="*.yaml" --include="*.json" --include="*.toml"

# Check frontend (TypeScript/Vue)
grep -r "disposal_advisor\|aging_alert" frontend/ --include="*.ts" --include="*.vue"
```

Only delete when all sweeps return nothing. Remove the file, then re-run the grep to confirm no dangling references remain. Do not leave commented-out imports — remove them entirely.

### Architectural rule: packages never import from apps

If the consolidation also introduces a `server/packages/` layer (shared libraries used by ≥2 apps), enforce this import direction rule:

```
packages/ → no imports from apps/
apps/      → may import from packages/
apps/      → must NOT import from sibling apps/ directly
```

Cross-app communication (backend ↔ agent) must go through `packages/` or an explicit API boundary, never a direct `from apps.backend.X import Y` inside `apps/agent/`.

## Why This Matters

- **Single dependency lock**: One `pyproject.toml` eliminates version skew between the backend and agent. A library upgrade is one PR, not two.
- **Clean intra-server imports**: The agent can import backend models with a normal `from apps.backend.models import Asset` — no `sys.path` hacks, no environment variable injection.
- **Simpler Docker surface**: One build context means one layer cache, one image tag to track, and one `docker build` command in CI.
- **Dead code removal is safe and auditable**: The grep-before-delete pattern produces a clear paper trail. If a future developer wonders why a service was removed, the commit message and the zero-import evidence are self-documenting.
- **Reduced CI complexity**: Path-based change detection in CI can now use a single `server/**` filter instead of two separate filters that had to be kept in sync.

## When to Apply

- Two Python apps are always deployed together and share the same runtime environment.
- The apps have or will have direct import dependencies on each other's models or utilities.
- Docker Compose already runs both apps from the same `docker-compose.yml`.
- The team is small enough that a single monorepo PR review cycle is faster than coordinating cross-repo changes.
- You are about to add a shared library and don't want a third package to manage.

Do **not** apply if the apps have independent release cadences, different Python version requirements that cannot be reconciled, or are owned by separate teams with separate deployment pipelines.

## Examples

### Before/after directory structure

```
# Before
numina/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/
│   │   ├── routers/
│   │   └── services/
│   ├── requirements.txt
│   └── Dockerfile
├── agent/
│   ├── apps/
│   │   └── agent/
│   │       ├── main.py
│   │       ├── skills/
│   │       └── tools/
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/

# After
numina/
├── server/
│   ├── apps/
│   │   ├── backend/
│   │   │   ├── main.py
│   │   │   ├── models/
│   │   │   ├── routers/
│   │   │   └── services/
│   │   └── agent/
│   │       ├── main.py
│   │       ├── skills/
│   │       └── tools/
│   ├── pyproject.toml
│   └── Dockerfile
└── frontend/
```

### Key import path changes

```python
# Backend self-imports — before
from app.models.asset import Asset
from app.services.auth import get_current_user
from app.core.config import settings

# Backend self-imports — after
from apps.backend.models.asset import Asset
from apps.backend.services.auth import get_current_user
from apps.backend.core.config import settings

# Agent importing backend — before (required sys.path hack)
import sys; sys.path.insert(0, "/app")
from app.models.asset import Asset

# Agent importing backend — after (clean package import)
from apps.backend.models.asset import Asset
```

### Alembic env.py change

```python
# Before
from app.db.base import Base
target_metadata = Base.metadata

# After
from apps.backend.db.base import Base
target_metadata = Base.metadata
```

### Dead service deletion audit trail

```bash
# Confirm zero imports before deleting disposal_advisor.py
$ grep -r "disposal_advisor" server/ frontend/ --include="*.py" --include="*.ts"
(no output)

$ grep -r "disposal_advisor" . --include="*.yaml" --include="*.json"
(no output)

# Safe to delete
$ rm server/apps/agent/services/disposal_advisor.py
$ rm server/apps/agent/services/aging_alert.py
```

### `__init__.py` and package importability

Moving `app/` to `apps/backend/` requires `apps/__init__.py` and `apps/backend/__init__.py` to exist for the package to be importable as a regular package. If any tool (pytest, mypy, coverage) is configured with `rootdir` or `pythonpath` assumptions, missing `__init__.py` files will cause import errors that are hard to diagnose. Create them explicitly after the move:

```bash
touch server/apps/__init__.py
touch server/apps/backend/__init__.py
touch server/apps/agent/__init__.py
```

If the project uses implicit namespace packages (PEP 420) throughout, this is not required — but be consistent.

## Known Pitfalls (session history)

These failure patterns were encountered during the Phase 2 execution and are worth knowing before attempting a similar consolidation:

- **Plan file write failures during planning**: Write tool calls failed when plan content was too large. Fix: request a minimal plan with only headers, task items, and acceptance criteria.
- **Test patching paths break after extraction**: Tests that patched `app.auth.revoke_jti.SessionLocal` failed after the module moved. Fix: update test patches to target the new canonical location (`apps.backend.auth.revoke_jti.SessionLocal`). Note that `mock.patch` targets the location where the name is *used*, not where it's *defined* — if a consuming module does `from apps.backend.auth import revoke_jti`, the patch target is `apps.backend.consuming_module.revoke_jti`, not `apps.backend.auth.revoke_jti`.
- **Behavioral regression when rewriting jobs**: When rewriting background jobs for the new structure, behaviors from the original were accidentally dropped (query filters, exception handlers). Fix: read the original implementation from git history before rewriting (`git show HEAD~N:backend/app/scheduler.py`).
- **Session lifecycle in extracted services**: After extracting a service, calling `db.close()` in a `finally` block invalidated the shared test transaction. Fix: use the session-as-argument pattern with `flush()` instead of `commit()` when a caller session is provided.
- **Reverse dependency in shared packages**: A shared `packages/db/session.py` initially contained `from app.db import get_engine` — a reverse dependency that would prevent independent use. Fix: move `get_engine` to `packages/db/engine.py` with backend shims pointing to the new location.
- **Dockerfile Python version mismatch**: The new Dockerfile still referenced `python:3.11-slim` after the unified `pyproject.toml` adopted `>=3.12`. Fix: update to `python:3.12-slim` (or `3.13-slim`) and verify the build context paths match the new `server/` structure.

## Related

- `docs/solutions/workflow-issues/backend-module-extraction-workflow-2026-05-14.md` — companion guide covering the extraction workflow in detail: Strangler Fig sequencing, shim re-exports, import direction rules, job isolation patterns, and Alembic model migration
- `docs/solutions/test-failures/audit-service-session-closure-test-isolation-2026-05-14.md` — downstream pitfall: session closure bug exposed by the extraction, and the optional-session pattern fix
- `server/apps/backend/CLAUDE.md` — backend-specific dev commands and Snowflake ID serialization pattern
- `server/apps/agent/CLAUDE.md` — agent-specific dev commands and DeerFlow guardrails
