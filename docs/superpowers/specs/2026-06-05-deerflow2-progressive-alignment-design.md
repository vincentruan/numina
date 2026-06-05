---
title: DeerFlow 2.0 Progressive Alignment
type: refactor
status: active
date: 2026-06-05
origin: brainstorming session — analysis of agent module vs DeerFlow 2.0 framework design practices
---

# DeerFlow 2.0 Progressive Alignment — Agent Module Optimization

## Summary

Three-phase progressive alignment of the Numina agent module with DeerFlow 2.0 framework design practices. Phase 1 fixes correctness issues (zero risk). Phase 2 eliminates structural bottlenecks (medium risk, requires testing). Phase 3 integrates unused DeerFlow capabilities (low risk, incremental).

---

## Problem Frame

The agent module was built on the DeerFlow 2.0 harness but has drifted from its standard paths in eight specific ways:

| # | Drift | Impact |
|---|-------|--------|
| D1 | Global `_init_lock` + `reload_app_config()` serialises all family requests | Concurrent families blocked; streaming throughput capped |
| D2 | `_build_message()` JSON-encodes skill+context instead of using natural language trigger phrases | DeerFlow skill auto-routing disabled; harness receives opaque JSON |
| D3 | All non-chat capabilities pre-fetch full family data via `_build_context()` | High token cost and latency; agent receives data it may not need |
| D4 | Dual streaming paths (raw text + NDJSON) with ~200 lines of duplicated logic | Maintenance burden; divergent retry/circuit-breaker behavior |
| D5 | ~~Non-chat `agent_dispatch.py` path missing `phase.thinking` and `tool.call`/`tool.result` events~~ **Resolved** — `_chunk_to_event_lines()` already emits all event types; `agent_dispatch.py` also emits them | ~~Frontend cannot differentiate tool types~~ Already working |
| D6 | `thinking_enabled` passed to `stream()` — initially believed to be ignored, but DeerFlow `stream(**kwargs)` routes it to `_get_runnable_config()` as a per-call override | Two-level thinking control (init-time default + per-request override) works correctly; code is not buggy but the two-level design should be documented |
| D7 | Frontend uses hardcoded template suggestions instead of DeerFlow suggestions API | Lower quality follow-up suggestions |
| D8 | DeerFlow Gateway API (models/skills/memory/threads management) not utilized | No runtime model/skill introspection; no thread lifecycle management |

---

## Success Criteria

| ID | Criterion | Acceptance |
|----|-----------|------------|
| SC1 | `stream()` `thinking_enabled` kwarg documented as per-call override | HARNESS_API.md documents two-level thinking control; code comment added |
| SC2 | Single NDJSON streaming path — `stream_dispatch()` raw-text method removed | grep confirms exactly one `stream_dispatch` method in orchestrator.py, producing NDJSON; all `/stream` router endpoints removed or migrated |
| SC3 | No global lock on concurrent family requests | Two families can stream simultaneously without blocking |
| SC4 | All capabilities use MCP for data access (chat already does) | `_build_context()` only called as fallback, not default |
| SC5 | Skill dispatch uses natural language `[SKILL:xxx]` format | `_build_message()` replaced with `_build_prompt()` pattern; LLM skill selection accuracy validated |
| SC6 | Gateway API proxy endpoints verified | `GET /internal/gateway/models`, `PUT /internal/gateway/skills/{name}`, `DELETE /internal/gateway/threads/{id}` return 200 |
| SC7 | Suggestions API integrated | Chat responses include LLM-generated follow-up suggestions (with template fallback) |

---

## Phase 1: Corrections (Zero Risk)

### U1.1 — ~~Remove `thinking_enabled` from `stream()` calls~~ — NOT A BUG

**Drift addressed:** D6 (reclassified — not a drift)

**Finding from review:** DeerFlow `stream()` accepts `**kwargs` which flow into `_get_runnable_config()`. `thinking_enabled` passed as a kwarg overrides the init-time default per-request. This is intentional two-level control: init-time sets the default, per-call overrides it. Removing it would break the per-request thinking toggle.

**Revised action:** Keep `thinking_enabled=enable_thinking` in `stream()` calls. Instead, document the two-level design in `HARNESS_API.md` and add a code comment clarifying that `stream()` kwargs are per-call overrides, not dead code.

---

### U1.2 — Deprecate `stream_dispatch()` raw text path

**Drift addressed:** D4

**Files:**
- `server/apps/agent/services/orchestrator.py`
- Any router files that call `orchestrator.stream_dispatch()`

