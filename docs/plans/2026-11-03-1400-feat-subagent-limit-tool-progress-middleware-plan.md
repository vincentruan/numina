---
title: "SubagentLimit + ToolProgress Middleware - Plan"
date: 2026-11-03
type: feat
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# SubagentLimit + ToolProgress Middleware — Plan

## Goal Capsule

- **Objective:** Protect the agent runtime from subagent explosion and long-running tool hangs by introducing two config-driven DeerFlow middlewares — SubagentLimitMiddleware (T15) and ToolProgressMiddleware (T17) — that enforce bounded concurrency and tool execution health.
- **Means:** Implement both as Numina custom middleware classes injected via `DeerFlowAdapter.middlewares=[]`, activated by config keys `subagent_limit.enabled` and `tool_progress.enabled` in the per-family temp config YAML. (KTD1)
- **Execution profile:** Single PR. Both middlewares follow the same injection pattern and share test infrastructure.
- **Stop conditions:** Both middlewares pass unit tests with config on/off; no regression in existing agent dispatch tests.

## Product Contract

### Summary

Two DeerFlow agent middlewares that harden the runtime:

1. **SubagentLimitMiddleware** (T15): Caps the number of concurrent subagent tasks per run, preventing runaway task spawning that could exhaust thread pool slots or memory.
2. **ToolProgressMiddleware** (T17): Tracks tool execution duration through a state machine (ACTIVE → WARNED → BLOCKED), emitting progress events and optionally blocking tools that exceed time budgets.

Both are config-driven — toggled via boolean `enabled` flags in the per-family DeerFlow config YAML, following the established pattern of `token_budget.enabled`, `pii_redaction.enabled`, and `guardrails.enabled`.

### Problem Frame

The agent runtime has two unguarded failure modes:

1. **Subagent explosion:** When a skill enables `subagent_enabled=True`, the LLM can spawn unbounded background tasks. `FamilySubagentRegistry` tracks them but does not limit concurrency. A misbehaving skill or adversarial prompt could exhaust the `DEERFLOW_CONCURRENCY=8` thread pool.

2. **Tool hangs:** Long-running tools (e.g., `web_search` against a slow provider, large `read_file`) block their thread pool slot indefinitely. There is no visibility into tool execution duration and no mechanism to warn or block tools that exceed reasonable time budgets.

### Requirements

- R1. SubagentLimitMiddleware rejects new subagent tasks when the per-run concurrent count exceeds `subagent_limit.max_concurrent` (default: `SUBAGENT_MAX_CONCURRENT` from AgentSettings, currently 3).
- R2. SubagentLimitMiddleware is activated only when `subagent_limit.enabled: true` in the per-family config. When disabled, no overhead is added.
- R3. ToolProgressMiddleware tracks each tool execution start and completion, transitioning through states: ACTIVE (running normally) → WARNED (exceeded `warn_threshold_seconds`) → BLOCKED (exceeded `hard_stop_threshold_seconds`).
- R4. ToolProgressMiddleware emits `tool_progress` SSE events on state transitions so the frontend can display tool execution health.
- R5. ToolProgressMiddleware is activated only when `tool_progress.enabled: true` in the per-family config.
- R6. Both middlewares must not break existing dispatch when disabled (the default for both).
- R7. Both middlewares are thread-safe — they run inside DeerFlow's executor threads where tool execution happens synchronously.

### Scope Boundaries

**In scope:**
- Backend middleware classes (Python)
- Config injection in `family_adapter_cache.py`
- Base config YAML entries
- Unit tests

**Out of scope:**
- Frontend rendering of tool_progress events (already supported by existing ChainOfThought.vue)
- Changes to DeerFlow upstream harness
- Changes to `FamilySubagentRegistry` (T15 reads from it, does not modify it)
- Async file I/O (T16) or sandbox authorization (T18) — separate PRs

---

## Planning Contract

### Key Technical Decisions

KTD1. **Numina custom middleware injection, not `custom_middlewares` config.** Both middlewares are implemented as Numina-owned Python classes and passed via `DeerFlowAdapter(middlewares=[...])` — the same path TodoMiddleware uses. The `custom_middlewares` config key triggers a class-name dedup `AssertionError` in the DeerFlow harness (documented in AGENTS.md). The `middlewares=[]` init parameter is the sanctioned injection path for Numina-specific middlewares.

KTD2. **State machine for ToolProgress is middleware-local, not persisted.** The ACTIVE → WARNED → BLOCKED state lives in a per-tool-call dict inside the middleware instance. It is not persisted to DB or checkpoint. On run completion, the state is discarded. This matches the ephemeral nature of tool execution tracking — it is observable via SSE events, not queryable after the fact.

