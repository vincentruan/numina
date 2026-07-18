# agent/CLAUDE.md

Module-specific guidance for the Python FastAPI AI agent microservice.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

```bash
uv run ruff check .              # lint
uv run ruff check . --fix        # lint + auto-fix
uv run ruff format .             # format (only files you touch)
uv run mypy . --exclude vendor   # type check
uv run pytest tests/ -v          # run all tests
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
3. **Audit logging:** Every agent decision must emit an audit event via `audit_logger`. This includes both success and error paths — the `finally` block in `orchestrator.py` guarantees this.
4. **DeerFlow-only execution:** All agent orchestration must use `DeerFlowClient` through `services/deerflow_adapter/`. Never implement custom runtime, tool registry, skill loader, memory manager, orchestrator, or workflow engine.

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

All DeerFlow integration lives in one place:

```
services/deerflow_adapter/
├── adapter.py              # Async wrapper + ThreadPoolExecutor
├── family_adapter_cache.py # LRU cache of per-family DeerFlowClient
└── skill_loader.py         # Load flags from skills/*.md frontmatter
```

Business code (routers, services) calls adapter methods — never instantiates `DeerFlowClient` directly.

## Directory Structure

```
agent/
├── app/
│   ├── config.py              # AgentSettings (pydantic-settings)
│   ├── main.py                # FastAPI app entry point + lifespan
│   ├── scheduler.py           # APScheduler (configured, no active jobs yet)
│   └── routers/
│       └── cache.py           # POST /internal/cache/invalidate/{family_id}
├── core/
│   ├── backend_client.py      # httpx client for all backend calls
│   ├── desensitize.py         # Structural PII stripping (assets/liabilities/members)
│   ├── llm.py                 # LLMClient (Anthropic + OpenAI), ThinkingTagParser
│   └── logging.py             # setup_logging()
├── routers/                   # Top-level router registrations (14 routers)
│   ├── agent_stream.py        # Generic agent NDJSON streaming endpoint
│   ├── alerts.py              # POST /alerts/aging, /alerts/stream
│   ├── allocation.py          # POST /allocation/drift, /allocation/stream
│   ├── capabilities.py        # GET /capabilities
│   ├── chat.py                # POST /chat/ask, /chat/ask/stream (NDJSON)
│   ├── disposal.py            # POST /disposal/scan, /disposal/stream
│   ├── import_parse.py        # POST /import/parse
│   ├── liability.py           # POST /liability/analyze, /liability/stream
│   ├── model_test.py          # POST /model-test — validate per-family LLM config (token, model, ping)
│   ├── report.py              # POST /report/generate, /report/generate/stream
│   ├── sessions.py            # GET /sessions, GET /sessions/{id}/events (NDJSON)
│   ├── spending_leak.py       # POST /spending-leak, /spending-leak/stream
│   ├── suggest.py             # POST /suggest/asset
│   └── time_machine.py        # POST /time-machine/interpret, /time-machine/stream
├── services/
│   ├── orchestrator.py        # Central dispatch pipeline (policy → context → PII → DeerFlow → audit)
│   ├── deerflow_adapter/      # DeerFlow harness integration (mandatory execution path)
│   │   ├── adapter.py         # Async wrapper + ThreadPoolExecutor bridge
│   │   ├── family_adapter_cache.py  # LRU cache (100 families) of DeerFlowClient instances
│   │   └── skill_loader.py    # Loads thinking/mcp_tools flags from skills/*.md frontmatter
│   ├── pii_redactor.py        # PII scrubbing (must run before any LLM call)
│   ├── policy_guard.py        # Request policy enforcement (pure in-memory)
│   ├── audit_logger.py        # Structured JSONL audit log (logs/agent-audit.log, 30-day rotation)
│   ├── session_journal.py     # Append-only JSONL event log per session (local disk)
│   ├── session_store.py       # AiSessionRepository (delegates to backend via HTTP)
│   ├── stream_events.py       # EventStreamBuilder → NDJSON event protocol
│   ├── output_mapper.py       # Maps DeerFlow output → AgentResponse
│   └── capability_registry.py # Loads capabilities from skills/*.md frontmatter
├── schemas/
│   ├── capability.py          # CapabilityDefinition, CapabilityUISchema, CapabilityPolicy
│   ├── context.py             # FamilyContext, RedactedContext
│   ├── policy.py              # CapabilityPolicy, PolicyDecision
│   └── response.py            # AgentResponse, Scorecard, RiskFlag, Recommendation, Finding
├── skills/                    # Capability definitions: YAML frontmatter + prompt body
│   ├── alerts.md
│   ├── allocation.md
│   ├── chat.md
│   ├── disposal.md
│   ├── liability.md
│   ├── report.md
│   ├── spending_leak.md
│   ├── time_machine.md
│   └── custom/                # Per-family skill overrides (fetched from backend)
├── deerflow_config/
│   ├── HARNESS_API.md         # DeerFlow harness API reference
│   ├── base/config.yaml       # Base config template ($AI_MODEL, $AI_API_KEY placeholders)
│   ├── dev/config.yaml
│   └── prod/config.yaml
├── tests/
│   ├── conftest.py            # Shared fixtures (mock_backend_client, mock_deerflow_client)
│   ├── golden/                # Golden output tests
│   ├── integration/           # Full dispatch + orchestrator pipeline tests
│   └── unit/                  # ~15 unit test files
├── scripts/
│   ├── vendor-deerflow.sh     # Re-vendors the DeerFlow harness
│   └── vendor-harness.sh
└── vendor/                    # Vendored deerflow-harness (uv workspace member)
```

## Key Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_INTERNAL_TOKEN` | — | **Required.** Shared service-to-service token; startup fails without it |
| `BACKEND_BASE_URL` | `http://backend:8000` | Backend service address |
| `AI_ENCRYPTION_KEY` | — | Fernet key shared with backend for decrypting per-family stored API keys |
| `DEER_FLOW_CONFIG_PATH` | — | **Required.** Path to DeerFlow config.yaml (relative to `server/`, e.g. `apps/agent/deerflow_config/base/config.yaml`) |
| `DEERFLOW_DB_URL` | — | Postgres URL for DeerFlow checkpointer; SQLite used if absent |
| `DEERFLOW_ENV` | `base` | Which `deerflow_config/` overlay to use (`base`/`dev`/`prod`) |
| `ENVIRONMENT` | `development` | Controls whether `/docs` is exposed (hidden in `production`) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `SESSIONS_DATA_DIR` | `data/sessions` | Base dir for JSONL session event logs |