**Change:** Remove `stream_dispatch()` method (lines 314-633) and any endpoints that use `text/plain` streaming. All frontend consumers already use NDJSON.

**Scope check:** Before removing, verify which routers still have raw-text `/stream` endpoints and which have NDJSON `/events` endpoints:
- `alerts.py` — has BOTH `/stream` (raw text, calls `stream_dispatch()`) AND `/events` (NDJSON)
- `allocation.py` — has BOTH `/stream` (raw text) AND `/events` (NDJSON)
- `chat.py` — NDJSON only (`stream_dispatch_events()`)
- `disposal.py` — has BOTH `/stream` (raw text) AND `/events` (NDJSON)
- `liability.py` — has BOTH `/stream` (raw text) AND `/events` (NDJSON)
- `report.py` — NDJSON only (`/generate` + `/events`, no `/stream`)
- `spending_leak.py` — has BOTH `/stream` (raw text) AND `/events` (NDJSON)
- `time_machine.py` — has ONLY `/stream` (raw text), NO `/events` endpoint — **must add NDJSON variant first**

If any endpoint only has a raw-text variant, add an NDJSON variant first.

**After removal:** Rename `stream_dispatch_events()` → `stream_dispatch()` (the simpler name is now unambiguous).

**Verification:** `grep -n "def stream_dispatch" orchestrator.py` returns exactly one method. Frontend typecheck passes.

---

### U1.3 — Verify `thinking_enabled` construction-time source

**Drift addressed:** D6 (completeness check)

