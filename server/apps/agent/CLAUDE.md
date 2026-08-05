# agent/CLAUDE.md

Module-specific guidance for the Python FastAPI AI agent microservice.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run from `server/` (the uv workspace root):

```bash
uv run ruff check apps/agent/              # lint
uv run ruff check apps/agent/ --fix        # lint + auto-fix
uv run ruff format apps/agent/             # format (only files you touch)
uv run mypy apps/agent/ --exclude vendor   # type check
uv run pytest tests/agent/ -v              # run all agent tests (canonical root; auto-collected by `testpaths=["tests"]`)
uv run pytest tests/agent/ -v -k "keyword" # run tests matching keyword
```

> **Test root:** The canonical agent test root is `tests/agent/` (mirrors `tests/backend/`; auto-collected by bare `pytest` via `testpaths = ["tests"]`). The legacy `apps/agent/tests/` directory still exists with **stale, partially-failing** tests (`test_branch_endpoint.py`, `test_threads_router.py` — 404 on thread lookup) and is **not** collected by default — do not add new tests there. When in doubt, run `uv run pytest tests/ -v` to run the full server suite.

## Tooling

- **ruff:** lint + format. Config in `pyproject.toml` under `[tool.ruff]`. Rules: E, F, I, UP, B, SIM. E501 is ignored — no line length enforcement.
- **mypy:** type checker. `ignore_missing_imports = true` is intentional — LangChain and DeerFlow stubs are incomplete. Use `# type: ignore[<code>]` with an inline comment explaining why when suppressing.
- **pytest + pytest-asyncio:** async test runner. `asyncio_mode = "auto"` is set in `pyproject.toml`.
- **uv:** package manager. `deerflow-harness` is a workspace member from `vendor/deerflow-harness/` — always installed from local source, never from PyPI.

## Key Invariants (Risk Control)

These must hold in every code path — never bypass them:

1. **PII redaction:** Always call `pii_redactor.redact()` on `FamilyContext` before passing data to any LLM call or writing to logs. This produces a `RedactedContext`.
2. **Policy guard:** All agent requests must pass through `policy_guard.check()`. Never skip or short-circuit it.
3. **Audit logging:** Every agent run emits an audit event via `audit_logger.log_call()` in the `finally` block of each per-app runner in `runtime/worker.py` (e.g. `_run_numina_agent`). Both success and error paths are covered — the `finally` placement guarantees it.
4. **DeerFlow-only execution:** All multi-step agent orchestration goes through `DeerFlowAdapter.typed_stream_dispatch` (in `services/deerflow_adapter/`). Never implement a custom runtime, tool registry, skill loader, memory manager, orchestrator, or workflow engine. Lightweight single-call LLM paths (`suggest`, `input_polish`) use `core/llm.py` directly — these are explicitly exempt (no DeerFlow dispatch needed for one-shot calls).

## DeerFlow 问题排查指南

遇到以下问题时，参考对应的 solution 文档：

| 问题场景 | 参考文档 |
|---------|---------|
| DeerFlow stream 类型不匹配 / SSE 安全问题 | [`deerflow-stream-type-mismatch`](../../../../docs/solutions/integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md) |
| GLM5 thinking provider endpoint 错误 | [`deerflow-glm5-thinking-mismatch`](../../../../docs/solutions/integration-issues/deerflow-glm5-thinking-provider-endpoint-mismatch-2026-05-16.md) |
| DeerFlow harness 静默 fallback / 并发问题 | [`deerflow-harness-fixes`](../../../../docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md) |
| MCP tools 加载失败 / 跨线程 asyncio.Lock 死锁 | [`user-feedback-branch-fixes`](../../../../docs/solutions/ui-bugs/user-feedback-branch-multi-domain-fixes-2026-08-05.md) (Bug 3) |
| 会话标题显示 thinking-block 原始内容 | 同上 (Bug 4) |
| stream 提前关闭 / 连接中断 | [`stream-closure-fix`](../../../../docs/solutions/integration-issues/stream-closure-fix-2026-06-15.md) |
| 多 provider 熔断 / cascade retry | [`three-state-circuit-breaker`](../../../../docs/solutions/architecture-patterns/three-state-circuit-breaker-with-cascade-retry-2026-05-20.md) |
| MCP caller-bound principal / tenant isolation | [`mcp-caller-bound-principal`](../../../../docs/solutions/architecture-patterns/mcp-caller-bound-principal-2026-05-31.md) |
| MCP chat adapter 架构 | [`mcp-chat-adapter-architecture`](../../../../docs/solutions/architecture-patterns/mcp-chat-adapter-architecture-2026-05-21.md) |
| 多 app dispatch (stream_run) | [`two-ai-apps-unified-dispatch`](../../../../docs/solutions/architecture-patterns/two-ai-apps-unified-dispatch-stream-run.md) |

