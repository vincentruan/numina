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
uv run pytest apps/agent/tests/ -v         # run all tests (integration/ + unit/)
uv run pytest apps/agent/tests/ -v -k "keyword"  # run tests matching keyword
```

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

## Cross-Cutting Invariants

These apply across the whole server monorepo. An agent loading only this file must still know them.

1. **Router decorator style** — see root [CLAUDE.md](../../CLAUDE.md) §URL Style for the `redirect_slashes=False` rule
2. **Snowflake ID serialization** — if this service ever returns IDs in API responses, use `SnowflakeBase` not plain `BaseModel`. JS loses precision on integers > 2⁵³. See `server/apps/backend/CLAUDE.md` for the full pattern.
3. **Auth return codes** — the agent uses `X-Agent-Token` (shared secret), not JWT auth endpoints. If auth-style endpoints are ever added, they return `200` not `201`.
4. **Import direction** — this service must never import from `apps/backend` or `apps/scheduler_worker` directly. All backend data access goes through `core/backend_client.py` (HTTP). Use `packages/` for shared logic.

## DeerFlow Framework Guardrails

DeerFlow 2.0 is batteries-included: it already provides runtime, tools, skills, memory, sandbox, planning, and subagent coordination. **Do NOT reimplement these.**

### Prohibited Abstractions

| Forbidden Class/File | Why | Use Instead |
|---------------------|-----|-------------|
| `AgentRuntime` | DeerFlow already provides execution harness | `DeerFlowClient` through adapter |
| `ToolRegistry` | DeerFlow manages MCP tools natively | Configure in `deerflow_config/*.yaml` |
| `SkillLoader` | DeerFlow loads `skills/*.md` automatically | Skill files + `SkillLoader` in adapter only |
| `MemoryManager` | DeerFlow has checkpointer/thread memory | `checkpointer` config in client |
| `Orchestrator` | DeerFlow orchestrates agent + tools + memory | `subagent_enabled=True` if needed |
| `WorkflowEngine` | DeerFlow has graph-based workflows | `plan_mode=True` for multi-step |
| `SubAgentCoordinator` | DeerFlow supports nested subagents | `subagent_enabled` + skill triggers |
| `MCPRuntime` | DeerFlow runs MCP servers internally | MCP config in deerflow_config |

### Design Constraints

- **No langchain-native reimplementation.** If DeerFlow provides a capability (long-task orchestration, tool calling, memory, planning), use it via adapter — never rebuild equivalent logic with `langchain` primitives.
- **Reuse DeerFlow interaction patterns.** Streaming, progress reporting, and multi-step planning UX must follow DeerFlow's canonical patterns. Do not invent new interaction protocols.

### Prohibited Dependencies

Never add these unless explicitly asked to migrate frameworks:
- LangGraph, CrewAI, AutoGen, Agno, LlamaIndex AgentWorkflow, OpenAI Agents SDK

### Pre-Change Checklist

Before any agent design or code change:

1. **Context7 lookup required.** Resolve `deerflow` via context7 (`resolve-library-id` → `query-docs`) and read the latest API. Never assume DeerFlow lacks a capability — verify first.
2. Does `DeerFlowClient` config already support this? (`model_name`, `thinking_enabled`, `plan_mode`, `subagent_enabled`, `available_skills`, `checkpointer`)
3. Does existing DeerFlow skill/tool/memory/MCP cover this?
4. If no: extend `deerflow_adapter/adapter.py` minimally — never build parallel harness.
5. If yes: call adapter from business code, don't wrap it again.

### Adapter Location

All DeerFlow integration lives in one package (`services/deerflow_adapter/`):

```
services/deerflow_adapter/
├── adapter.py              # DeerFlowAdapter — typed_stream_dispatch + raw_stream_dispatch (ThreadPoolExecutor bridge)
├── family_adapter_cache.py # LRU cache (100 families) of per-family DeerFlowClient + temp config generation
├── client_factory.py       # builds DeerFlowClient from generated config
├── skill_loader.py         # SkillLoader — reads thinking/mcp_tools flags from builtin/public/<name>/SKILL.md frontmatter
├── active_skill_context.py # ContextVar holding the active skill name (drives tool filtering)
├── memory_config_bridge.py # bridges DeerMem memory config per family
├── interrupt_tools.py      # tools used during interrupt/resume flows
├── sync_tool_patch.py      # monkey-patches DeerFlow harness: sync wrapping, ContextVar propagation, MCP proxy, active-skill tool filter
└── exceptions.py
```

Business code (routers, worker) calls adapter methods — never instantiates `DeerFlowClient` directly. The per-family adapter is obtained via `family_adapter_cache.get_family_adapter(...)` (cached) or `DeerFlowAdapter.create_family_adapter(...)`.

## Runtime & Dispatch (the v2 `stream_run` path)

The central dispatch lives in `services/runtime/`, NOT in an `Orchestrator` class (deleted in U8). Flow:

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
| `asset-report` | `_run_asset_report_pipeline` | `asset-report` | U4 3-step report pipeline |
| `import-parse` | `_run_import_parse_agent` | `import-parse` | U8 single-run PDF/statement parse |
| `finance-coach` | `_run_finance_coach_agent` | `finance-coach` | Plan A single-run advice |
| `wish-advice` | `_run_wish_advice_agent` | `wish-advice` | Plan B T7 single-run advice |

Each non-numina runner sets a fixed `skill_name`, injects a synthetic slash-trigger message, runs `adapter.typed_stream_dispatch`, forwards frames, synthesizes `tool_call`/`tool_result` custom events, and emits one result custom event (`report.step2_json` / `import-parse.result` / `finance_coach.result` / `wish_advice.result`) before the `end` frame.

### R1 allowlist (frontend direct dispatch gate)

`sse_gateway.start_run` rejects frontend direct dispatch of `asset-report`/`import-parse`/`finance-coach`/`wish-advice` with **409** ("须经由后端触发端点"). Only `numina` is allowed direct from the frontend. The internal run-trigger endpoints in `app/routers/gateway.py` (`/internal/gateway/runs/{app}/{thread_id}`) set `internal=True` to bypass the 409 gate — the backend has already enforced owner / `require_ai_enabled` / concurrency by that point. Unknown app values → 400.

> **Backend `RESERVED_NAMES`** (`apps/backend/app/routers/ai_skills.py`) is `["chat", "asset-report", "import-parse", "finance-coach"]` — it protects system skill IDs from custom-skill collision. Note: `wish-advice` is accepted by the agent worker/allowlist but is **not yet** in the backend `RESERVED_NAMES` list (latent inconsistency).

### Sandbox

`worker.run_agent` calls `set_family_sandbox_context(family_id, caller_user_id=user_id)` before dispatch and `reset_family_sandbox_context()` in `finally` (P0 fix). This sets a coroutine-scoped `sandbox_family_id` ContextVar read by `NuminaLocalSandboxProvider` (`services/runtime/sandbox_provider.py`) so `write_file`/`read_file`/`str_replace` resolve to `{DEER_FLOW_HOME}/users/{family_id}/threads/{thread_id}/user-data/workspace/`. The ContextVar is propagated into the DeerFlow ThreadPoolExecutor via `adapter._run_in_executor_with_context` (`contextvars.copy_context()`).

### Tool filtering

`sync_tool_patch._patched_get_available_tools` calls `_apply_active_skill_tool_filter`, which reads `active_skill_context.get_active_skill()` (set by the worker via `set_active_skill(skill_name)`) and calls DeerFlow's `filter_tools_by_skill_allowed_tools` to restrict tools to the skill's declared `allowed-tools` (full-name exact match; MCP tools use base names because `MultiServerMCPClient(tool_name_prefix=False)`).

## Directory Structure

```
agent/
├── app/
│   ├── config.py              # AgentSettings (pydantic-settings) — see §Key Environment Variables
│   ├── main.py                # FastAPI app + lifespan + httpx/MCP patches; router registration
│   ├── scheduler.py           # APScheduler (configured; stream_run-trigger jobs commented out pending USE_DEERFLOW)
│   ├── auth/
│   │   └── jwt_verify.py      # VerifiedFamily + verify_family_token (JWT cookie auth for external routers)
│   └── routers/               # Internal/token-auth routers (NO __init__.py)
│       ├── cache.py           # POST /internal/cache/invalidate/{family_id}
│       └── gateway.py         # /internal/gateway/* — mgmt proxies + run triggers (asset-report/finance-coach/wish-advice)
├── routers/                   # External routers (JWT cookie auth via verify_family_token unless noted)
│   ├── runs_stream.py         # POST /api/threads/{id}/runs/stream (stream_run) + /runs/{run_id}/cancel
│   ├── resume.py              # POST /api/threads/{id}/runs/resume (interrupt resume)
│   ├── threads.py             # Thread CRUD + checkpointer state/history/token-usage/branches
│   ├── capabilities.py        # GET /capabilities (X-Agent-Token)
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
│   ├── runtime/               # v2 dispatch runtime (the real orchestrator layer)
│   │   ├── worker.py          # run_agent + 5 per-app runners (_run_numina/_asset_report/_import_parse/_finance_coach/_wish_advice)
│   │   ├── sse_gateway.py     # start_run (R1 allowlist) + sse_consumer + format_sse (LangGraph Platform SSE)
│   │   ├── run_extras.py      # generate_suggestions + sync_title_from_checkpoint
│   │   ├── sandbox_provider.py# NuminaLocalSandboxProvider + sandbox_family_id ContextVar
│   │   ├── subagent_registry.py
│   │   ├── lifespan.py        # get_run_manager / get_stream_bridge / init_runtime
│   │   ├── asset_report_middleware.py
│   │   └── gc.py
│   ├── deerflow_adapter/      # DeerFlow harness integration — see §Adapter Location
│   ├── agent_dispatch.py      # LEGACY NDJSON gateway path (stream_agent_dispatch) — not the v2 path; imports _fire_and_forget/_select_model from orchestrator.py
│   ├── agent_registry.py      # AgentRegistry — per-agent attribute cache (memory_enabled)
│   ├── asset_suggest.py       # lightweight LLM single-call (suggest_asset_fields)
│   ├── input_polish.py        # lightweight LLM single-call (polish_draft)
│   ├── orchestrator.py        # Orchestrator class DELETED (U8); retains _select_model/_fire_and_forget/_select_provider_with_retry helpers
│   ├── fallback_engine.py     # STUB — module docstring only, no logic (import compat)
│   ├── pii_redactor.py        # PII scrubbing (must run before any LLM/dispatch call)
│   ├── policy_guard.py        # Request policy enforcement
│   ├── audit_logger.py        # Structured audit log (log_call)
│   ├── session_journal.py     # Append-only JSONL event log per session
│   ├── session_store.py       # AiSessionRepository (delegates to backend via HTTP)
│   ├── stream_events.py       # EventStreamBuilder
│   ├── capability_registry.py # Loads capabilities from builtin/public/<name>/SKILL.md frontmatter
│   ├── output_mapper.py
│   ├── import_parse_service.py
│   ├── model_tester.py
│   ├── message_classifier.py
│   └── (health_report.py, liability_advisor.py, spending_leak.py, vision_test_image.py, agent_temp_cache.py, chat.py, chat_adapter.py)
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
├── tests/
│   ├── integration/           # gateway, runs-cancel, u2-app-dispatch, v2-sse-contract
│   └── unit/                  # ~16 files (worker_*, adapter_contextvar, sync_tool_patch, resume/threads routers, etc.)
└── scripts/                   # vendor-deerflow.sh, patch-deerflow-thread-data.py, patch-langgraph-runtime.py
```

## Key Environment Variables

`AgentSettings` (`app/config.py`). Priority: system env > DeerFlow dynamic injection > `.env` > class defaults. `DATA_ROOT` is the unified data root — `LOG_DIR`, `SESSIONS_DATA_DIR`, `AGENT_DATA_DIR`, `DEERFLOW_DB_PATH` all derive from it via the `_resolve_data_root` validator.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_INTERNAL_TOKEN` | — | **Required.** Shared service-to-service token; startup fails without it |
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
| `SSE_HEARTBEAT_INTERVAL` | `15.0` | SSE heartbeat seconds |
| `SSE_QUEUE_MAXSIZE` | `256` | Per-run SSE queue cap |
| `RUN_CLEANUP_DELAY_SECONDS` | `300.0` | Deferred run GC |
| `STREAM_CLEANUP_DELAY_SECONDS` | `60.0` | Deferred bridge cleanup |
| `SUBAGENT_MAX_CONCURRENT` | `3` | Subagent bg tasks |
| `SUBAGENT_TIMEOUT_SECONDS` | `900` | Subagent timeout |
| `IMPORT_PARSE_TIMEOUT_SECONDS` | `110.0` | Import-parse timeout (strictly < backend's 120s httpx timeout) |
| `SANDBOX_MAX_CACHED_THREADS` | `256` | Sandbox LRU cap |
| `SANDBOX_IDLE_TIMEOUT_SECONDS` | `600` | Sandbox idle eviction |
| `DEERFLOW_GATEWAY_URL` | `http://localhost:8001` | DeerFlow Gateway API (internal proxy) |

**Non-`AgentSettings` env vars read directly:** `DEER_FLOW_CONFIG_PATH` (set in `main.py` from `deerflow_config/base/config.yaml` if unset; overridden per-family in `family_adapter_cache`), `DEERFLOW_DB_URL` (read via `os.environ` in `main.py` lifespan for a postgres checkpointer override), `DEERFLOW_ENV` (read via `os.getenv` in `adapter._make_adapter` for the legacy global singleton only).

**Note:** `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are **not used directly by the agent.** LLM credentials come from the backend's per-family AI config endpoint (`/api/v1/internal/ai/config`), which returns a decrypted `api_key` and `ai_provider`. `AI_ENCRYPTION_KEY` is the Fernet key the backend uses to decrypt stored keys before returning them.

## Patterns

### DeerFlow as Mandatory Execution Path

DeerFlow is the only multi-step execution path. There is no fallback to direct LLM calls for dispatch. If DeerFlow fails, the per-app runner in `runtime/worker.py` returns a structured error response to the caller — the user sees an error and should retry. Lightweight single-call LLM paths (`suggest`, `input_polish`, title generation) intentionally bypass DeerFlow and use `core/llm.py` directly — this is by design, not a violation.

Per-family `DeerFlowClient` instances are cached in an LRU cache (max 100 families) in `services/deerflow_adapter/family_adapter_cache.py`. Each family gets a temp `config.yaml` + `extensions_config.json` generated from `deerflow_config/base/config.yaml` with their `api_key`/`model_id`/provider substituted. A shared `AsyncSqliteSaver` checkpointer is passed to every client (initialized in lifespan). Cache is invalidated via `POST /internal/cache/invalidate/{family_id}` (→ `invalidate_family_adapter_cache`).

### Streaming Protocols

The v2 `stream_run` path uses the **LangGraph Platform SSE wire format** (`text/event-stream`) so `@langchain/langgraph-sdk`'s `useStream` works unmodified. Frame types: `messages`, `values`, `custom`, `end`, `error`, plus `interrupt` (custom event). Heartbeat sentinels fire every `SSE_HEARTBEAT_INTERVAL`s; client disconnect triggers run cancel; `Last-Event-ID` supports reconnection.

The legacy NDJSON gateway path (`agent_dispatch.py:stream_agent_dispatch`) still exists for backward compatibility but is **not** the v2 path. Prefer `stream_run` for new capabilities. The legacy text stream used `[THINK]`/`[TEXT]` chunk prefixes — do not reintroduce.

### Skill Schema (`skills/builtin/public/<name>/SKILL.md`)

Skills live in `skills/builtin/public/<name>/SKILL.md` — the DeerFlow-native `LocalSkillStorage` scanner requires the `public/` category subdir and a per-skill directory (allowing bundled assets). The old flat `skills/*.md` layout is gone (U1-U8 deleted `alerts`/`allocation`/`disposal`/`liability`/`report`/`spending_leak`/`time_machine` trigger skills).

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

All endpoints require `X-Agent-Token` header matching `AGENT_INTERNAL_TOKEN`. No JWT — simple shared secret for internal backend → agent calls only.

## Gotchas

- **`orchestrator.py` is not an orchestrator anymore** — the `Orchestrator` class and `dispatch` method were deleted in U8. The file now holds only provider-selection / retry / fire-and-forget helpers (`_select_model`, `_select_provider_with_retry`, `_is_transient_error`, `_should_route_to_half_open`, `_fire_and_forget`), imported by the legacy `agent_dispatch.py`. Do not add dispatch logic here — multi-app dispatch lives in `runtime/worker.py`.
- **`agent_dispatch.py` is the legacy NDJSON path** — `stream_agent_dispatch` still works but is not the v2 `stream_run` path. Do not build new capabilities against it.
- **`fallback_engine.py` is a stub** — module docstring only, no logic; kept for import compatibility. Do not add dispatch code to it.
- **DeerFlow init failure is non-fatal** — checkpointer init in `main.py` lifespan is wrapped in `try/except`. If the persistence engine fails to init, the app starts but DeerFlow dispatches fail at run time and return error responses.
- **`_CHECKPOINTER_LOCK` serialises non-streaming DeerFlow calls** — at most 1 concurrent non-streaming DeerFlow dispatch at a time. Streaming (`stream_run`) calls do not hold this lock.
- **Temp config dirs accumulate in `/tmp`** — `family_adapter_cache.py` creates a `tempfile.mkdtemp()` per family. Evicted entries clean up, but a crash leaves orphaned dirs.
- **Session journal and session store can diverge** — `session_journal` writes JSONL to local disk; session metadata goes to backend DB via fire-and-forget HTTP. A backend failure leaves the local log without a corresponding DB record.
- **Scheduler has zero active jobs** — `scheduler.py` is configured and starts cleanly but the `stream_run`-trigger jobs are commented out (pending `USE_DEERFLOW`).
- **`wish-advice` is in the agent allowlist but not backend `RESERVED_NAMES`** — latent inconsistency (see §R1 allowlist). A custom skill named `wish-advice` could be created on the backend today.
- **Importing from `apps/backend` directly** — Symptom: `ImportError`/`ModuleNotFoundError` on `apps.backend.*`, or tests pass locally but fail in CI because the backend package is not installed in the agent's virtualenv. Cause: violates the import direction rule — the agent must not import from `apps/backend` or `apps/scheduler_worker` directly. Fix: use `core/backend_client.py` for all backend data access (HTTP).

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
- [`deerflow_config/HARNESS_API.md`](./deerflow_config/HARNESS_API.md) — DeerFlow harness API reference