KTD3. **SubagentLimitMiddleware reads FamilySubagentRegistry for per-family counts.** Rather than maintaining a separate counter, the middleware queries `FamilySubagentRegistry.list_for_family(family_id)` to count active tasks. This reuses the existing per-family index and avoids double-bookkeeping. The middleware adds a `max_concurrent` check before each subagent spawn.

### Assumptions

- The DeerFlow harness middleware interface (`AgentMiddleware` or equivalent protocol) supports `before_tool_call` and `after_tool_call` hooks, or a similar interception point. The `NuminaGuardrailProvider` pattern (which implements a `check_tool_call` method) confirms this interface exists.
- The `middlewares=[]` parameter accepts middleware instances with any protocol the harness recognizes — the harness calls methods by name convention (duck typing).

---

## Implementation Units

### U1. SubagentLimitMiddleware class

- **Goal:** Implement the subagent concurrency limit middleware that rejects new tasks when the per-family count exceeds the configured maximum.
- **Requirements:** R1, R2, R6, R7
- **Dependencies:** None
- **Files:**
  - `server/apps/agent/services/runtime/subagent_limit_middleware.py` (create)
  - `server/tests/agent/unit/test_subagent_limit_middleware.py` (create)
- **Approach:**
  1. Create `SubagentLimitMiddleware` class with `__init__(self, max_concurrent: int, family_id: str)`.
  2. Implement a `before_subagent_spawn()` hook (or `check_tool_call()` if the harness uses that interface for subagent tools) that:
     - Calls `FamilySubagentRegistry.list_for_family(family_id)` to get current active task count
     - Returns a deny decision if count >= `max_concurrent`
     - Returns an allow decision otherwise
  3. Thread safety: `FamilySubagentRegistry` already uses `_family_index_lock` for its operations, so reads are thread-safe.
- **Patterns to follow:** `NuminaGuardrailProvider` in `numina_guardrail_provider.py` — same middleware provider pattern with `check_tool_call()` returning a decision dataclass.
- **Test scenarios:**
  - Allow spawn when active count < max_concurrent (e.g., 2 active, max 3 → allowed)
  - Deny spawn when active count >= max_concurrent (e.g., 3 active, max 3 → denied)
  - Empty registry (0 active) → allowed
  - Different family_id isolation: family A's tasks don't count against family B's limit
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_subagent_limit_middleware.py -v`

### U2. ToolProgressMiddleware class

- **Goal:** Implement the tool execution health tracking middleware with ACTIVE → WARNED → BLOCKED state machine.
- **Requirements:** R3, R4, R5, R6, R7
- **Dependencies:** None
- **Files:**
  - `server/apps/agent/services/runtime/tool_progress_middleware.py` (create)
  - `server/tests/agent/unit/test_tool_progress_middleware.py` (create)
- **Approach:**
  1. Create `ToolProgressMiddleware` class with `__init__(self, warn_threshold_seconds: float = 30.0, hard_stop_threshold_seconds: float = 120.0)`.
  2. Maintain a `_tool_states: dict[str, ToolState]` mapping `tool_call_id → ToolState(start_time, status, tool_name)`.
  3. Implement `before_tool_call(tool_call_id, tool_name)`:
     - Record start time, set status to ACTIVE
     - Emit `tool_progress` event via the run's stream writer (if available)
  4. Implement `after_tool_call(tool_call_id, tool_name, success)`:
     - Calculate elapsed time
     - If elapsed < warn_threshold: status remains ACTIVE
     - If warn_threshold <= elapsed < hard_stop: emit WARNED event
     - If elapsed >= hard_stop: emit BLOCKED event
     - Remove from `_tool_states`
  5. Thread safety: protect `_tool_states` with a threading.Lock (same pattern as `FamilySubagentRegistry._family_index_lock`).
- **Patterns to follow:** `NuminaGuardrailProvider` for the middleware interface; `EventStreamBuilder` in `stream_events.py` for the event emission pattern.
- **Test scenarios:**
  - Tool completes within warn_threshold → ACTIVE only, no warning event
  - Tool exceeds warn_threshold but not hard_stop → WARNED event emitted
  - Tool exceeds hard_stop → BLOCKED event emitted
  - Concurrent tools tracked independently (two tools with different durations)
  - Empty tool_call_id handled gracefully
  - Lock contention under concurrent tool calls (basic sanity check)
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_tool_progress_middleware.py -v`

### U3. Config injection and wiring