**Files:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`

**Analysis:** `get_family_adapter()` constructs `DeerFlowClient` with `thinking_enabled=bool(ai_config.get("thinking_supported", False))` (line ~645). This is the provider-level capability flag, which is correct — `thinking_enabled` at construction time enables the model's thinking infrastructure. The per-skill `thinking` flag controls whether the orchestrator requests thinking in the stream — but since `thinking_enabled` is init-time, the client is already configured for the provider's capability.

**Cache key implication:** If two skills on the same provider differ in their `thinking` flag but both use `(subagent_enabled=False, plan_mode=False)`, they share one client instance. The client has `thinking_enabled=True` (provider supports it). The orchestrator's `enable_thinking` logic decides whether to pass thinking context in the message. This is correct — the client is "capable of thinking" and the per-request flag controls whether thinking is actually used.

**Conclusion:** No code change needed. Document this invariant.

**Verification:** Add a comment in `family_adapter_cache.py` explaining the provider-capability vs per-request distinction.

---

## Phase 2: Decoupling (Medium Risk)

### U2.1 — Eliminate `_init_lock` global serialization

**Drift addressed:** D1

**Root cause:** DeerFlow's `get_app_config()` returns a module-level global singleton. `reload_app_config(path)` resets this singleton. Concurrent family requests overwrite each other's config, forcing Numina to serialize with `_init_lock`.

**Approach: DeerFlow native ContextVar config injection**

DeerFlow's `app_config.py` already has a ContextVar-based config injection mechanism:
- `_current_app_config: ContextVar[AppConfig | None]` — per-context config override
- `push_current_app_config(config)` — set config for the current context
- `pop_current_app_config()` — restore previous config
- `get_app_config()` already checks `_current_app_config.get()` first (line 368-370)

This eliminates the need for monkey-patching or thread-local storage:

1. In `_produce()` (runs in thread pool):
   - Call `push_current_app_config(parsed_config)` before `self._client.stream()`
   - Call `pop_current_app_config()` in a `finally` block after stream completes
   - Remove `_init_lock` acquisition from `_produce()`
   - Remove `os.environ["DEER_FLOW_CONFIG_PATH"]` manipulation
   - Remove `reload_app_config()` calls from `_produce()`

2. In `get_family_adapter()`:
   - Remove `_init_lock` acquisition around `DeerFlowClient()` construction
   - Keep `DeerFlowClient(config_path=...)` call — the constructor reads config once

3. Remove `_init_lock` from `adapter.py` module level

**Caveat:** Python ContextVars propagate to new threads on creation, but `_produce()` runs in a ThreadPoolExecutor where threads are reused. The `push/pop` must happen *inside* `_produce()` (not in the calling async code) to ensure the ContextVar is visible to DeerFlow code running in the same thread. Test this explicitly.

**Fallback:** If ContextVar propagation across ThreadPoolExecutor thread reuse proves unreliable, fall back to forking the vendor harness with a `from_config_dict()` factory method that accepts an explicit config object.

**Concurrency model after change:**
- `_cache_lock` — still needed for cache mutation (short hold, no I/O)
- `_CHECKPOINTER_LOCK` — still needed for SqliteSaver write serialization
- `_init_lock` — REMOVED
- `_semaphore` — still bounds concurrent DeerFlow dispatches

**Verification:** Two families can stream simultaneously without blocking. Unit test: mock two threads calling `_produce()` with different configs concurrently — assert both complete without serialization.

---

### U2.2 — All capabilities use MCP for data access

**Drift addressed:** D3

**Current state:** Chat uses `ChatAdapter` which injects `numina-family-data` MCP server. Other 7 capabilities use `_build_context()` to pre-fetch all family data.

**Approach:**

1. Register MCP tools for each data type currently fetched in `_build_context()`:
   - `get_liabilities` — fetch liabilities
   - `get_dashboard_overview` — fetch overview metrics
   - `get_dashboard_allocation` — fetch allocation breakdown
   - `get_dashboard_trend` — fetch trend data
   - `get_low_usage_assets` — fetch low-usage asset list
   - `get_assets` — fetch assets (currently always `[]`, but MCP tool ready for when backend adds endpoint)
   - `get_members` — fetch members (currently always `[]`)

2. Modify `orchestrator._stream_dispatch_event_lines()` to inject the same MCP server config as `ChatAdapter` for all capabilities (not just chat).

3. Remove the `_build_context()` call from the non-chat branch. Instead, pass a minimal context (family_id + free_text) and let the DeerFlow agent decide what data it needs via MCP tools.

4. Keep `_build_context()` as a documented fallback path — if MCP is unavailable, the orchestrator can pre-fetch and inject context.

**Impact on prompt/skill files:** Skill prompts need to be updated to instruct the agent to use MCP tools for data access rather than expecting pre-loaded context.

**Token savings estimate:** Current `_build_context()` injects ~2-4K tokens of context per request. MCP on-demand fetch reduces this to ~200-500 tokens for the skill prompt, with additional tokens only when tools are called.

**Verification:** Non-chat capability (e.g., `alerts`) successfully calls MCP tools during execution. Token usage comparison before/after.

---

### U2.3 — Change `_build_message()` to natural language skill trigger

**Drift addressed:** D2

**Current state:** `_build_message()` outputs `{"skill": "alerts", "context": {...}, "thinking": true}` as JSON. Note: `_build_prompt()` (dead code at adapter.py:411-414) already uses the `[SKILL:xxx]` format but is not called in the streaming path.

**Important:** DeerFlow does NOT have a `trigger_phrases` routing mechanism. Skills are injected into the system prompt as a list and the LLM chooses which to invoke based on the message content. The `[SKILL:xxx]` tag helps the LLM identify the intended skill but there is no programmatic routing layer. The original SC5 ("DeerFlow trigger_phrases matching activates") is incorrect — there is no matching to activate.

**Target state:** Output natural language that helps the LLM identify and invoke the correct skill:

```
[SKILL:alerts]
用户请求：{free_text or default prompt for capability}

