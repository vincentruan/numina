# AGENTS.md

This file provides guidance to AI coding agents working with code in this repository.

## Project Overview

Numina (Family Asset Visualization) is a privacy-first, self-hosted family asset visualization and management system. It helps families track, manage, and visualize their assets and liabilities across multiple members with role-based access control.

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| Server (Backend + Agent + Worker) | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Infrastructure | Docker Compose + Nginx |

**Note:** This repo uses `AGENTS.md` files, not `CLAUDE.md`. Do not add a `CLAUDE.md` — it would shadow the `AGENTS.md` at the same level and silently skip it.

## Engineering Principles

These supersede general defaults in this repo:

- **State assumptions before coding.** If multiple interpretations exist, present them — don't pick silently. If a simpler approach exists, say so. If something is unclear, stop and ask.
- **Match user language.** Respond in the language used by the user in their prompt (e.g., Chinese if asked in Chinese, English if asked in English).
- **Surgical changes.** Touch only what the request requires. Don't refactor adjacent code, "improve" formatting, or delete pre-existing dead code. Match existing style, even if you'd do it differently. Do remove imports/variables that *your* changes left unused.
- **Goal-driven verification.** "Fix bug" → reproduce with a failing test, then make it pass. "Refactor X" → tests pass before and after. "Add validation" → invalid-input test first.
- **No work claimed done without evidence.** Run the module's quality commands (`pytest`, `typecheck`, `ruff check`) and confirm they pass. "Looks right" is not verification.
- **Never run dev servers from automated agents.** `uvicorn` and `pnpm dev` block indefinitely. Use `pytest` and `typecheck` for verification.

## Repository Structure

Repository layout — two workspaces plus supporting trees:

```
numina/
├── server/               # uv workspace — apps (backend, agent, scheduler_worker) + packages
├── frontend/             # pnpm workspace — apps (main, child, android) + packages
└── site/  tests/  docs/  # marketing site · E2E/visual tests · architecture, specs, solutions
```

## Cross-Cutting Conventions

Rules in this section apply to every module. Module files should reference them rather than restating them — root owns these rules.

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

**Implementation:** All response schemas use `SnowflakeBase` which automatically converts `int` fields named `id` or ending in `_id` to `str` during JSON serialization. See `server/apps/backend/AGENTS.md` §Snowflake ID Serialization for the full pattern and `SnowflakeBase` usage.

### API Return Code Conventions

- **Auth endpoints return 200** — `register`, `login`, `join-family` all return `TokenResponse` with status 200, not 201.
- **Asset/Liability POST endpoints return 201** — explicit `status_code=201` on router decorators.
- **`TokenResponse` does not include `user`** — frontend must call `/auth/me` after login to get user info.
- **Dashboard allocation** returns `{ items: [...], total: float }`, not a flat list.
- **Dashboard trend** returns `{ points: [...] }`, not a flat list.

### Incremental Formatting

Format only files you touch. Do not run formatters on entire modules in a single commit.

### No Speculative Code

Don't add features, abstractions, or error handling beyond what was asked. No abstractions for single-use code. No error handling for impossible scenarios.

## Development Commands

This is a `pnpm` workspace (`pnpm-workspace.yaml`) for the frontend, and a `uv` workspace (single `pyproject.toml` at `server/`) for all Python apps. Use those tools — never `npm install` or `pip install` directly.

### Frontend

See [`frontend/AGENTS.md`](./frontend/AGENTS.md) §Commands.

### Server

See [`server/AGENTS.md`](./server/AGENTS.md) §Quality Commands.

### Docker (all services)

```bash
docker-compose up -d          # Start everything (backend + agent + worker + frontend nginx)
docker-compose logs -f        # Follow logs
docker-compose up -d --build  # Rebuild after code changes
docker-compose down           # Stop all
# Access at http://localhost:8080
```

## Testing and Verification

Verification is scoped to the module you changed. Run the commands its `AGENTS.md` defines before reporting completion, and state which commands you ran.

