# CLAUDE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Behavioral Guidelines

These supersede general defaults in this repo:

- **State assumptions before coding.** If multiple interpretations of a request exist, present them — don't pick silently.
- **Surgical changes.** Touch only what the request requires. Don't refactor adjacent code, "improve" formatting, or delete pre-existing dead code. Do remove imports/variables that *your* changes left unused.
- **Goal-driven verification.** "Fix bug" → reproduce with a failing test, then make it pass. "Refactor X" → tests pass before and after. "Add validation" → invalid-input test first.
- **No work claimed done without evidence.** Run the module's quality commands (`pytest`, `typecheck`, `ruff check`) and confirm they pass. "Looks right" is not verification.
- **Never run dev servers from automated agents.** `uvicorn` and `pnpm dev` block indefinitely. Use `pytest` and `typecheck` for verification.

## Project Overview

Numina (家庭资产可视化) is a privacy-first, self-hosted family asset visualization and management system. It helps families track, manage, and visualize their assets and liabilities across multiple members with role-based access control.

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| Server (Backend + Agent + Worker) | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Infrastructure | Docker Compose + Nginx |

## Known Pitfalls

### URL Style — No Trailing Slash, No Redirects

All API endpoints must respond with 200 directly — no 307 redirects.

**Rule:** `redirect_slashes=False` is set in `app/main.py`. All router root-path decorators must use `""` not `"/"`:
```python
# ✅ Correct — hits 200 directly
@router.get("")
@router.post("")

# ❌ Wrong — FastAPI issues 307 redirect, breaks HTTPS behind nginx
@router.get("/")
@router.post("/")
```

Applies to every router with root-path endpoints. Frontend calls must also omit trailing slashes.

### Bigint Serialization

JS loses precision on integers > 2⁵³. All `bigint` fields (IDs, large amounts, etc.) **must be serialized as strings in API responses** and typed as `string` in TypeScript.

**Implementation:** All response schemas use `SnowflakeBase` which automatically converts `int` fields named `id` or ending in `_id` to `str` during JSON serialization. See `server/apps/backend/CLAUDE.md` §Snowflake ID Serialization for the full pattern and `SnowflakeBase` usage.

### API Return Code Conventions

- **Auth endpoints return 200** — `register`, `login`, `join-family` all return `TokenResponse` with status 200, not 201.
- **Asset/Liability POST endpoints return 201** — explicit `status_code=201` on router decorators.
- **`TokenResponse` does not include `user`** — frontend must call `/auth/me` after login to get user info.
- **Dashboard allocation** returns `{ items: [...], total: float }`, not a flat list.
- **Dashboard trend** returns `{ points: [...] }`, not a flat list.

## Cross-Cutting Conventions

- **i18n required for all UI strings** — every user-facing string (toasts, dialogs, labels, status text) must be defined in `src/i18n/locales/zh-CN.ts` and referenced via `t('key')`. Never hard-code Chinese strings directly in `.vue` files or `.ts` logic — not even in template ternaries. Applies to both `frontend/apps/main` and `frontend/apps/child`.
- **Emoji convention** — all toast/error strings must include an emoji prefix. See `frontend/apps/main/CLAUDE.md` for the full table.
- **Error messages in Chinese** — backend HTTP exceptions use Chinese detail strings: `raise HTTPException(status_code=404, detail="资产不存在")`
- **Incremental formatting** — format only files you touch. Do not run formatters on entire modules in a single commit.
- **No speculative code** — don't add features, abstractions, or error handling beyond what was asked.
- **Past solutions** — `docs/solutions/` contains documented fixes for recurring problems. Check before debugging known issue categories. Subdirectories: `architecture-patterns/` (e.g. MCP chat adapter, tenant isolation, three-state circuit breaker), `best-practices/` (e.g. Redis fail-fast strategy, cache key granularity, Pydantic validation), `workflow-issues/` (e.g. backend module extraction workflow), `integration-issues/` (e.g. DeerFlow silent fallback), `test-failures/`, `ui-bugs/`, `developer-experience/`.

## CodeGraph

Prefer CodeGraph MCP (`codegraph_*` tools) over grep/read for structural code queries. See [`codegraph-structural-code-search-2026-06-10.md`](./docs/solutions/developer-experience/codegraph-structural-code-search-2026-06-10.md) for setup and edge cases.