## Cross-Cutting Invariants

These apply across the whole server monorepo. An agent loading only this file must still know them.

1. **Router decorator style** — see root [CLAUDE.md](../../CLAUDE.md) §URL Style for the `redirect_slashes=False` rule
2. **Snowflake ID serialization** — if this service ever returns IDs in API responses, use `SnowflakeBase` not plain `BaseModel`. JS loses precision on integers > 2⁵³. See `server/apps/backend/CLAUDE.md` for the full pattern.
3. **Auth return codes** — the agent uses `X-Agent-Token` (shared secret), not JWT auth endpoints. If auth-style endpoints are ever added, they return `200` not `201`.
4. **Import direction** — this service must never import from `apps/backend` or `apps/scheduler_worker` directly. All backend data access goes through `core/backend_client.py` (HTTP). Use `packages/` for shared logic.

## DeerFlow Execution

DeerFlow is the mandatory multi-step execution path — all dispatch goes through `DeerFlowAdapter` (`services/deerflow_adapter/`). Do not build a parallel runtime, tool registry, skill loader, memory manager, or workflow engine; extend the adapter instead. Lightweight single-call LLM paths (`suggest`, `input_polish`, title generation) use `core/llm.py` directly and intentionally bypass DeerFlow.

DeerFlow credentials are **not** env-based — `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` are unused. Each family's decrypted `api_key` + `ai_provider` come from the backend's `/api/v1/internal/ai/config` endpoint (Fernet-decrypted with `AI_ENCRYPTION_KEY`). Per-family `DeerFlowClient` instances are LRU-cached (max 100) in `family_adapter_cache.py`, each with a temp `config.yaml` + `extensions_config.json` generated from `deerflow_config/base/config.yaml`. Cache is invalidated via `POST /internal/cache/invalidate/{family_id}`.

### Adapter package layout

```
services/deerflow_adapter/
├── adapter.py              # DeerFlowAdapter — typed_stream_dispatch + raw_stream_dispatch (ThreadPoolExecutor bridge)
├── family_adapter_cache.py # LRU cache (100 families) of per-family DeerFlowClient + temp config generation
├── client_factory.py       # builds DeerFlowClient from generated config
├── active_skill_context.py # ContextVar holding the active skill name (drives tool filtering)
├── memory_config_bridge.py # bridges DeerMem memory config per family
├── original_user_content_context.py  # ContextVar preserving original user content through middleware
├── sync_tool_patch.py      # monkey-patches DeerFlow harness: sync wrapping, ContextVar propagation, MCP proxy, active-skill tool filter
└── exceptions.py
```

Business code (routers, worker) calls adapter methods — never instantiates `DeerFlowClient` directly. Obtain the per-family adapter via `family_adapter_cache.get_family_adapter(...)` (cached) or `DeerFlowAdapter.create_family_adapter(...)`.

## Runtime & Dispatch (the v2 `stream_run` path)

Central dispatch lives in `services/runtime/`. Flow:

