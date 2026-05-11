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
│   ├── alerts.py              # POST /alerts/aging, /alerts/stream
│   ├── allocation.py          # POST /allocation/drift, /allocation/stream
│   ├── capabilities.py        # GET /capabilities
│   ├── chat.py                # POST /chat/ask, /chat/ask/stream (NDJSON)
│   ├── disposal.py            # POST /disposal/scan, /disposal/stream
│   ├── import_parse.py        # POST /import/parse
│   ├── liability.py           # POST /liability/analyze, /liability/stream
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
│   │   └── skill_loader.py    # Loads skill prompts from skills/*.md + per-family overrides
│   ├── fallback_engine.py     # Direct LLM dispatch (used when USE_DEERFLOW=false)
│   ├── pii_redactor.py        # PII scrubbing (must run before any LLM call)
│   ├── policy_guard.py        # Request policy enforcement (pure in-memory)
│   ├── audit_logger.py        # Structured JSONL audit log (logs/agent-audit.log, 30-day rotation)
│   ├── session_journal.py     # Append-only JSONL event log per session (local disk)
│   ├── session_store.py       # AiSessionRepository (delegates to backend via HTTP)
│   ├── stream_events.py       # EventStreamBuilder → NDJSON event protocol
│   ├── output_mapper.py       # Maps DeerFlow/fallback output → AgentResponse
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
| `USE_DEERFLOW` | `false` | Route through DeerFlow harness vs direct LLM calls |
| `DEERFLOW_DB_URL` | — | Postgres URL for DeerFlow checkpointer; SQLite used if absent |
| `DEERFLOW_ENV` | `base` | Which `deerflow_config/` overlay to use (`base`/`dev`/`prod`) |
| `ENVIRONMENT` | `development` | Controls whether `/docs` is exposed (hidden in `production`) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `SESSIONS_DATA_DIR` | `data/sessions` | Base dir for JSONL session event logs |

**Note:** `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` are **not** used directly by the agent. LLM credentials come from the backend's per-family AI config endpoint (`/api/v1/internal/ai/config`), which returns a decrypted `api_key` and `ai_provider`. `AI_ENCRYPTION_KEY` is the Fernet key used by the backend to decrypt stored keys before returning them.

## Patterns

### DeerFlow as Primary Execution Path

DeerFlow is the intended production execution path. `USE_DEERFLOW=true` routes through the DeerFlow harness; `USE_DEERFLOW=false` (default) uses `fallback_engine` for direct LLM calls.

The orchestrator automatically falls back to `fallback_engine` if DeerFlow raises any exception, setting `fallback_used=True` in the response. DeerFlow init failure at startup is non-fatal (logged as warning) — the app starts regardless.

Per-family `DeerFlowClient` instances are cached in an LRU cache (max 100 families). Each family gets a temp config generated from `deerflow_config/base/config.yaml` with their `api_key`/`model_id` substituted. Cache is invalidated via `POST /internal/cache/invalidate/{family_id}`.

### Streaming Protocols

Two streaming protocols coexist — do not mix them:

| Protocol | Content-Type | Used by |
|----------|-------------|---------|
| Raw text chunks | `text/plain` | All capabilities except chat |
| NDJSON events | `application/x-ndjson` | `chat/ask/stream`, `sessions/{id}/events` |

NDJSON event types: `phase.{connecting|thinking|answering}`, `token.stream`, `tool.call`, `tool.result`, `capability.end`, `capability.error`.

The legacy text stream uses `[THINK]` / `[TEXT]` chunk prefixes. Prefer the NDJSON path for new capabilities.

### Two Distinct Skill Systems

There are two separate skill file formats — do not conflate them.

**1. Capability prompt files (`skills/*.md`)** — consumed by `SkillLoader` and `CapabilityRegistry`. These are internal prompt templates, not DeerFlow skills.

```markdown
---
capability: report
thinking: true
mcp_tools: []
---

LLM prompt body with {template_vars}...
```

`CapabilityRegistry` reads frontmatter for the `/capabilities` discovery endpoint. `SkillLoader` reads the full file for prompt dispatch. Per-family prompt overrides are fetched from backend and cached by `(family_id, capability, updated_at)`.

**2. DeerFlow custom skills (`skills/custom/*/SKILL.md`)** — loaded directly by the DeerFlow harness from `/app/skills/custom` (configured in `deerflow_config/base/config.yaml`). These use the DeerFlow skill spec format:

```markdown
---
name: family-asset-checkup
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

DeerFlow custom skills are invoked by the harness based on `trigger_phrases` matching. The `skills/*.md` prompt files are used by the fallback engine and capability registry — they are independent of DeerFlow.

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
- **DeerFlow init failure is non-fatal** — `init_engine()` in `main.py` lifespan is wrapped in `try/except`. `USE_DEERFLOW=true` can silently degrade if the persistence engine fails to init.
- **`_CHECKPOINTER_LOCK` serialises non-streaming DeerFlow calls** — at most 1 concurrent non-streaming DeerFlow dispatch at a time. Streaming calls do not hold this lock.
- **Temp config dirs accumulate in `/tmp`** — `family_adapter_cache.py` creates a `tempfile.mkdtemp()` per family. Evicted entries clean up, but a crash leaves orphaned dirs.
- **Session journal and session store can diverge** — `session_journal` writes JSONL to local disk; session metadata goes to backend DB via fire-and-forget HTTP. A backend failure leaves the local log without a corresponding DB record.
- **Scheduler has zero active jobs** — `scheduler.py` is configured and starts cleanly but all job registrations are commented out (Phase 0).

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, API endpoints
- [`deerflow_config/HARNESS_API.md`](./deerflow_config/HARNESS_API.md) — DeerFlow harness API reference