**Note:** `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are **not** used directly by the agent. LLM credentials come from the backend's per-family AI config endpoint (`/api/v1/internal/ai/config`), which returns a decrypted `api_key` and `ai_provider`. `AI_ENCRYPTION_KEY` is the Fernet key used by the backend to decrypt stored keys before returning them.

## Patterns

### DeerFlow as Mandatory Execution Path

DeerFlow is the only execution path. There is no fallback to direct LLM calls. If DeerFlow fails, the orchestrator returns a structured error response to the caller — the user sees "AI 服务暂时不可用，请稍后重试" and should retry.

Per-family `DeerFlowClient` instances are cached in an LRU cache (max 100 families). Each family gets a temp config generated from `deerflow_config/base/config.yaml` with their `api_key`/`model_id` substituted. Cache is invalidated via `POST /internal/cache/invalidate/{family_id}`.

### Streaming Protocols

Two streaming protocols coexist — do not mix them:

| Protocol | Content-Type | Used by |
|----------|-------------|---------|
| Raw text chunks | `text/plain` | All capabilities except chat |
| NDJSON events | `application/x-ndjson` | `chat/ask/stream`, `sessions/{id}/events`, `agent_stream` |

NDJSON event types: `phase.{connecting|thinking|answering}`, `token.stream`, `tool.call`, `tool.result`, `capability.end`, `capability.error`.

The legacy text stream uses `[THINK]` / `[TEXT]` chunk prefixes. Prefer the NDJSON path for new capabilities.

### Unified Skill Schema (`skills/*.md`)

Each capability has a `skills/{capability}.md` file with a unified frontmatter schema. This single file serves two consumers:

- **`CapabilityRegistry`** — reads UI metadata (`name`, `description`, `icon`, `color`, `route`, `input_mode`, `examples`, `allowed_roles`) for the `/capabilities` discovery endpoint
- **`SkillLoader`** — reads `thinking` and `mcp_tools` flags for orchestrator dispatch config

```markdown
---
capability: chat
name: 智能问答
description: 回答关于净资产、资产配置、负债等问题
category: chat
icon: message-circle
color: "#06b6d4"
route: /ai/chat
input_mode: free_text          # free_text | trigger
placeholder: 问问家庭资产状况...
examples:
  - 我的净资产健康吗？
allowed_roles: [member, admin]
thinking: true
mcp_tools: []
max_tokens: 2000
---
```

There is no prompt body in these files — prompts live in `skills/custom/*/SKILL.md` and are loaded directly by the DeerFlow harness.

### DeerFlow Custom Skills (`skills/custom/*/SKILL.md`)

Loaded directly by the DeerFlow harness from `/app/skills/custom` (configured in `deerflow_config/base/config.yaml`). These use the DeerFlow skill spec format and are invoked by the harness based on `trigger_phrases` matching:

```markdown
---
name: chat
description: |
  触发条件描述...

trigger_phrases:
  - 资产体检
  - 净资产分析

allowed-tools: []

planning:          # optional — enables DeerFlow multi-step planning mode
  enabled: true
  max_steps: 5
---

## 适用场景
...

## 输出 JSON Schema
...

## 边界限制
...
```

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

- **`assets` and `members` are always `[]`** — `orchestrator._build_context()` hardcodes both to empty lists (no backend endpoint yet). PII redaction for those fields is a no-op.
- **DeerFlow init failure is non-fatal** — `init_engine()` in `main.py` lifespan is wrapped in `try/except`. If the persistence engine fails to init, the app starts but DeerFlow calls will fail at dispatch time and return error responses.
- **`_CHECKPOINTER_LOCK` serialises non-streaming DeerFlow calls** — at most 1 concurrent non-streaming DeerFlow dispatch at a time. Streaming calls do not hold this lock.
- **Temp config dirs accumulate in `/tmp`** — `family_adapter_cache.py` creates a `tempfile.mkdtemp()` per family. Evicted entries clean up, but a crash leaves orphaned dirs.
- **Session journal and session store can diverge** — `session_journal` writes JSONL to local disk; session metadata goes to backend DB via fire-and-forget HTTP. A backend failure leaves the local log without a corresponding DB record.
- **Scheduler has zero active jobs** — `scheduler.py` is configured and starts cleanly but all job registrations are commented out (Phase 0).
- **`fallback_engine.py` is a stub** — the file exists for import compatibility but contains no dispatch logic. Do not add LLM dispatch code to it.
- **Importing from `apps/backend` directly** — Symptom: `ImportError` or `ModuleNotFoundError` on `apps.backend.*`; or tests pass locally but fail in CI because the backend package is not installed in the agent's virtualenv. Cause: violates the import direction rule — the agent must not import from `apps/backend` or `apps/scheduler_worker` directly. Fix: use `core/backend_client.py` for all backend data access; it wraps `httpx` calls to the backend HTTP API.

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
- [`deerflow_config/HARNESS_API.md`](./deerflow_config/HARNESS_API.md) — DeerFlow harness API reference