```
routers/runs_stream.py:stream_run
  → services/runtime/sse_gateway.py:start_run   (R1 allowlist + RunManager.create_or_reject)
  → services/runtime/worker.py:run_agent        (sets sandbox ContextVar, reads metadata["app"])
  → _run_<app>_agent                            (5 branches, see table below)
  → DeerFlowAdapter.typed_stream_dispatch       (services/deerflow_adapter/adapter.py)
  → DeerFlowClient.stream                        (inside ThreadPoolExecutor w/ copy_context)
  → bridge.publish → sse_consumer → format_sse  (LangGraph Platform SSE wire format)
```

### Multi-app dispatch (`metadata["app"]`)

The dispatch app is carried in `body.metadata["app"]` (defaults to `"numina"`). `worker.run_agent` branches on it:

| App | Runner | Skill | Purpose |
|-----|--------|-------|---------|
| `numina` (default) | `_run_numina_agent` | `chat` / `chat-search` | `/ai/chat` live conversation |
| `asset-report` | `_run_asset_report_pipeline` | `asset-report` | 3-step report pipeline |
| `import-parse` | `_run_import_parse_agent` | `import-parse` | PDF/statement parse (single run) |
| `finance-coach` | `_run_finance_coach_agent` | `finance-coach` | finance advice (single run) |
| `wish-advice` | `_run_wish_advice_agent` | `wish-advice` | wish savings advice (single run) |

Each non-numina runner sets a fixed `skill_name`, injects a synthetic slash-trigger message, runs `adapter.typed_stream_dispatch`, forwards frames, synthesizes `tool_call`/`tool_result` custom events, and emits one result custom event (`report.step2_json` / `import-parse.result` / `finance_coach.result` / `wish_advice.result`) before the `end` frame.

### R1 allowlist (frontend direct dispatch gate)

`sse_gateway.start_run` rejects frontend direct dispatch of `asset-report`/`import-parse`/`finance-coach`/`wish-advice` with **409** ("须经由后端触发端点"). Only `numina` is allowed direct from the frontend. The internal run-trigger endpoints in `app/routers/gateway.py` (`/internal/gateway/runs/{app}/{thread_id}`) set `internal=True` to bypass the 409 gate — the backend has already enforced owner / `require_ai_enabled` / concurrency by that point. Unknown app values → 400.

> **Backend `RESERVED_NAMES`** (`apps/backend/app/routers/ai_skills.py`) is `["chat", "asset-report", "import-parse", "finance-coach", "wish-advice", "dashboard-narrative", "literacy-weekly-report"]` — it protects system skill IDs from custom-skill collision.

### Sandbox

`worker.run_agent` calls `set_family_sandbox_context(family_id, caller_user_id=user_id)` before dispatch and `reset_family_sandbox_context()` in `finally`. This sets a coroutine-scoped `sandbox_family_id` ContextVar read by `NuminaLocalSandboxProvider` (`services/runtime/sandbox_provider.py`) so `write_file`/`read_file`/`str_replace` resolve to `{DEER_FLOW_HOME}/users/{family_id}/threads/{thread_id}/user-data/workspace/`. The ContextVar is propagated into the DeerFlow ThreadPoolExecutor via `adapter._run_in_executor_with_context` (`contextvars.copy_context()`).

### Tool filtering

`sync_tool_patch._patched_get_available_tools` calls `_apply_active_skill_tool_filter`, which reads `active_skill_context.get_active_skill()` (set by the worker via `set_active_skill(skill_name)`) and calls DeerFlow's `filter_tools_by_skill_allowed_tools` to restrict tools to the skill's declared `allowed-tools` (full-name exact match; MCP tools use base names because `MultiServerMCPClient(tool_name_prefix=False)`).

## DeerFlow-parity subsystems

Three thread-scoped subsystems mirror DeerFlow's canonical implementations (all on the `numina` chat path):

