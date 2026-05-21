# CLAUDE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Behavioral Guidelines

### 1. Think Before Coding

Before implementing, state assumptions explicitly. If multiple interpretations exist, present them — don't pick silently. If a simpler approach exists, say so. If something is unclear, stop and ask.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

Touch only what you must. When editing existing code:

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Remove imports/variables/functions that **your** changes made unused, but leave pre-existing dead code alone.

Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

Transform tasks into verifiable goals before starting:

- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Add validation" → write tests for invalid inputs, then make them pass.
- "Refactor X" → ensure tests pass before and after.

For multi-step tasks, state a brief plan with explicit verify steps **before coding**.

### 5. Verify Before Claiming Done

Run the module's quality commands and confirm they pass. Do not report a task complete without evidence. "Looks right" is not verification.

## Project Overview

Numina (家庭资产可视化) is a privacy-first, self-hosted family asset visualization and management system. It helps families track, manage, and visualize their assets and liabilities across multiple members with role-based access control.

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| Server (Backend + Agent + Worker) | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Infrastructure | Docker Compose + Nginx |

## Known Pitfalls

### Never Run Dev Servers from Automated Agents

Do NOT run `uvicorn`, `npm run dev`, or any long-running process from an agent. These block indefinitely. Use `pytest` and `typecheck` for verification instead.

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
- **Past solutions** — `docs/solutions/` contains documented fixes for recurring problems. Check before debugging known issue categories. Subdirectories: `architecture-patterns/` (e.g. MCP chat adapter, tenant isolation), `best-practices/` (e.g. Redis fail-fast strategy, cache key granularity, Pydantic validation), `workflow-issues/` (e.g. backend module extraction workflow), `integration-issues/` (e.g. DeerFlow silent fallback), `test-failures/`, `ui-bugs/`, `developer-experience/`.

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

### Frontend (Main App)

```bash
cd frontend/apps/main
npm run dev          # Dev server — http://localhost:5173 (hot reload)
npm run test:run     # Run tests once
npm run typecheck    # Type check before push
```

### Backend

```bash
cd server/apps/backend
uv run uvicorn app.main:app --reload --port 8000  # Dev server (hot reload)
uv run pytest tests/ -v                            # Run tests
uv run alembic upgrade head                        # Apply migrations
uv run alembic downgrade -1                        # Rollback last migration
```

### Docker (All Services)

```bash
docker-compose up -d          # Start all services
docker-compose logs -f        # View logs
docker-compose up -d --build  # Rebuild after code changes
docker-compose down           # Stop all services
# Access at http://localhost:8080
```