| Query | Tool | Example |
|-------|------|---------|
| "Where is X defined?" | `codegraph_search` | Find symbol by name |
| "What calls Y?" | `codegraph_callers` | Trace upstream deps |
| "How does X reach Y?" | `codegraph_trace` | Full call path in one call |
| "What breaks if Z changes?" | `codegraph_impact` | Change impact analysis |
| "Context for a task" | `codegraph_context` | Search + callers + callees |
| "Multiple symbols' source" | `codegraph_explore` | Batch retrieval |

## Module Documentation

For module-specific dev commands, conventions, and patterns:

| Module | CLAUDE.md | README |
|--------|-----------|--------|
| Backend | [`server/apps/backend/CLAUDE.md`](./server/apps/backend/CLAUDE.md) | [`server/apps/backend/README.md`](./server/apps/backend/README.md) |
| Agent | [`server/apps/agent/CLAUDE.md`](./server/apps/agent/CLAUDE.md) | [`server/apps/agent/README.md`](./server/apps/agent/README.md) |
| Scheduler Worker | [`server/apps/scheduler_worker/CLAUDE.md`](./server/apps/scheduler_worker/CLAUDE.md) | [`server/apps/scheduler_worker/README.md`](./server/apps/scheduler_worker/README.md) |
| server/packages/core | [`server/packages/core/CLAUDE.md`](./server/packages/core/CLAUDE.md) | [`server/packages/core/README.md`](./server/packages/core/README.md) |
| server/packages/db | [`server/packages/db/CLAUDE.md`](./server/packages/db/CLAUDE.md) | [`server/packages/db/README.md`](./server/packages/db/README.md) |
| server/packages/domain | [`server/packages/domain/CLAUDE.md`](./server/packages/domain/CLAUDE.md) | [`server/packages/domain/README.md`](./server/packages/domain/README.md) |
| server/packages/security | [`server/packages/security/CLAUDE.md`](./server/packages/security/CLAUDE.md) | [`server/packages/security/README.md`](./server/packages/security/README.md) |
| server/packages/storage | [`server/packages/storage/CLAUDE.md`](./server/packages/storage/CLAUDE.md) | [`server/packages/storage/README.md`](./server/packages/storage/README.md) |
| Frontend (main) | [`frontend/apps/main/CLAUDE.md`](./frontend/apps/main/CLAUDE.md) | [`frontend/README.md`](./frontend/README.md) |
| Frontend (child) | [`frontend/apps/child/CLAUDE.md`](./frontend/apps/child/CLAUDE.md) | — |
| Frontend packages | [`frontend/packages/CLAUDE.md`](./frontend/packages/CLAUDE.md) | — |
| Site | [`site/CLAUDE.md`](./site/CLAUDE.md) | — |

## Development Commands

This is a `pnpm` workspace (`pnpm-workspace.yaml`) for the frontend, and a `uv` workspace (single `pyproject.toml` at `server/`) for all Python apps. Use those tools — never `npm install` or `pip install` directly.

### Frontend

```bash
# Main app (adult-facing) — http://localhost:5173
cd frontend/apps/main
pnpm dev --host 0.0.0.0  # Vite dev server, 支持局域网访问
pnpm typecheck           # vue-tsc --noEmit
pnpm test:run            # vitest run (no watch)
pnpm lint                # ESLint
pnpm build               # Production build

# Child app — http://localhost:5174
cd frontend/apps/child
pnpm dev --host 0.0.0.0
pnpm typecheck
pnpm test:run

# Workspace-wide (from frontend/)
pnpm -r typecheck  # type-check all apps + packages
pnpm -r test:run   # run vitest in every workspace
```

### Server (backend, agent, scheduler_worker — single uv workspace)

Run from `server/`:

```bash
# Backend API (监听 0.0.0.0 支持局域网访问)
uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000

# AI agent
uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001

# Scheduler worker
uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --reload --port 8002

# Tests + lint + typecheck (scope to a path)
uv run pytest apps/backend/tests/ -v
uv run ruff check apps/backend/
uv run mypy apps/backend/

# Migrations (backend only)
cd apps/backend
uv run alembic upgrade head        # apply all pending
uv run alembic revision --autogenerate -m "description"
uv run alembic downgrade -1
```

### Docker (all services)

```bash
docker-compose up -d          # Start everything (backend + agent + worker + frontend nginx)
docker-compose logs -f        # Follow logs
docker-compose up -d --build  # Rebuild after code changes
docker-compose down           # Stop all
# Access at http://localhost:8080
```