| Subsystem | Endpoint(s) | Implementation |
|-----------|-------------|----------------|
| **Thread compaction** | `POST /threads/{id}/compact` | `compact_service.py` — thin wrapper over DeerFlow's `compact_thread_context` |
| **Thread goal** | `GET/PUT/DELETE /threads/{id}/goal` | `goal_store.py` (persistence) + `goal_evaluator.py` (non-thinking LLM judging completion) |
| **Todo tracking** | (no endpoint — middleware) | `deerflow_adapter/todo_middleware.py` — `TodoListMiddleware` subclass (context-loss reminder + premature-exit prevention) |

**Gotchas:**
- **Compaction delegates to DeerFlow's canonical `compact_thread_context`** — do not hand-write message partitioning. LangGraph's default `messages` reducer re-accumulates by id, so a naive short-list `aput` does not persist on the next run.
- **Goal evaluator reuses the family provider via `_create_lightweight_llm`**, not DeerFlow's `create_goal_evaluator_model` — the worker path carries no DeerFlow `AppConfig`. It runs after the user-visible turn completes; fail-closed (returns `missing_evidence` without calling the LLM when there is no visible assistant evidence).
- **TodoMiddleware is wired only in plan mode** — `worker.py` passes `[get_todo_middleware()] if call_plan_mode else None`. Use the `get_todo_middleware()` module-level singleton (not a fresh instance per call) so the middlewares cache key `tuple(id(m) for m in middlewares)` stays stable.

## Directory Structure

