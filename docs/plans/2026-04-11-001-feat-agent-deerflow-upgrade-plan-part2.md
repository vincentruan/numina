---
title: "feat: Upgrade agent/ to DeerFlow Harness Architecture — Part 2: Implementation Units"
type: feat
status: completed
date: 2026-04-11
parent: 2026-04-11-001-feat-agent-deerflow-upgrade-plan.md
---

# Implementation Units

This file is Part 2 of the DeerFlow upgrade plan. Read Part 1 first for context, decisions, and architecture.

---

## Phase 1 — Foundation (prerequisite for all DeerFlow work)

- [x] **Unit 1: Fix known bugs in existing agent services**

**Goal:** Eliminate the 5 known bugs before adding new infrastructure, so the fallback path is reliable.

**Requirements:** R3 (backward compatibility), R4 (PII)

**Dependencies:** None

**Files:**
- Modify: `agent/core/desensitize.py`
- Modify: `agent/services/health_report.py`
- Modify: `agent/services/disposal_advisor.py`
- Modify: `agent/services/aging_alert.py`
- Modify: `agent/core/llm.py`
- Modify: `agent/config.py`
- Modify: `agent/main.py`
- Test: `agent/tests/unit/test_desensitize.py`
- Test: `agent/tests/unit/test_llm_client.py`

**Approach:**
- `desensitize.py`: add `remaining_amount_range_mid` field to `desensitize_liabilities()` output (compute midpoint of range as float)
- `health_report.py`: strip markdown fences before JSON parsing (regex `r'```(?:json)?\s*([\s\S]*?)\s*```'` with fallback to raw `find`/`rfind`)
- `disposal_advisor.py` + `aging_alert.py`: call `desensitize_assets()` before building LLM prompt
- `llm.py`: instantiate Anthropic/OpenAI SDK clients once in `__init__`, not per `complete()` call
- `config.py`: add `AGENT_INTERNAL_TOKEN` startup validation — raise `ValueError` if empty
- `main.py`: add startup check that calls `settings.validate()` in lifespan

**Patterns to follow:**
- `backend/app/config.py` for startup validation pattern
- `docs/solutions/best-practices/redis-fail-fast-strategy.md` for fail-fast pattern

**Test scenarios:**
- Happy path: `desensitize_liabilities()` returns dict with `remaining_amount_range_mid` as float
- Edge case: liability amount exactly on range boundary maps to correct midpoint
- Happy path: JSON wrapped in ` ```json ``` ` fences is correctly extracted
- Happy path: JSON without fences still extracted correctly
- Error path: `AGENT_INTERNAL_TOKEN=""` raises `ValueError` at startup
- Happy path: LLM client reuses same SDK instance across two `complete()` calls

**Verification:**
- All existing 36 backend tests still pass (`uv run pytest tests/ -v` from `backend/`)
- `uv run pytest agent/tests/ -v` passes with new unit tests

---

- [x] **Unit 2: Promote PIIRedactor to unified service with free-text support**

**Goal:** Replace the scattered `desensitize_*` calls with a single `PIIRedactor` service that accepts a `FamilyContext` and returns a `RedactedContext`. Critically, add a regex-based pass for free-text inputs (chat questions) that field-stripping cannot handle.

**Requirements:** R4

**Dependencies:** Unit 1

**Files:**
- Create: `agent/services/pii_redactor.py`
- Create: `agent/schemas/context.py` (FamilyContext, RedactedContext Pydantic models)
- Modify: `agent/core/desensitize.py` (keep as internal implementation, imported by pii_redactor)
- Test: `agent/tests/unit/test_pii_redactor.py`

**Approach:**
- `FamilyContext`: typed container for all data fetched from backend (assets, liabilities, members, dashboard data) plus optional `free_text: str | None` for chat inputs
- `RedactedContext`: same shape but with PII fields replaced; includes `redaction_log` listing what was stripped
- `PIIRedactor.redact(ctx: FamilyContext) -> RedactedContext`: calls existing `desensitize_*` functions for structured data; applies regex pass to `free_text`
- Regex patterns for free-text: Chinese ID card (`\d{17}[\dXx]`), phone numbers (`1[3-9]\d{9}`), bank card numbers (`\d{16,19}`), exact addresses (heuristic: 省|市|区|路|号 sequences)
- Redacted tokens replaced with `[已脱敏]` placeholder
- `redaction_log` is included in audit entries but never sent to LLM
- The decrypted API key fetched from backend must never be included in any `FamilyContext` or `RedactedContext` — it is passed separately to the LLM client

