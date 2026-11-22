# AGENTS.md

**Language:** Match the user's language in their prompt (e.g., Chinese if asked in Chinese, English if asked in English).

## Project Overview

Numina — privacy-first, self-hosted family asset visualization and management system. Helps families track, manage, and visualize assets and liabilities across members with role-based access control.

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| Server (Backend + Agent + Worker) | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Infrastructure | Docker Compose + Nginx |

---

## Collaboration Baselines

Always active, highest priority.

1. **Conclusion first.** State conclusion/result first, then reasoning and steps. Short sentences, no fluff.
2. **No sycophancy.** Point out logical flaws, counter-examples, or risks directly — don't hedge or agree just to please.
3. **Mark unverified claims.** Content not actually run or verified must be labeled "unverified"; never fabricate data, links, or results.
4. **Do nothing beyond scope.** Don't add features, abstractions, or error handling unprompted. For complex tasks, confirm use case, acceptance criteria, and "what we're NOT doing this time" before starting.
5. **Check upstream/downstream before changing.** Inspect impact scope before modifying. If the same fix fails twice on the same premise → stop immediately, investigate root cause and underlying assumptions, no more patching.
6. **Self-rescue on blockers.** External tool limits, network errors, missing deps → try alternatives within your control first. Only when truly blocked, clearly state the blocker and the specific step needing human intervention; never push the task back as-is.
7. **High-risk operations require caution.** Any operation that could cause data loss, overwrite, or external transmission (even a single step): state impact scope → prepare rollback plan → verify on a copy before executing.

---

## Complex Task Workflow

> Opt-in triggers: product planning, open-ended solutions, architecture decisions, important decisions, multi-step breakdowns, rework retrospectives. Skip for simple tasks.

### Before starting

- Align on scenario and acceptance criteria (ask at most 3 key questions)
- Subtract: 3+ feature points → pick 1-2 core ones, explicitly defer the rest
- Break down to independently verifiable units

### During planning

- For open questions, provide 2-3 differentiated options with short-term/long-term trade-offs
- Check upstream/downstream impact before changing local parts
- Prefer reversible solutions
- Consecutive failures → forced circuit-breaker, return to root cause

### Before delivery

- No sycophancy: reverse-list 2-3 most error-prone edge cases, verify them first
- Plain-language handoff: core logic, what's verified, what's not

### After completion

- Smooth sailing → no forced retrospective
- Rework occurred → brief retrospective, extract 1-2 actionable check items
- If a checklist already exists → proactively use it

---

## Repository Structure

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

`redirect_slashes=False` is set in `app/main.py`. All router root-path decorators must use `""` not `"/"`:
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

## Development Commands

This is a `pnpm` workspace (`pnpm-workspace.yaml`) for the frontend, and a `uv` workspace (single `pyproject.toml` at `server/`) for all Python apps. Use those tools — never `npm install` or `pip install` directly.

Module commands: [Frontend](./frontend/AGENTS.md) · [Server](./server/AGENTS.md)

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

Test commands: [Python](./server/AGENTS.md) · [Frontend](./frontend/AGENTS.md) · [Android](./frontend/apps/android/AGENTS.md) · [E2E](./tests/AGENTS.md)

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
| [`three-state-circuit-breaker`](./docs/solutions/architecture-patterns/three-state-circuit-breaker-with-cascade-retry-2026-05-20.md) | Three-state circuit breaker + multi-provider cascade retry |
| [`gateway-worker-responsibility-separation`](./docs/solutions/architecture-patterns/gateway-worker-responsibility-separation-2026-08-15.md) | Gateway/Worker responsibility separation |
| [`two-ai-apps-unified-dispatch`](./docs/solutions/architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md) | Unified dispatch for two AI apps |
| [`unified-data-root-path`](./docs/solutions/architecture-patterns/unified-data-root-path-management-2026-05-17.md) | DATA_ROOT unified path management |
| [`ai-task-page-leave-continuity`](./docs/solutions/architecture-patterns/ai-task-page-leave-continuity-2026-08-21.md) | AI task page-leave continuity |
| [`nginx-proxy-buffer`](./docs/solutions/integration-issues/nginx-proxy-buffer-sizing-frontend-assets.md) | Nginx proxy buffer sizing (large JS/CJK fonts) |
| [`nginx-stale-dns`](./docs/solutions/integration-issues/nginx-stale-dns-upstream-cache.md) | Nginx stale DNS cache causing 502 |
| [`production-deployment-config`](./docs/solutions/integration-issues/production-deployment-config-mismatches.md) | Production deployment config mismatches (CSP/pool/volume) |
| [`basehttpmiddleware-exception`](./docs/solutions/runtime-errors/basehttpmiddleware-exception-bypasses-fastapi-handlers.md) | BaseHTTPMiddleware exception bypasses FastAPI handlers |

Domain-specific solutions: see [`server/AGENTS.md`](./server/AGENTS.md) §Solutions, [`frontend/AGENTS.md`](./frontend/AGENTS.md) §Solutions, [`tests/AGENTS.md`](./tests/AGENTS.md) §Solutions.