```
agent/
├── app/
│   ├── config.py              # AgentSettings (pydantic-settings) — see §Key Environment Variables
│   ├── main.py                # FastAPI app + lifespan + httpx/MCP patches; router registration
│   ├── scheduler.py           # APScheduler (configured; stream_run-trigger jobs commented out)
│   ├── auth/
│   │   └── jwt_verify.py      # VerifiedFamily + verify_family_token (JWT cookie auth for external routers)
│   └── routers/               # Internal/token-auth routers (NO __init__.py)
│       ├── cache.py           # POST /internal/cache/invalidate/{family_id}
│       └── gateway.py         # /internal/gateway/* — mgmt proxies + run triggers (asset-report/finance-coach/wish-advice)
├── routers/                   # External routers (JWT cookie auth via verify_family_token unless noted)
│   ├── runs_stream.py         # POST /api/threads/{id}/runs/stream (stream_run) + /runs/{run_id}/cancel
│   ├── threads.py             # Thread CRUD + checkpointer state/history/token-usage/branches + goal + compact
│   ├── import_parse.py        # POST /import/parse — sync JSON parse (X-Agent-Token)
│   ├── input_polish.py        # POST /input-polish — D3 DeerFlow-synced draft polish (cookie auth)
│   ├── model_test.py          # POST /test/model — stateless model capability test (X-Agent-Token)
│   └── suggest.py             # POST /suggest/asset — asset field suggestions (X-Agent-Token)
├── core/
│   ├── backend_client.py      # BackendClient — httpx client for all backend calls (agent → backend HTTP)
│   ├── desensitize.py         # Structural PII stripping
│   ├── llm.py                 # LLMClient — lightweight single-call LLM (suggest, input_polish, title)
│   └── logging.py             # setup_logging()
├── schemas/
│   ├── capability.py | context.py | model_test.py | policy.py | response.py
├── services/
│   ├── runtime/               # v2 dispatch runtime
│   │   ├── worker.py          # run_agent + 5 per-app runners (_run_numina/_asset_report/_import_parse/_finance_coach/_wish_advice)
│   │   ├── sse_gateway.py     # start_run (R1 allowlist) + sse_consumer + format_sse (LangGraph Platform SSE)
│   │   ├── run_extras.py      # generate_suggestions + sync_title_from_checkpoint
│   │   ├── sandbox_provider.py# NuminaLocalSandboxProvider + sandbox_family_id ContextVar
│   │   ├── subagent_registry.py
│   │   ├── lifespan.py        # get_run_manager / get_stream_bridge / init_runtime
│   │   ├── asset_report_middleware.py
│   │   └── gc.py
│   ├── deerflow_adapter/      # DeerFlow harness integration — see §Adapter Location
│   │   ├── adapter.py
│   │   ├── family_adapter_cache.py
│   │   ├── client_factory.py
│   │   ├── active_skill_context.py
│   │   ├── memory_config_bridge.py
│   │   ├── original_user_content_context.py  # ContextVar for original user content
│   │   ├── sync_tool_patch.py
│   │   └── exceptions.py
│   ├── agent_dispatch.py      # LEGACY NDJSON gateway path (stream_agent_dispatch) — not the v2 path; imports _fire_and_forget/_select_model from orchestrator.py
│   ├── agent_registry.py      # AgentRegistry — per-agent attribute cache (memory_enabled)
│   ├── asset_suggest.py       # lightweight LLM single-call (suggest_asset_fields)
│   ├── input_polish.py        # lightweight LLM single-call (polish_draft)
│   ├── orchestrator.py        # provider-selection / retry / fire-and-forget helpers (no dispatch class)
│   ├── pii_redactor.py        # PII scrubbing (must run before any LLM/dispatch call)
│   ├── policy_guard.py        # Request policy enforcement
│   ├── audit_logger.py        # Structured audit log (log_call)
│   ├── session_journal.py     # Append-only JSONL event log per session
│   ├── session_store.py       # AiSessionRepository (delegates to backend via HTTP)
│   ├── stream_events.py       # EventStreamBuilder
│   ├── capability_registry.py # Loads capabilities from builtin/public/<name>/SKILL.md frontmatter (legacy; skill refactor in progress)
│   ├── compact_service.py     # Thread compaction — wraps DeerFlow's compact_thread_context
│   ├── goal_store.py          # Thread-scoped goal persistence (read/write/build state)
│   ├── goal_evaluator.py      # Non-thinking LLM that judges goal completion
│   ├── output_mapper.py
│   ├── import_parse_service.py
│   ├── model_tester.py
│   ├── message_classifier.py
│   └── (health_report.py, vision_test_image.py, agent_temp_cache.py, chat.py, chat_adapter.py)
├── skills/
│   └── builtin/public/        # DeerFlow-native LocalSkillStorage scanner layout
│       ├── chat/SKILL.md
│       ├── chat-search/SKILL.md
│       ├── asset-report/SKILL.md
│       ├── import-parse/SKILL.md
│       ├── finance-coach/SKILL.md
│       ├── wish-advice/SKILL.md
│       ├── skill-creator/SKILL.md    # internal-only (_INTERNAL_ONLY_SKILLS)
│       └── skill-installer/SKILL.md  # internal-only (_INTERNAL_ONLY_SKILLS)
├── deerflow_config/
│   ├── HARNESS_API.md         # DeerFlow harness API reference
│   ├── HARNESS_VERSION        # pinned harness revision
│   ├── base/config.yaml       # Base config template ($AI_MODEL, $AI_API_KEY placeholders)
│   ├── dev/config.yaml
│   ├── prod/config.yaml
│   └── agents/family-finance-agent/profile.yaml
├── prompts/chat/default_system_prompt.md
├── tests/                   # ⚠️ legacy dir — see §Quality Commands; canonical root is tests/agent/
│   ├── integration/           # gateway, runs-cancel, u2-app-dispatch, v2-sse-contract
│   └── unit/                  # worker_*, adapter_contextvar, sync_tool_patch, threads routers, etc.
│   # Canonical tests live in tests/agent/ (unit/ ~26 files, integration/, golden/) — see top of file.
└── scripts/                   # vendor-deerflow.sh, patch-deerflow-thread-data.py, patch-langgraph-runtime.py
```

## Key Environment Variables

`AgentSettings` (`app/config.py`). Priority: system env > DeerFlow dynamic injection > `.env` > class defaults. `DATA_ROOT` is the unified data root — `LOG_DIR`, `SESSIONS_DATA_DIR`, `AGENT_DATA_DIR`, `DEERFLOW_DB_PATH` all derive from it via the `_resolve_data_root` validator.