**Patterns to follow:**
- `agent/core/desensitize.py` for existing redaction logic
- Pydantic `BaseModel` with `model_config = {"from_attributes": True}` (project convention)

**Test scenarios:**
- Happy path: asset names replaced with category labels in `RedactedContext`
- Happy path: member names replaced with 成员A/B/C labels
- Happy path: liability amounts converted to ranges with correct midpoints
- Edge case: empty asset list produces empty `RedactedContext.assets`
- Edge case: member list with 1 member produces single 成员A label
- Happy path: `redaction_log` lists all fields that were stripped
- Happy path: free-text containing a phone number `13812345678` → `[已脱敏]`
- Happy path: free-text containing an ID card number → `[已脱敏]`
- Edge case: free-text with no PII passes through unchanged
- Edge case: `free_text=None` produces no error

**Verification:**
- `PIIRedactor.redact()` produces output with no raw names, phone numbers, ID numbers, or exact amounts
- Chat service free-text input is redacted before reaching any LLM call
- API key never appears in any `FamilyContext` or `RedactedContext` field

---

- [x] **Unit 3: Add feature flag and AuditLogger**

**Goal:** Add `USE_DEERFLOW` feature flag to config and implement `AuditLogger` that records every agent invocation.

**Requirements:** R6, R10

**Dependencies:** Unit 1

**Files:**
- Modify: `agent/config.py`
- Create: `agent/services/audit_logger.py`
- Create: `agent/tests/unit/test_audit_logger.py`

**Approach:**
- `config.py`: add `USE_DEERFLOW: bool = False` to `AgentSettings`
- `AuditLogger`: writes structured JSON lines to `logs/agent-audit.log` (daily rotation, 30-day retention)
- Log entry fields: `audit_id` (UUID), `timestamp`, `family_id`, `user_id`, `capability`, `skill_triggered`, `fallback_used`, `deerflow_attempted`, `duration_ms`, `success`, `error_type` (if failed), `output_summary` (first 200 chars of response — **must be passed through `PIIRedactor._redact_free_text()` before writing**)
- `AuditLogger.log_call(entry: AuditEntry)` — uses `logging` module with `TimedRotatingFileHandler`. Note: `TimedRotatingFileHandler` performs synchronous disk I/O. To avoid blocking the async event loop under load, wrap the call in `asyncio.to_thread()` or use a `QueueHandler`/`QueueListener` pattern (stdlib). If p99 write latency is acceptable (<1 ms for a single JSON line in practice), sync is permissible — document the choice explicitly.
- Follow `docs/solutions/best-practices/security-audit.md` format: `<timestamp> - INFO - [AGENT_CALL] key=value | key=value`
- `logs/agent-audit.log` must be written with file mode `0600` (owner-only). If `/app/logs` is a Docker volume, document who has host-level access to it and treat the log as sensitive data equivalent to the database.
- `user_id` is included in `AuditEntry` (see field list above) — routers must pass it from request context so member-level abuse can be attributed (not just family-level)

**Patterns to follow:**
- `docs/solutions/best-practices/security-audit.md` for log format and handler setup
- `agent/core/logging.py` for existing logging setup

**Test scenarios:**
- Happy path: `AuditLogger.log_call()` writes a valid JSON-line entry to the log file
- Happy path: log entry contains all required fields
- Edge case: `output_summary` truncated to 200 chars when response is long
- Happy path: `audit_id` is a valid UUID4 string
- Error path: logging failure does not raise — swallowed silently (audit must not break the main path)

**Verification:**
- `logs/agent-audit.log` is created on first call
- Log entries are parseable as JSON
- `USE_DEERFLOW=false` is the default; existing behavior unchanged

---

## Phase 2 — DeerFlow Integration Layer

- [x] **Unit 4: Set up DeerFlow reference repo and harness dependency**

**Goal:** Clone the DeerFlow reference repo outside the numina project, install the harness package as a pinned editable dependency in `agent/`, and verify the import works.

**Requirements:** R1, R2

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Modify: `agent/pyproject.toml` (add deerflow harness dependency)
- Create: `agent/deerflow_config/base/config.yaml` (DeerFlow base config template)
- Create: `agent/deerflow_config/dev/config.yaml` (dev overlay)
- Create: `agent/deerflow_config/prod/config.yaml` (prod overlay)
- Create: `agent/deerflow_config/agents/family-finance-agent/profile.yaml`
- Modify: `agent/Dockerfile` (install harness from pinned path/commit)
- Test: `agent/tests/unit/test_deerflow_import.py`

