# AGENTS.md

This file provides guidance to AI coding agents working with code in this repository.

## Project Overview

Numina — 隐私优先、自托管的家庭资产可视化管理系统。帮助家庭跨成员跟踪、管理、可视化资产与负债，支持角色权限控制。

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| Server (Backend + Agent + Worker) | Python 3.12+ + FastAPI + SQLAlchemy + Alembic |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 + ECharts |
| Infrastructure | Docker Compose + Nginx |

> **Note:** 本仓库使用 `AGENTS.md`，不要创建 `CLAUDE.md` — 它会遮蔽同级 `AGENTS.md` 导致其失效。

---

## 协作底线

始终生效，优先级最高。

1. **结论先行。** 先给结论/结果，再给理由和步骤。短句白描，不空谈。
2. **禁止迎合。** 发现逻辑漏洞、反例或风险直接指出，不绕弯、不附和。
3. **未验证必须标注。** 没实际运行或核对过的内容标「未验证」；不编造数据、链接或结果。
4. **不做需求之外的事。** 不擅自加功能、抽象或错误处理。复杂任务先确认使用场景、验收标准和「本次不做什么」再动工。
5. **改局部先看上下游。** 修改前检查影响范围。同一问题基于同一前提连续两次修复失败 → 立刻停下查根因与底层假设，不再打补丁。
6. **遇到阻碍先自救。** 外部工具受限、网络报错、依赖缺失 → 先在可控范围内尝试替代方案。确实硬阻断时再清晰说明卡点与需要你介入的具体一步；禁止把任务原样推回。
7. **高风险操作必须谨慎。** 任何可能造成数据丢失、覆盖或外发的操作（哪怕只有一步）：写明影响范围 → 准备可回退方案 → 在副本上验证后再执行。

---

## 复杂任务工作流

> 按需触发：产品立项、开放性方案、架构选型、重要决策、多步骤拆解、返工复盘。简单任务跳过。

### 开工前

- 对齐场景与验收标准（最多问 3 个关键问题）
- 做减法：3 个以上功能点 → 挑 1-2 个主干，其余明确移出首版
- 拆细到可独立验证

### 方案期

- 开放性问题给 2-3 个差异化方案，标短期/长期取舍
- 改局部前查上下游影响
- 优先可逆方案
- 连续失败 → 强制熔断，回到根因

### 交付前

- 禁止迎合：逆向列出 2-3 个最易出错边界，优先验证
- 大白话交接：核心逻辑、已验证、未验证

### 收尾时

- 顺利 → 不强行复盘
- 有返工 → 简要复盘，提炼 1-2 条可执行检查项
- 若已有检查清单 → 主动调用

---

## Engineering Principles

These supersede general defaults in this repo:

- **Match user language.** Respond in the language used by the user in their prompt (e.g., Chinese if asked in Chinese, English if asked in English).
- **Never run dev servers from automated agents.** `uvicorn` and `pnpm dev` block indefinitely. Use `pytest` and `typecheck` for verification.

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