家庭上下文数据：
{context JSON, pretty-printed}
```

**Approach:**
1. Replace `_build_message()` with the existing `_build_prompt()` pattern (which already uses `[SKILL:xxx]`), or unify the two methods
2. Keep context data in the message (until U2.2 MCP migration completes), but format it as readable text rather than opaque JSON
3. Update `HARNESS_API.md` to document that `stream()` messages use natural language with `[SKILL:xxx]` tags, not JSON

**Verification:** DeerFlow correctly routes to the intended skill based on trigger phrase matching. Agent output quality unchanged.

---

## Phase 3: Enhancement (Low Risk)

### U3.1 — Gateway API proxy endpoints (already implemented)

**Drift addressed:** D8

**Status:** All three Gateway proxy endpoints already exist in `server/apps/agent/app/routers/gateway.py`:
- `GET /internal/gateway/models` (line 60) — proxy to DeerFlow `GET /api/models`
- `PUT /internal/gateway/skills/{name}` (line 83) — proxy to `PUT /api/skills/{name}`
- `DELETE /internal/gateway/threads/{id}` (line 113) — proxy to `DELETE /api/threads/{id}`
- `POST /internal/gateway/skill-dispatch` (line 141) — additional dispatch endpoint

All require `X-Agent-Token` header. Path parameters validated against `_SAFE_ID_PATTERN` before forwarding (SSRF prevention).

**Action:** No new code needed. Update SC6 success criteria to reference the actual paths (`/internal/gateway/*`). Verify existing tests cover these endpoints.

---

### U3.2 — Suggestions API integration

**Drift addressed:** D7

**Files:**
- `server/apps/agent/routers/chat.py` or `agent_stream.py`
- `frontend/apps/main/src/components/ai/SuggestionChips.vue`
- `frontend/apps/main/src/api/ai.ts`

**Approach:**
1. Backend: After stream ends, call DeerFlow `POST /api/threads/{id}/suggestions` to get LLM-generated follow-up suggestions
2. Backend: Include suggestions in the `capability.end` NDJSON event (new `suggestions` field)
3. Frontend: `SuggestionChips` component receives suggestions from event, falls back to template interpolation when absent
4. Fire-and-forget: suggestions generation is non-blocking; if it fails, the `capability.end` event omits the field and frontend uses template fallback

**Verification:** Chat responses occasionally include LLM-generated suggestions. When suggestions API is unavailable, template suggestions display correctly.

---

### U3.3 — Dynamic capability display via DeerFlow API

**Drift addressed:** D8 (extended)

**Files:**
- `server/apps/agent/services/capability_registry.py`
- `server/apps/agent/routers/capabilities.py`
- `frontend/apps/main/src/api/ai.ts`

**Approach:**
1. `CapabilityRegistry.get_all()` refreshes from DeerFlow `GET /api/skills` instead of only reading local `skills/*.md` files
2. Local files remain the source of truth for prompt content; DeerFlow API provides runtime status (enabled/disabled)
3. `/capabilities` endpoint merges local metadata with DeerFlow runtime status
4. Frontend can show "available" vs "disabled" status per capability

**Verification:** Disabling a skill via Gateway API is reflected in `/capabilities` response within one refresh cycle.

---

## Sequencing

```
Phase 1 (corrections):
  U1.1 (document thinking_enabled two-level design — NOT a code change)
  U1.2 (deprecate raw text path — requires adding /events to time_machine first)
  U1.3 (document thinking invariant)
  → U1.1 and U1.3 are documentation-only, parallel
  → U1.2 requires adding NDJSON endpoint to time_machine before removing stream_dispatch()

Phase 2 (decoupling):
  U2.1 (eliminate _init_lock via ContextVar) — independent
  U2.2 (MCP for all capabilities) — should precede U2.3 (context formatting will be superseded)
  U2.3 (natural language trigger) — depends on U2.2 for full value; verify existing _build_prompt() pattern
  → U2.1 and U2.2 can proceed in parallel; U2.3 should follow U2.2

Phase 3 (enhancement):
  U3.1 (Gateway API proxy — already implemented, verify only)
  U3.2 (Suggestions API) — verify DeerFlow suggestions endpoint exists before implementing
  U3.3 (Dynamic capabilities) — needs user story validation before implementation
  → U3.1 is verification only; U3.2 and U3.3 can proceed after U3.1 verification
```

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ContextVar propagation across ThreadPoolExecutor thread reuse | Medium | High | Test explicitly: push config in _produce(), verify DeerFlow reads it. Fallback: fork vendor harness with `from_config_dict()` factory |
| DeerFlow has no `trigger_phrases` routing — LLM selects skill from system prompt | N/A (confirmed) | Low | `[SKILL:xxx]` tag helps LLM identify intent; validate output quality empirically |
| MCP tool latency adds overhead vs pre-fetched context | Low | Medium | Measure p50/p95 latency before/after; keep `_build_context()` as fallback |
| Removing `stream_dispatch()` breaks `/stream` router endpoints | High | High | First add NDJSON `/events` endpoint to `time_machine.py`; then deprecate and remove all `/stream` router endpoints alongside the method |
| DeerFlow `POST /api/threads/{id}/suggestions` endpoint may not exist | Medium | Low | Verify endpoint exists in installed DeerFlow version before implementing U3.2; if absent, use local LLM call for suggestions instead |

---

## Out of Scope

- Postgres checkpointer migration (separate initiative)
- APScheduler job activation (Phase 0 constraint)
- JSONL file migration to object storage
- Frontend UI for Gateway API management (follow-up after U3.1)
- `reasoning_effort` parameter support (covered by Chat UX Fusion Plan U2)
- SubtaskCard multi-subtask visualization (covered by Chat UX Fusion Plan)