**Approach:**
- Reference repo: `../deer-flow-reference/` (cloned outside numina, not committed)
- **Version pinning (required):** Record the exact commit SHA of the harness in `agent/deerflow_config/HARNESS_VERSION` (e.g., `abc1234`). The vendor copy step must verify the checked-out SHA matches before copying. A CI check must fail if the vendored copy's SHA does not match `HARNESS_VERSION`. This prevents silent behavior changes from upstream updates.
- Add to `.gitignore`: `../deer-flow-reference/` note in `agent/README.md`
- `pyproject.toml`: add `deerflow-harness = {path = "../deer-flow-reference/backend/packages/harness", editable = true}` under `[tool.uv.sources]` or equivalent
- **Vendor automation (required):** Create `agent/scripts/vendor-harness.sh` that: (1) checks `../deer-flow-reference/` exists, (2) verifies the current commit SHA matches `HARNESS_VERSION`, (3) copies the harness package into `agent/vendor/deerflow-harness/`. Reference this script in the Dockerfile comment and README. Any developer who runs `docker build` without running this script first gets a clear error, not a silent missing-file failure.
- `Dockerfile`: The reference clone is outside the numina repo (`../deer-flow-reference/`), so it cannot be `COPY`-ed directly. Solution: run `scripts/vendor-harness.sh` as a pre-build step, then `COPY vendor/deerflow-harness /opt/deerflow-harness && pip install /opt/deerflow-harness`. Document this in the upgrade playbook.
- **Harness API spike (required before Unit 5):** Before writing any adapter code, verify the harness package exposes `DeerFlowClient`, `client.stream()`, and `RunnableConfig` with the expected signatures. Document the actual public API surface in `agent/deerflow_config/HARNESS_API.md`. If `RunnableConfig` is not available, document the actual API key injection mechanism.
- `base/config.yaml`: model config (reads from env `$AI_PROVIDER`, `$AI_API_KEY`), checkpointer (SQLite at `/app/data/deerflow-checkpoints.db`), memory (at `/app/data/deerflow-memory.json`), sandbox (`allow_host_bash: false`), skills path (`/app/skills`)
- `prod/config.yaml`: overrides memory `max_facts: 50`, `fact_confidence_threshold: 0.8`
- `agents/family-finance-agent/profile.yaml`: agent name, description, available skill groups, model override
- **Data lifecycle (required):** `deerflow-memory.json` facts must be scoped by `family_id`. A family deletion event must purge all associated facts. Define a TTL for checkpoint records in `deerflow-checkpoints.db` (e.g., delete threads older than 30 days). Document whether these files are included in backups and who has read access at rest. `AI_API_KEY` must never appear in application logs, error messages, or audit entries — document the secret management strategy (Docker secrets, `.env` excluded from VCS, or equivalent).
- **`allow_host_bash: false` is a hard system-level constraint** — individual SKILL.md files must not be able to override it. Clarify in the config whether this is enforced at the harness level or only as a default. If skills can opt into bash, require a security review gate before deployment.

**Patterns to follow:**
- `agent/pyproject.toml` for existing dependency format
- `agent/Dockerfile` for existing build pattern

**Test scenarios:**
- Happy path: `from deerflow.client import DeerFlowClient` imports without error
- Happy path: `DeerFlowClient(config_path=...)` instantiates with base config
- Error path: missing `config.yaml` raises a clear error at instantiation, not at first call
- Happy path: `config.yaml` reads model API key from environment variable (not hardcoded)

**Verification:**
- `python -c "from deerflow.client import DeerFlowClient; print('ok')"` succeeds inside the agent container
- `agent/deerflow_config/` directory is committed to the repo
- `../deer-flow-reference/` is NOT committed (confirmed via `git status`)

---

- [x] **Unit 5: Implement DeerFlowAdapter**

**Goal:** Build the single adapter layer that wraps `DeerFlowClient` and exposes a clean async interface to the orchestrator.

**Requirements:** R1, R2

**Dependencies:** Unit 4

**Files:**
- Create: `agent/services/deerflow_adapter/__init__.py`
- Create: `agent/services/deerflow_adapter/adapter.py`
- Create: `agent/services/deerflow_adapter/client_factory.py`
- Create: `agent/services/deerflow_adapter/exceptions.py`
- Test: `agent/tests/unit/test_deerflow_adapter.py`
- Test: `agent/tests/integration/test_deerflow_adapter_integration.py`