- **Goal:** Wire both middlewares into the per-family config generation and adapter creation pipeline.
- **Requirements:** R2, R5, R6
- **Dependencies:** U1, U2
- **Files:**
  - `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` (modify)
  - `server/apps/agent/deerflow_config/base/config.yaml` (modify)
  - `server/tests/agent/unit/test_family_adapter_cache.py` (modify)
- **Approach:**
  1. Add `_inject_subagent_limit(config, ai_config)` function in `family_adapter_cache.py`:
     - Reads `ai_config.get("subagent_limit", {})` for per-family override
     - Writes `config["subagent_limit"] = {"enabled": True, "max_concurrent": ...}`
     - Called from `_generate_temp_config()` alongside `_inject_token_budget()`
  2. Add `_inject_tool_progress(config, ai_config)` function:
     - Reads `ai_config.get("tool_progress", {})` for per-family override
     - Writes `config["tool_progress"] = {"enabled": True, "warn_threshold_seconds": 30.0, "hard_stop_threshold_seconds": 120.0}`
  3. In `get_family_adapter()`, when creating the `NuminaDeerFlowClient`:
     - Read `subagent_limit.enabled` and `tool_progress.enabled` from the generated config
     - If enabled, instantiate the middleware and append to the `middlewares` list
     - Pass the list to `NuminaDeerFlowClient(middlewares=...)`
  4. Add default config entries in `base/config.yaml`:
     ```yaml
     subagent_limit:
       enabled: false
       max_concurrent: 3
     tool_progress:
       enabled: false
       warn_threshold_seconds: 30.0
       hard_stop_threshold_seconds: 120.0
     ```
     Default `enabled: false` ensures no behavior change until explicitly enabled.
- **Patterns to follow:** `_inject_token_budget()`, `_inject_pii_redaction()`, `_inject_guardrail()` in `family_adapter_cache.py`
- **Test scenarios:**
  - Config with `subagent_limit.enabled: true` → middleware instance created and passed to client
  - Config with `subagent_limit.enabled: false` (default) → no middleware instance
  - Config with `tool_progress.enabled: true` → middleware instance created
  - Per-family overrides from `ai_config` (e.g., different `max_concurrent`) are respected
  - Existing tests with no subagent_limit/tool_progress config → no regression
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_family_adapter_cache.py -v`

### U4. Integration test

- **Goal:** Verify both middlewares work end-to-end in the dispatch pipeline.
- **Requirements:** R1-R7
- **Dependencies:** U1, U2, U3
- **Files:**
  - `server/tests/agent/integration/test_middleware_integration.py` (create)
- **Approach:**
  1. Test that a `DeerFlowAdapter` created with both middlewares enabled dispatches correctly (mock the DeerFlow client stream).
  2. Test that SubagentLimitMiddleware correctly denies a subagent spawn when the registry has >= max_concurrent tasks for the family.
  3. Test that ToolProgressMiddleware emits `tool_progress` events during a mock tool execution.
- **Test scenarios:**
  - Adapter with both middlewares enabled → dispatches without error
  - SubagentLimitMiddleware denies spawn → adapter handles denial gracefully
  - ToolProgressMiddleware tracks a mock long-running tool → events emitted
- **Verification:** `cd server && uv run pytest tests/agent/integration/test_middleware_integration.py -v`

---

## Verification Contract

| Check | Command | Scope |
|-------|---------|-------|
| Unit tests | `cd server && uv run pytest tests/agent/unit/test_subagent_limit_middleware.py tests/agent/unit/test_tool_progress_middleware.py tests/agent/unit/test_family_adapter_cache.py -v` | U1, U2, U3 |
| Integration tests | `cd server && uv run pytest tests/agent/integration/test_middleware_integration.py -v` | U4 |
| Regression | `cd server && uv run pytest tests/agent/ -v --timeout=60` | Full agent suite |
| Lint | `cd server && uv run ruff check apps/agent/services/runtime/subagent_limit_middleware.py apps/agent/services/runtime/tool_progress_middleware.py apps/agent/services/deerflow_adapter/family_adapter_cache.py` | Changed files |
| Type check | `cd server && uv run mypy apps/agent/services/runtime/ --exclude vendor` | Runtime module |

## Definition of Done

- All four implementation units pass their verification commands
- Both middlewares default to `enabled: false` — zero behavior change for existing deployments
- Enabling either middleware via config does not break existing dispatch tests
- Config injection follows the established `_inject_*` pattern in `family_adapter_cache.py`
- No code added to `custom_middlewares` config key (KTD1)
- Experimental/abandoned code from failed approaches is removed