| Area | Commands defined in |
|------|---------------------|
| Python apps + packages | [`server/AGENTS.md`](./server/AGENTS.md) §Quality Commands |
| Frontend | [`frontend/AGENTS.md`](./frontend/AGENTS.md) §Commands |
| Android shell | [`frontend/apps/android/AGENTS.md`](./frontend/apps/android/AGENTS.md) §Commands |
| E2E / visual regression | [`tests/AGENTS.md`](./tests/AGENTS.md) §Commands |

Test locations: Python backend → `server/tests/backend/`, E2E/visual → `tests/e2e/` (specs) and `tests/visual/` (screenshots). New E2E specs go in `tests/e2e/`, shell runners in `tests/e2e/scripts/`.

## Structural Code Search

CodeGraph is a tree-sitter-parsed knowledge graph of every symbol, edge, and file in this project. Reads are sub-millisecond and return structural information grep cannot. Prefer `codegraph_*` tools over grep/read for structural queries. See [`codegraph-structural-code-search-2026-06-10.md`](./docs/solutions/developer-experience/codegraph-structural-code-search-2026-06-10.md) for setup and edge cases.

| Query | Tool |
|-------|------|
| "Where is X defined?" / "Find symbol named X" | `codegraph_search` |
| "What calls function Y?" | `codegraph_callers` |
| "What does Y call?" | `codegraph_callees` |
| "How does X reach Y? / trace the flow" | `codegraph_trace` (one call = whole path, incl. dynamic hops) |
| "What breaks if Z changes?" | `codegraph_impact` |
| "Show me Y's signature / source / docstring" | `codegraph_node` |
| "Context for a task/area" | `codegraph_context` |
| "Multiple symbols' source at once" | `codegraph_explore` |
| "What files exist under path/" | `codegraph_files` |
| "Is the index healthy?" | `codegraph_status` |

These tools are provided by a CodeGraph MCP server. If your agent has no MCP support or the server is not configured, fall back to `grep`/`read` for the same questions.

### If `.codegraph/` doesn't exist

The MCP server returns "not initialized." Ask: *"Want me to run `codegraph init -i` to build the index?"*

## Solutions (Lessons Learned)

`docs/solutions/` contains verified solutions and best practices. Check relevant docs before debugging or implementation.

| Doc | Topic |
|-----|-------|
| [`three-state-circuit-breaker`](./docs/solutions/architecture-patterns/three-state-circuit-breaker-with-cascade-retry-2026-05-20.md) | 三态熔断器 + 多 Provider 级联重试 |
| [`gateway-worker-responsibility-separation`](./docs/solutions/architecture-patterns/gateway-worker-responsibility-separation-2026-08-15.md) | Gateway/Worker 职责分离 |
| [`two-ai-apps-unified-dispatch`](./docs/solutions/architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md) | 双 AI 应用统一 dispatch |
| [`unified-data-root-path`](./docs/solutions/architecture-patterns/unified-data-root-path-management-2026-05-17.md) | DATA_ROOT 统一路径管理 |
| [`ai-task-page-leave-continuity`](./docs/solutions/architecture-patterns/ai-task-page-leave-continuity-2026-08-21.md) | AI 任务页面离开连续性 |
| [`nginx-proxy-buffer`](./docs/solutions/integration-issues/nginx-proxy-buffer-sizing-frontend-assets.md) | Nginx 代理缓冲区 (大 JS/CJK 字体) |
| [`nginx-stale-dns`](./docs/solutions/integration-issues/nginx-stale-dns-upstream-cache.md) | Nginx DNS 缓存过期导致 502 |
| [`production-deployment-config`](./docs/solutions/integration-issues/production-deployment-config-mismatches.md) | 生产部署配置不匹配 (CSP/pool/volume) |
| [`basehttpmiddleware-exception`](./docs/solutions/runtime-errors/basehttpmiddleware-exception-bypasses-fastapi-handlers.md) | BaseHTTPMiddleware 异常绕过 FastAPI 处理器 |

Domain-specific solutions: see [`server/AGENTS.md`](./server/AGENTS.md) §Solutions, [`frontend/AGENTS.md`](./frontend/AGENTS.md) §Solutions, [`tests/AGENTS.md`](./tests/AGENTS.md) §Solutions.