**Approach:**
- `client_factory.py`: `get_deerflow_client(config_path: str) -> DeerFlowClient` — singleton, created once at startup, stored in app state
- `adapter.py`: `DeerFlowAdapter` class with:
  - `async def dispatch(skill_name: str, context: RedactedContext, thread_id: str) -> str` — wraps `client.stream()` in `run_in_executor` using a **dedicated bounded `ThreadPoolExecutor(max_workers=4)`** (not the default pool), collects all AI text events, returns final string
  - `async def stream_dispatch(skill_name: str, context: RedactedContext, thread_id: str) -> AsyncGenerator[str, None]` — yields text deltas for future streaming use
  - Timeout: 120s (configurable via `DEERFLOW_TIMEOUT_SECONDS` env var)
  - An `asyncio.Semaphore(4)` guards concurrent calls to match the executor pool size — prevents queue buildup beyond the pool capacity
  - The decrypted API key is injected via `RunnableConfig` model config, never embedded in the context string passed to DeerFlow
- `exceptions.py`: `DeerFlowError`, `DeerFlowTimeoutError`, `DeerFlowSkillNotFoundError`
- No business logic in adapter — only protocol translation (sync→async, StreamEvent→str)
- **SQLite checkpointer concurrency**: `asyncio.Semaphore(4)` allows up to 4 concurrent holders and does NOT serialize SQLite writes. Use a separate `asyncio.Lock` (or `Semaphore(1)`) exclusively for checkpointer writes, OR configure the SQLite checkpointer in WAL mode with a retry/timeout and document that concurrent writes are handled at the DB layer. Clarify which approach is chosen before implementation.
- **`RunnableConfig` verification (required):** After implementing the adapter, run a test that captures all strings passed to the LLM (via mock) and asserts the `AI_API_KEY` does not appear in any of them. This converts an assumed security property into a tested invariant. If `RunnableConfig` is not available in the installed harness version, document the actual injection mechanism from `HARNESS_API.md` (Unit 4 spike).

**Patterns to follow:**
- `agent/core/backend_client.py` for async HTTP client pattern
- `agent/core/llm.py` for existing LLM client pattern (to replace)

**Test scenarios:**
- Happy path: `dispatch()` returns a non-empty string when DeerFlow responds
- Happy path: `dispatch()` with unknown skill name raises `DeerFlowSkillNotFoundError`
- Error path: DeerFlow raises exception → `DeerFlowError` is raised (not raw DeerFlow exception)
- Error path: DeerFlow takes > timeout → `DeerFlowTimeoutError` is raised
- Integration: `dispatch()` with a real `DeerFlowClient` instance and base config returns a string response

**Verification:**
- `DeerFlowAdapter` never imports DeerFlow internals beyond `DeerFlowClient` and `StreamEvent`
- No DeerFlow imports exist outside `services/deerflow_adapter/`

---

- [x] **Unit 6: Implement PolicyGuard**

**Goal:** Enforce family admin capability switches before any dispatch. Reject requests for disabled capabilities without reaching DeerFlow or the legacy path.

**Requirements:** R5

**Dependencies:** Unit 3

**Files:**
- Create: `agent/services/policy_guard.py`
- Create: `agent/schemas/policy.py` (CapabilityPolicy, PolicyDecision)
- Test: `agent/tests/unit/test_policy_guard.py`

**Approach:**
- `CapabilityPolicy`: Pydantic model with `ai_enabled: bool`, `allowed_capabilities: list[str]`, `admin_only_capabilities: list[str]`, `member_role: str`
- `PolicyGuard.check(policy: CapabilityPolicy, capability: str) -> PolicyDecision`
- `PolicyDecision`: `allowed: bool`, `reason: str`
- Policy is derived from the AI config fetched from backend (`get_family_ai_config()` already returns `ai_enabled`)
- For now, `allowed_capabilities` defaults to all capabilities when `ai_enabled=True`; admin-only capabilities are blocked for non-admin members
- **Rate limiting (deferred to Phase 3, but plan now):** `PolicyGuard` or the `Orchestrator` should enforce a per-family (or per-user) call rate limit (e.g., N calls per minute) to prevent API cost exhaustion. The `asyncio.Semaphore(4)` protects the checkpointer but does not bound per-user request rates. Add this as a deferred requirement for the plan that enables `USE_DEERFLOW` in production.

**Patterns to follow:**
- `agent/routers/report.py` for existing inline token check pattern (to replace with PolicyGuard)