| Variable | Default | Purpose |
|----------|---------|---------|
| `BACKEND_BASE_URL` | `http://backend:8000` | Backend service address |
| `BACKEND_BASE_URL` | `http://backend:8000` | Backend service address |
| `AI_ENCRYPTION_KEY` | — | Fernet key shared with backend for decrypting per-family stored API keys |
| `DATA_ROOT` | `~/.numina/data` | Unified data root — other path vars derive from this |
| `ENVIRONMENT` | `development` | Controls whether `/docs` is exposed (hidden in `production`) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `LOG_DIR` | `{DATA_ROOT}/logs` | Log dir |
| `SESSIONS_DATA_DIR` | `{DATA_ROOT}/workspaces` | JSONL session event logs |
| `AGENT_DATA_DIR` | `{DATA_ROOT}/workspaces` | Agent data root (memory, sandboxes); also sets `DEER_FLOW_HOME` if unset |
| `DEERFLOW_DB_PATH` | `{DATA_ROOT}/db/deerflow-checkpoints.db` | DeerFlow checkpointer SQLite path |
| `DEERFLOW_CONCURRENCY` | `8` | DeerFlow ThreadPoolExecutor workers + semaphore |
| `DEERFLOW_DEFAULT_TIMEOUT` | `300` | Default timeout for DeerFlow operations |
| `SSE_HEARTBEAT_INTERVAL` | `15.0` | SSE heartbeat seconds |
| `SSE_QUEUE_MAXSIZE` | `256` | Per-run SSE queue cap |
| `RUN_CLEANUP_DELAY_SECONDS` | `300.0` | Deferred run GC |
| `RUN_DRAIN_TIMEOUT_SECONDS` | `30.0` | Timeout for draining active runs |
| `STREAM_CLEANUP_DELAY_SECONDS` | `60.0` | Deferred bridge cleanup |
| `SUBAGENT_MAX_CONCURRENT` | `3` | Subagent bg tasks |
| `SUBAGENT_TIMEOUT_SECONDS` | `900` | Subagent timeout |
| `IMPORT_PARSE_TIMEOUT_SECONDS` | `110.0` | Import-parse timeout (strictly < backend's 120s httpx timeout) |
| `SANDBOX_MAX_CACHED_THREADS` | `256` | Sandbox LRU cap |
| `SANDBOX_IDLE_TIMEOUT_SECONDS` | `600` | Sandbox idle eviction |
| `DEERFLOW_GATEWAY_URL` | `http://localhost:8001` | DeerFlow Gateway API (internal proxy) |

**Non-`AgentSettings` env vars read directly:** `DEER_FLOW_CONFIG_PATH` (set in `main.py` from `deerflow_config/base/config.yaml` if unset; overridden per-family in `family_adapter_cache`), `DEERFLOW_DB_URL` (read via `os.environ` in `main.py` lifespan for a postgres checkpointer override), `DEERFLOW_ENV` (read via `os.getenv` in `adapter._make_adapter` for the legacy global singleton only).

## Patterns

### Streaming Protocols

The v2 `stream_run` path uses the **LangGraph Platform SSE wire format** (`text/event-stream`) so `@langchain/langgraph-sdk`'s `useStream` works unmodified. Frame types: `messages`, `values`, `custom`, `end`, `error`. Heartbeat sentinels fire every `SSE_HEARTBEAT_INTERVAL`s; client disconnect triggers run cancel; `Last-Event-ID` supports reconnection.

The legacy NDJSON gateway path (`agent_dispatch.py:stream_agent_dispatch`) still exists for backward compatibility but is **not** the v2 path. Prefer `stream_run` for new capabilities. The legacy text stream used `[THINK]`/`[TEXT]` chunk prefixes — do not reintroduce.

### Skill Schema (`skills/builtin/public/<name>/SKILL.md`)

Skills live in `skills/builtin/public/<name>/SKILL.md` — the DeerFlow-native `LocalSkillStorage` scanner requires the `public/` category subdir and a per-skill directory (allowing bundled assets).

Each `SKILL.md` uses the DeerFlow-native frontmatter schema (prompts live in the body, loaded by the DeerFlow harness — not by `SkillLoader`):

```markdown
---
name: asset-report
description: 生成家庭资产报告
trigger_phrases:
  - /asset-report
  - 生成家庭资产报告
allowed-tools:
  - get_family_overview
  - get_assets
  - get_liabilities
  - get_members
  - get_recent_alerts
  - write_file
thinking: true
max_tokens: 6000
---

## 适用场景
...
```

**Two consumers:**
- **`CapabilityRegistry`** — reads UI metadata for `/capabilities` discovery.
- **`SkillLoader`** — reads `thinking`/`mcp_tools`/`subagent_enabled`/`plan_mode` flags for backward-compat dispatch config (the harness loads the prompt body itself).

`skill-creator` and `skill-installer` are internal-only skills excluded from agent dispatch via `_INTERNAL_ONLY_SKILLS` in `agent_dispatch.py`. Per-family custom skill overrides are fetched from the backend (not stored under `skills/`).

### Pydantic v2

```python
# ✅ ConfigDict
from pydantic import BaseModel, ConfigDict
class MyModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# ✅ model_validate
obj = MyModel.model_validate(data)

# ✅ field_validator
from pydantic import field_validator
class MyModel(BaseModel):
    @field_validator("field")
    @classmethod
    def check(cls, v: str) -> str:
        return v.strip()
```

### Authentication

All endpoints use `X-Agent-Token` header with JWT tokens issued by `create_agent_token()`. The JWT is verified by `verify_service_token` in `packages/security/service_auth/agent_token_verify.py`.

## Gotchas

- **`orchestrator.py` is not an orchestrator** — the file holds only provider-selection / retry / fire-and-forget helpers (`_select_model`, `_select_provider_with_retry`, `_is_transient_error`, `_should_route_to_half_open`, `_fire_and_forget`), imported by the legacy `agent_dispatch.py`. Multi-app dispatch lives in `runtime/worker.py`, not here.
- **`agent_dispatch.py` is the legacy NDJSON path** — `stream_agent_dispatch` still works but is not the v2 `stream_run` path. Do not build new capabilities against it.
- **DeerFlow init failure is non-fatal** — checkpointer init in `main.py` lifespan is wrapped in `try/except`. If the persistence engine fails to init, the app starts but DeerFlow dispatches fail at run time and return error responses.
- **`_CHECKPOINTER_LOCK` serialises non-streaming DeerFlow calls** — at most 1 concurrent non-streaming DeerFlow dispatch at a time. Streaming (`stream_run`) calls do not hold this lock.
- **Temp config dirs accumulate in `/tmp`** — `family_adapter_cache.py` creates a `tempfile.mkdtemp()` per family. Evicted entries clean up, but a crash leaves orphaned dirs.
- **Session journal and session store can diverge** — `session_journal` writes JSONL to local disk; session metadata goes to backend DB via fire-and-forget HTTP. A backend failure leaves the local log without a corresponding DB record.
- **Scheduler has zero active jobs** — `scheduler.py` is configured and starts cleanly but all job registrations are commented out.
- **Importing from `apps/backend` directly** — Symptom: `ImportError`/`ModuleNotFoundError` on `apps.backend.*`, or tests pass locally but fail in CI because the backend package is not installed in the agent's virtualenv. Cause: violates the import direction rule — the agent must not import from `apps/backend` or `apps/scheduler_worker` directly. Fix: use `core/backend_client.py` for all backend data access (HTTP).

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
- [`deerflow_config/HARNESS_API.md`](./deerflow_config/HARNESS_API.md) — DeerFlow harness API reference
