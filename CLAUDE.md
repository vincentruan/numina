# CLAUDE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Behavioral Guidelines

These supersede general defaults in this repo:

- **State assumptions before coding.** If multiple interpretations exist, present them — don't pick silently. If a simpler approach exists, say so. If something is unclear, stop and ask.
- **Match user language.** Respond in the language used by the user in their prompt (e.g., Chinese if asked in Chinese, English if asked in English).
- **Surgical changes.** Touch only what the request requires. Don't refactor adjacent code, "improve" formatting, or delete pre-existing dead code. Match existing style, even if you'd do it differently. Do remove imports/variables that *your* changes left unused.
- **Goal-driven verification.** "Fix bug" → reproduce with a failing test, then make it pass. "Refactor X" → tests pass before and after. "Add validation" → invalid-input test first.
- **No work claimed done without evidence.** Run the module's quality commands (`pytest`, `typecheck`, `ruff check`) and confirm they pass. "Looks right" is not verification.
- **Never run dev servers from automated agents.** `uvicorn` and `pnpm dev` block indefinitely. Use `pytest` and `typecheck` for verification.

## Project Overview

Numina (Family Asset Visualization) is a privacy-first, self-hosted family asset visualization and management system. It helps families track, manage, and visualize their assets and liabilities across multiple members with role-based access control.

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

- **Incremental formatting** — format only files you touch. Do not run formatters on entire modules in a single commit.
- **No speculative code** — don't add features, abstractions, or error handling beyond what was asked. No abstractions for single-use code. No error handling for impossible scenarios.

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

Domain-specific solutions: see [`server/CLAUDE.md`](./server/CLAUDE.md) §Solutions, [`frontend/CLAUDE.md`](./frontend/CLAUDE.md) §Solutions, [`tests/CLAUDE.md`](./tests/CLAUDE.md) §Solutions.

## CodeGraph

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

### Rules of thumb

- **Trust codegraph results.** They come from a full AST parse. Do NOT re-verify with grep — slower, less accurate, wastes context.
- **Don't grep first** when looking up a symbol by name. `codegraph_search` returns kind + location + signature in one call.
- **Don't chain `codegraph_search` + `codegraph_node`** for context — `codegraph_context` is one call.
- **Don't loop `codegraph_node`** over many symbols — one `codegraph_explore` returns several symbols' source in a single capped call.
- **Index lag**: file watcher debounces ~500ms behind writes; don't re-query immediately after editing.

### If `.codegraph/` doesn't exist

The MCP server returns "not initialized." Ask: *"Want me to run `codegraph init -i` to build the index?"*

## Module Documentation

For module-specific dev commands, conventions, and patterns:

| Module | CLAUDE.md | README |
|--------|-----------|--------|
| Server workspace | [`server/CLAUDE.md`](./server/CLAUDE.md) | — |
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

See [`frontend/CLAUDE.md`](./frontend/CLAUDE.md) §Commands.

### Server

See [`server/CLAUDE.md`](./server/CLAUDE.md) §Quality Commands.

### Docker (all services)

```bash
docker-compose up -d          # Start everything (backend + agent + worker + frontend nginx)
docker-compose logs -f        # Follow logs
docker-compose up -d --build  # Rebuild after code changes
docker-compose down           # Stop all
# Access at http://localhost:8080
```

## Tests Directory (`tests/`)

E2E / visual regression / testing tools root directory. Python backend tests live in `server/tests/backend/` (see Module Documentation above).

```
tests/
├── e2e/              # Playwright specs (*.spec.ts) + Python smoke (smoke_test.py)
│   └── scripts/      # Shell runners (acceptance.sh, extended.sh …)
├── visual/           # Visual regression (visual.config.ts, visual-check.*)
├── lib/              # TS shared utilities (auth, fixtures, routes)
├── data/             # Python test data (factories/, scenarios/, seed_data.py)
├── fixtures/         # Static fixtures (openapi.snapshot.json)
├── tools/            # Standalone tools (screenshot/, page-agent/ config)
├── scripts/          # Helper scripts (update-openapi-snapshot.js)
├── reports/          # Historical audit reports (ui-audit-*.md)
├── docs/             # Test documentation (TEST_SPEC.md …)
├── playwright.config.ts / tsconfig.json / package.json
└── run-regression.sh # One-command regression entry point
```

**Rules:**
- New specs go in `e2e/`, shell scripts go in `e2e/scripts/`
- Screenshot outputs (`.png`) are `.gitignore`-excluded, not committed
- `reports/` holds historical audit reports only