**Test scenarios:**
- Happy path: `ai_enabled=True`, capability in allowed list → `PolicyDecision(allowed=True)`
- Error path: `ai_enabled=False` → `PolicyDecision(allowed=False, reason="AI功能未启用")`
- Error path: capability not in `allowed_capabilities` → `PolicyDecision(allowed=False, reason="该功能不可用")`
- Error path: admin-only capability requested by non-admin member → `PolicyDecision(allowed=False, reason="仅管理员可使用")`
- Edge case: empty `allowed_capabilities` list → all capabilities blocked

**Verification:**
- `PolicyGuard.check()` never calls backend or LLM — pure in-memory logic
- All 4 scenarios above covered by unit tests

---

- [x] **Unit 7: Implement OutputMapper and AgentResponse schema**

**Goal:** Define the stable domain output schema and implement the mapper that transforms DeerFlow raw output (or legacy service output) into `AgentResponse`.

**Requirements:** R8

**Dependencies:** Unit 5

**Files:**
- Create: `agent/schemas/response.py` (AgentResponse and all sub-types)
- Create: `agent/services/output_mapper.py`
- Test: `agent/tests/unit/test_output_mapper.py`
- Test: `agent/tests/unit/test_response_schema.py`

**Approach:**
- `AgentResponse` Pydantic model with fields: `capability`, `summary`, `scorecards`, `risk_flags`, `recommendations`, `followup_actions`, `disclaimers`, `ui_blocks`, `needs_confirmation`, `rule_based_findings`, `ai_inferences`, `fallback_used`, `audit_id`
- Sub-types: `Scorecard(name, score, max_score, label, color)`, `RiskFlag(level, title, description)`, `Recommendation(priority, title, body, action_type)`, `Finding(source, content, confidence)`, `UIBlock(block_type, data)`
- `OutputMapper.from_deerflow(raw: str, capability: str, audit_id: str) -> AgentResponse`: parses DeerFlow text output (attempts JSON parse, falls back to summary-only)
- `OutputMapper.from_legacy(legacy_dict: dict, capability: str, audit_id: str) -> AgentResponse`: wraps existing service dict output in `AgentResponse`
- `OutputMapper.from_error(error: Exception, capability: str, audit_id: str) -> AgentResponse`: produces a safe error response

**Patterns to follow:**
- `agent/services/health_report.py` for existing output dict structure (to wrap)
- Pydantic `BaseModel` with `model_config = {"from_attributes": True}`

**Test scenarios:**
- Happy path: `from_deerflow()` with valid JSON string produces fully populated `AgentResponse`
- Happy path: `from_deerflow()` with plain text (no JSON) produces `AgentResponse` with `summary` only
- Happy path: `from_legacy()` wraps existing health report dict into `AgentResponse`
- Happy path: `from_error()` produces `AgentResponse` with `fallback_used=True` and safe summary
- Edge case: DeerFlow output is empty string → `AgentResponse` with empty summary, no error raised
- Happy path: `AgentResponse.model_dump()` produces valid JSON (no unserializable fields)

**Verification:**
- `AgentResponse` serializes to JSON without errors for all 4 construction paths
- `fallback_used` semantics: `True` only when `from_error()` is called (DeerFlow was attempted and failed, and legacy ran as emergency fallback), or when `from_legacy()` is called *after* a `DeerFlowError`. When `USE_DEERFLOW=False`, the legacy path is the normal path — `fallback_used` must be `False`.
- `deerflow_attempted` field in `AuditEntry` (not in `AgentResponse`): `True` only when `USE_DEERFLOW=True` and a DeerFlow call was initiated. This gives operators a clean signal: `deerflow_attempted=True, fallback_used=True` = real DeerFlow failure; `deerflow_attempted=False` = feature was off. Without this distinction, the audit log cannot answer "how often did DeerFlow fail when it was enabled?"
- `FallbackEngine.run()` must accept an `is_deerflow_fallback: bool` parameter so `OutputMapper.from_legacy()` can set `fallback_used` correctly for both call sites (normal legacy path vs. post-DeerFlow-failure path).

---

- [x] **Unit 8: Implement Orchestrator and wire feature flag**

**Goal:** Build the central dispatch coordinator that routes requests through PolicyGuard → PIIRedactor → DeerFlow or Legacy → OutputMapper → AuditLogger.

**Requirements:** R1, R3, R7, R10

**Dependencies:** Units 2, 3, 5, 6, 7

