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

## Instruction Hierarchy

This repository keeps its agent instructions in `AGENTS.md` files: one at the repository root (this file) and one in each module directory. There is no second, parallel instruction system.

**Do not add a `CLAUDE.md`.** Where a `CLAUDE.md` exists alongside an `AGENTS.md` in the same directory, Claude Code loads only the `CLAUDE.md` and silently skips the `AGENTS.md` at that level.

**Precedence.** The closest module `AGENTS.md` wins over a parent `AGENTS.md`, which wins over this root file. Module files may restate or specialize root rules; where they conflict, the module file governs inside its own directory.

**Workflow contract.** Before editing:

1. Read this file, then load the `AGENTS.md` for the module you are about to change.
2. Keep changes minimal and scoped; do not refactor unrelated code.
3. Verify only with commands defined in the relevant `AGENTS.md` (module scope first).
4. In reports, state: changed files, verification commands run, and unresolved risks.

**Single source of truth.** Conventions belong in the `AGENTS.md` that owns their scope. Do not copy a rule into this root file when a module file should own it, and do not duplicate one rule across multiple files — pick an owner and reference it.

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
├── frontend/             # pnpm workspace — apps (main, child) + packages
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
| E2E / visual regression | [`tests/AGENTS.md`](./tests/AGENTS.md) §Commands |

Python backend tests live in `server/tests/backend/`.

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

### Rules of thumb

- **Trust codegraph results.** They come from a full AST parse. Do NOT re-verify with grep — slower, less accurate, wastes context.
- **Don't grep first** when looking up a symbol by name. `codegraph_search` returns kind + location + signature in one call.
- **Don't chain `codegraph_search` + `codegraph_node`** for context — `codegraph_context` is one call.
- **Don't loop `codegraph_node`** over many symbols — one `codegraph_explore` returns several symbols' source in a single capped call.
- **Index lag**: file watcher debounces ~500ms behind writes; don't re-query immediately after editing.

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

## Documentation Map

Module-specific dev commands, conventions, and patterns:

| Module | AGENTS.md | README |
|--------|-----------|--------|
| Server workspace | [`server/AGENTS.md`](./server/AGENTS.md) | — |
| Backend | [`server/apps/backend/AGENTS.md`](./server/apps/backend/AGENTS.md) | [`server/apps/backend/README.md`](./server/apps/backend/README.md) |
| Agent | [`server/apps/agent/AGENTS.md`](./server/apps/agent/AGENTS.md) | [`server/apps/agent/README.md`](./server/apps/agent/README.md) |
| Scheduler Worker | [`server/apps/scheduler_worker/AGENTS.md`](./server/apps/scheduler_worker/AGENTS.md) | [`server/apps/scheduler_worker/README.md`](./server/apps/scheduler_worker/README.md) |
| server/packages/core | [`server/packages/core/AGENTS.md`](./server/packages/core/AGENTS.md) | [`server/packages/core/README.md`](./server/packages/core/README.md) |
| server/packages/db | [`server/packages/db/AGENTS.md`](./server/packages/db/AGENTS.md) | [`server/packages/db/README.md`](./server/packages/db/README.md) |
| server/packages/domain | [`server/packages/domain/AGENTS.md`](./server/packages/domain/AGENTS.md) | [`server/packages/domain/README.md`](./server/packages/domain/README.md) |
| server/packages/security | [`server/packages/security/AGENTS.md`](./server/packages/security/AGENTS.md) | [`server/packages/security/README.md`](./server/packages/security/README.md) |
| server/packages/storage | [`server/packages/storage/AGENTS.md`](./server/packages/storage/AGENTS.md) | [`server/packages/storage/README.md`](./server/packages/storage/README.md) |
| Frontend workspace | [`frontend/AGENTS.md`](./frontend/AGENTS.md) | — |
| Frontend (main) | [`frontend/apps/main/AGENTS.md`](./frontend/apps/main/AGENTS.md) | [`frontend/apps/main/README.md`](./frontend/apps/main/README.md) |
| Frontend (child) | [`frontend/apps/child/AGENTS.md`](./frontend/apps/child/AGENTS.md) | — |
| Frontend packages | [`frontend/packages/AGENTS.md`](./frontend/packages/AGENTS.md) | — |
| Site | [`site/AGENTS.md`](./site/AGENTS.md) | — |
| Tests | [`tests/AGENTS.md`](./tests/AGENTS.md) | [`tests/README.md`](./tests/README.md) |

### Tests Directory (`tests/`)

E2E / visual regression / testing tools root directory. Python backend tests live in `server/tests/backend/`.

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