**Files:**
- Create: `agent/services/orchestrator.py`
- Create: `agent/services/fallback_engine.py`
- Modify: `agent/routers/report.py` (wire orchestrator)
- Modify: `agent/routers/liability.py` (wire orchestrator)
- Modify: `agent/routers/chat.py` (wire orchestrator)
- Test: `agent/tests/unit/test_orchestrator.py`
- Test: `agent/tests/integration/test_orchestrator_integration.py`

**Approach:**
- `Orchestrator.dispatch(capability: str, family_context: FamilyContext, policy: CapabilityPolicy) -> AgentResponse`:
  1. `PolicyGuard.check()` → 403 if blocked
  2. `PIIRedactor.redact()` → `RedactedContext`
  3. If `USE_DEERFLOW=True`: `DeerFlowAdapter.dispatch()` → `OutputMapper.from_deerflow()`; on `DeerFlowError` → `FallbackEngine.run()`
  4. If `USE_DEERFLOW=False`: `FallbackEngine.run()` directly
  5. `AuditLogger.log_call()`
  6. Return `AgentResponse`
- `FallbackEngine.run(capability: str, redacted_context: RedactedContext, is_deerflow_fallback: bool = False) -> AgentResponse`: calls the appropriate existing service and wraps result via `OutputMapper.from_legacy(fallback_used=is_deerflow_fallback)`. Catch **known** exception types from the legacy path (`LLMError`, `BackendClientError`, `ValueError`, `KeyError`) — if the legacy service raises one of these, return a hardcoded safe `AgentResponse` (empty scorecards, generic disclaimer, `fallback_used=True`). Let unexpected exceptions (`AttributeError`, `TypeError`, `ImportError`) propagate to the top-level handler so programming errors are visible, not silently swallowed. This is the final backstop for expected failures only.
- Routers: replace inline service calls with `orchestrator.dispatch()`; keep request/response JSON shapes identical to current
- Scheduler path: `agent/scheduler.py` calls service functions directly. When `USE_DEERFLOW=true`, the scheduler must construct a synthetic `FamilyContext` per family and call `orchestrator.dispatch()` with an explicit `timeout_seconds` budget (recommended: 60s, shorter than `DEERFLOW_TIMEOUT_SECONDS` to avoid blocking the scheduler thread pool). **APScheduler runs jobs in a `ThreadPoolExecutor` by default — calling `asyncio.wait_for()` from a scheduler thread with no running event loop raises `RuntimeError`.** Use `AsyncIOScheduler` so jobs run natively as coroutines, OR capture the FastAPI event loop at startup and use `asyncio.run_coroutine_threadsafe(orchestrator.dispatch(...), loop)`. Document which approach is chosen. The scheduler must: (a) authenticate using `AGENT_INTERNAL_TOKEN`, (b) enumerate families from the backend one at a time (not batch), (c) skip and log a warning if `FamilyContext` fetch fails for a family rather than aborting the entire run, (d) scope each `FamilyContext` to exactly one `family_id` validated against the database before dispatch to prevent cross-family data leakage.

**Patterns to follow:**
- `agent/routers/report.py` for existing router pattern
- `agent/services/health_report.py` for existing service call pattern

**Test scenarios:**
- Happy path: `USE_DEERFLOW=False` → orchestrator calls fallback, returns `AgentResponse` with `fallback_used=False` (legacy is the normal path, not a fallback)
- Happy path: `USE_DEERFLOW=True`, DeerFlow succeeds → returns `AgentResponse` with `fallback_used=False`
- Error path: `USE_DEERFLOW=True`, DeerFlow raises `DeerFlowError` → fallback runs, returns `AgentResponse` with `fallback_used=True`
- Error path: policy blocks capability → `HTTPException(403)` raised before any LLM call
- Integration: full dispatch cycle with mocked DeerFlow client produces valid `AgentResponse`
- Integration: full dispatch cycle with `USE_DEERFLOW=False` produces same shape as current endpoint response

**Verification:**
- All 7 existing agent endpoints return valid JSON after orchestrator wiring
- `USE_DEERFLOW=false` produces responses identical in shape to pre-upgrade responses
- `AuditLogger` writes one entry per dispatch call

---

## Phase 3 — Domain Skills

- [x] **Unit 9: Define custom skills as SKILL.md files**

**Goal:** Create the 4 family finance domain skills as structured `SKILL.md` files in `agent/skills/custom/`.

**Requirements:** R9

**Dependencies:** Unit 4, Unit 7

**Note:** Skills must be written *after* `OutputMapper` (Unit 7) so that each skill's output JSON structure matches what `OutputMapper.from_deerflow()` expects to parse. The skill's output schema and the mapper's parsing logic must be co-designed.

**Files:**
- Create: `agent/skills/custom/family-asset-checkup/SKILL.md`
- Create: `agent/skills/custom/family-liability-review/SKILL.md`
- Create: `agent/skills/custom/fixed-asset-followup/SKILL.md`
- Create: `agent/skills/custom/family-finance-insight-planner/SKILL.md`

**Approach:**

Each `SKILL.md` must define:
- `name`, `description` (trigger phrases for DeerFlow skill selection)
- `allowed-tools`: start with no tools (pure reasoning); add `bash` only if scripts are needed
- Applicable scenarios and trigger conditions
- Input constraints (what data is expected in context)
- Output structure (JSON schema the skill should produce)
- Boundary limits (what the skill must NOT do: no investment advice, no loan commitments)
- Risk expression rules (use hedged language: "观察到", "建议关注", not "确定", "必须")
- Uncertainty expression (always include confidence level and data limitations)

`family-asset-checkup`: covers asset overview, liability health, liquidity, concentration risk, budget pressure, actionable suggestions, items needing confirmation, disclaimer.

`family-liability-review`: covers interest rate pressure, repayment pressure, short/medium/long-term structure, debt risk labels, conservative suggestions, uncertainty markers.

`fixed-asset-followup`: covers property/vehicle/durables tracking, anomaly flags, maintenance reminders, insurance reminders, depreciation/holding cost reminders, rule vs AI distinction.

`family-finance-insight-planner`: deep research planner — decomposes complex questions (asset allocation risk, debt structure optimization, holding cost analysis, long-term health) into sub-tasks for DeerFlow planning mode.

**Test scenarios:**
- Happy path: each `SKILL.md` is valid YAML frontmatter + Markdown (parseable)
- Happy path: `DeerFlowClient` can load each skill without error
- Happy path: skill description contains trigger phrases that match the capability name
- Edge case: skill with no `allowed-tools` loads correctly (defaults to no tool access)

**Verification:**
- All 4 skills appear in `DeerFlowClient.list_skills()` output
- Each skill's `SKILL.md` contains all 7 required sections (scenario, trigger, input, output, limits, risk rules, uncertainty)

---

## Phase 4 — Tests and Documentation

- [x] **Unit 10: Golden cases and integration test suite**

**Goal:** Add golden case tests that verify end-to-end output shape for each capability, and integration tests that run the full dispatch cycle.

**Requirements:** R11

**Dependencies:** Units 8, 9

**Files:**
- Create: `agent/tests/golden/health_report_golden.json`
- Create: `agent/tests/golden/liability_advice_golden.json`
- Create: `agent/tests/golden/asset_suggest_golden.json`
- Create: `agent/tests/integration/test_full_dispatch.py`
- Create: `agent/tests/conftest.py` (shared fixtures: mock backend client, mock DeerFlow client)

**Approach:**
- Golden cases: capture expected `AgentResponse` JSON for each capability with known input; assert: (a) all required fields present and non-null, (b) `fallback_used=False` on the DeerFlow path and `fallback_used=True` on the error path, (c) semantic invariants — e.g., `len(scorecards) >= 1` for report/liability, `len(recommendations) >= 1` for suggest, `len(disclaimers) >= 1` for all capabilities. Shape-only assertions are insufficient — golden cases exist to catch semantic regressions where the response is structurally valid but financially meaningless.
- Integration tests: use `httpx.AsyncClient` against a test FastAPI app with mocked backend client and mocked DeerFlow client
- `conftest.py`: `mock_backend_client` fixture returns canned data; `mock_deerflow_client` fixture returns a fixed string response

**Test scenarios:**
- Happy path: `POST /report/generate` with mock data returns `AgentResponse` with all required fields
- Happy path: `POST /liability/analyze` returns `AgentResponse` with `scorecards` and `risk_flags`
- Happy path: `POST /chat/ask` returns `AgentResponse` with non-empty `summary`
- Error path: `POST /report/generate` with DeerFlow mock raising exception returns `AgentResponse` with `fallback_used=True`
- Happy path: `USE_DEERFLOW=false` produces same field set as `USE_DEERFLOW=true`

**Verification:**
- `uv run pytest agent/tests/ -v` passes all tests
- Golden case files committed to repo

---

- [x] **Unit 11: Documentation — README, upgrade playbook, rollback guide**

**Goal:** Write the three required documentation files.

**Requirements:** R12

**Dependencies:** Units 1–10

**Files:**
- Create: `agent/README.md`
- Create: `docs/agent-deerflow-migration.md`
- Create: `docs/agent-upgrade-playbook.md`

**Approach:**

`agent/README.md`:
- Architecture overview (diagram of dispatch flow)
- Directory structure explanation
- How to run locally (with and without DeerFlow)
- Environment variables reference
- How to add a new skill
- How to enable/disable DeerFlow via feature flag

`docs/agent-deerflow-migration.md`:
- What changed from the old agent to the new one
- File-by-file migration notes
- Known bugs fixed
- New capabilities added
- What was preserved unchanged

`docs/agent-upgrade-playbook.md`:
- How to upgrade DeerFlow to a new commit SHA
- How to verify the upgrade works
- How to roll back (set `USE_DEERFLOW=false`, redeploy)
- How to judge whether rollback is needed (error rate, fallback rate in audit logs)
- How to restore old config
- Monitoring: what to watch in `logs/agent-audit.log`

**Test scenarios:**
- Test expectation: none — documentation files; verified by human review

**Verification:**
- All three files exist and are non-empty
- `agent/README.md` contains the dispatch flow diagram
- `docs/agent-upgrade-playbook.md` contains explicit rollback steps

---

## Implementation Dependency Graph

```
Unit 1 (bug fixes)
    │
    ├──► Unit 2 (PIIRedactor)
    │        │
    │        └──► Unit 8 (Orchestrator) ◄──────────────────┐
    │                                                        │
    ├──► Unit 3 (AuditLogger + feature flag)                │
    │        │                                              │
    │        └──► Unit 8 (Orchestrator)                    │
    │                                                        │
    └──► Unit 4 (DeerFlow setup)                           │
             │                                              │
             ├──► Unit 5 (DeerFlowAdapter) ──────────────► Unit 8
             │                                              │
             ├──► Unit 6 (PolicyGuard) ──────────────────► Unit 8
             │                                              │
             ├──► Unit 7 (OutputMapper) ──────────────────► Unit 8
             │        │                                     │
             │        └──► Unit 9 (Skills) ────────────────┘                          │
                                                            │
                                          Unit 8 ──────► Unit 10 (Tests)
                                                            │
                                                        Unit 10 ──► Unit 11 (Docs)
```

Units 2, 3, 4 can be worked in parallel after Unit 1.
Units 5, 6, 7 can be worked in parallel after Unit 4. Unit 9 requires Unit 7 (skills must co-design output schema with OutputMapper).
Unit 8 requires Units 2, 3, 5, 6, 7.
Unit 10 requires Units 8 and 9 (integration tests must exercise skill dispatch paths).
Unit 11 is sequential after Unit 10.

---

## Open Decisions (resolve before enabling USE_DEERFLOW in production)

1. ✅ **DeerFlow harness interface** — `client.stream()` is a **sync generator**. `run_in_executor` wrapping in `DeerFlowAdapter` is correct and necessary. `RunnableConfig` is available from `langchain_core.runnables`. Documented in `agent/deerflow_config/HARNESS_API.md`.

2. ✅ **SQLite checkpointer concurrency strategy** — Use a separate `asyncio.Lock` (`_CHECKPOINTER_LOCK`) for checkpointer writes. `Semaphore(4)` does NOT serialize writes. Implemented in `adapter.py`. Documented in `HARNESS_API.md`.

3. ✅ **APScheduler async bridge** — `AsyncIOScheduler` already used in `scheduler.py`. Jobs run as native coroutines on the FastAPI event loop. Dispatch contract (per-family scoping, 60s timeout, skip-on-failure) documented in `scheduler.py` module docstring.

4. ✅ **`USE_DEERFLOW` production enablement trigger** — Defined in `docs/plans/2026-04-11-002-feat-deerflow-production-enablement-plan.md`. Requires 7-day shadow-mode review + 3-day staging validation + rate limiting + data lifecycle verification.

5. ✅ **Rate limiting** — Spec defined in production enablement plan (OD-5). Per-family sliding window, 20 calls/hour default, `AGENT_RATE_LIMIT_PER_FAMILY_PER_HOUR` env var. Implementation deferred to the plan that enables `USE_DEERFLOW` in production.

6. ✅ **Data subject deletion** — Spec defined in production enablement plan (OD-6). Requires `DELETE /internal/family/{family_id}/data` endpoint + daily checkpoint TTL purge job. Implementation deferred to production enablement plan.

7. ✅ **Audit log volume** — `agent_logs` named Docker volume added to `docker-compose.yml`, mounted at `/app/logs`. Logs persist across container restarts. Access control and backup strategy documented in production enablement plan (OD-7).
