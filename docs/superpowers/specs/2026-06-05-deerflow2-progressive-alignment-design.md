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
| D5 | Non-chat `agent_dispatch.py` path missing `phase.thinking` and `tool.call`/`tool.result` events | Frontend cannot differentiate tool types or show thinking animation |
| D6 | `thinking_enabled` passed to `stream()` where it is ignored (init-time only param) | Misleading code; future harness change could break silently |
| D7 | Frontend uses hardcoded template suggestions instead of DeerFlow suggestions API | Lower quality follow-up suggestions |
| D8 | DeerFlow Gateway API (models/skills/memory/threads management) not utilized | No runtime model/skill introspection; no thread lifecycle management |

---

## Success Criteria

| ID | Criterion | Acceptance |
|----|-----------|------------|
| SC1 | `stream()` called with only `(message, thread_id)` — no extra kwargs | grep confirms zero `thinking_enabled` in stream() calls |
| SC2 | Single NDJSON streaming path — `stream_dispatch()` removed | grep confirms `stream_dispatch` only exists as `stream_dispatch_events` |
| SC3 | No global lock on concurrent family requests | Two families can stream simultaneously without blocking |
| SC4 | All capabilities use MCP for data access (chat already does) | `_build_context()` only called as fallback, not default |
| SC5 | Skill dispatch uses natural language format | DeerFlow trigger_phrases matching activates |
| SC6 | Gateway API proxy endpoints available | `GET /internal/models`, `PUT /internal/skills/{name}`, `DELETE /internal/threads/{id}` return 200 |
| SC7 | Suggestions API integrated | Chat responses include LLM-generated follow-up suggestions (with template fallback) |

---

## Phase 1: Corrections (Zero Risk)

### U1.1 — Remove invalid `thinking_enabled` from `stream()` calls

**Drift addressed:** D6

**Files:**
- `server/apps/agent/services/deerflow_adapter/adapter.py`

**Change:** Two call sites in `_produce()` (lines ~316 and ~331) pass `thinking_enabled=enable_thinking` to `self._client.stream()`. DeerFlow 2.0's `stream()` signature only accepts `message` and `thread_id`. The parameter is silently ignored.

**Action:** Change both to `self._client.stream(message, thread_id=thread_id)`.

**Verification:** `grep -n "thinking_enabled" adapter.py` only shows it in `__init__` and `DeerFlowClient()` constructor calls, not in `stream()` calls.

---

### U1.2 — Deprecate `stream_dispatch()` raw text path

**Drift addressed:** D4

**Files:**
- `server/apps/agent/services/orchestrator.py`
- Any router files that call `orchestrator.stream_dispatch()`

**Change:** Remove `stream_dispatch()` method (lines 314-633) and any endpoints that use `text/plain` streaming. All frontend consumers already use NDJSON.

**Scope check:** Before removing, verify all router endpoints that call `stream_dispatch()` have an NDJSON equivalent:
- `alerts.py` `/alerts/stream` — uses `stream_dispatch_events()`
- `allocation.py` `/allocation/stream` — uses `stream_dispatch_events()`
- `chat.py` `/chat/ask/stream` — uses `stream_dispatch_events()`
- `disposal.py` `/disposal/stream` — uses `stream_dispatch_events()`
- `liability.py` `/liability/stream` — uses `stream_dispatch_events()`
- `report.py` `/report/generate/stream` — uses `stream_dispatch_events()`
- `spending_leak.py` `/spending-leak/stream` — uses `stream_dispatch_events()`
- `time_machine.py` `/time-machine/stream` — uses `stream_dispatch_events()`

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

**Approach: Thread-local config injection**

Replace the global `reload_app_config()` + `os.environ["DEER_FLOW_CONFIG_PATH"]` pattern with thread-local storage:

1. Create a thin wrapper module `services/deerflow_adapter/config_local.py`:
   - `threading.local()` holds `_local.config_path` per thread
   - `get_thread_config_path()` / `set_thread_config_path()` accessors
   - Monkey-patch `deerflow.config.app_config.get_app_config()` to read from thread-local before falling back to global

2. In `_produce()` (runs in thread pool):
   - Call `set_thread_config_path(self._config_path)` before `self._client.stream()`
   - Clear thread-local after stream completes
   - Remove `_init_lock` acquisition from `_produce()`

3. In `get_family_adapter()`:
   - Remove `_init_lock` acquisition around `reload_app_config()` + `DeerFlowClient()` construction
   - Keep `DeerFlowClient(config_path=...)` call — the constructor reads config once

4. Remove `_init_lock` from `adapter.py` module level

**Fallback:** If monkey-patching `get_app_config()` proves fragile (e.g., harness calls it at unexpected times), fall back to forking the vendor harness with a `from_config_dict()` factory method.

**Concurrency model after change:**
- `_cache_lock` — still needed for cache mutation (short hold, no I/O)
- `_CHECKPOINTER_LOCK` — still needed for SqliteSaver write serialization
- `_init_lock` — REMOVED
- `_semaphore` — still bounds concurrent DeerFlow dispatches

**Verification:** Two families can stream simultaneously without blocking. Unit test: mock two threads calling `_produce()` with different configs concurrently — assert both complete without serialization.

---

### U2.2 — All capabilities use MCP for data access

**Drift addressed:** D3

**Current state:** Chat uses `ChatAdapter` which injects `numina-family-data` MCP server. Other 8 capabilities use `_build_context()` to pre-fetch all family data.

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

**Current state:** `_build_message()` outputs `{"skill": "alerts", "context": {...}, "thinking": true}` as JSON.

**Target state:** Output natural language that activates DeerFlow's skill trigger matching:

```
[SKILL:alerts]
用户请求：{free_text or default prompt for capability}

家庭上下文数据：
{context JSON, pretty-printed}
```

**Prerequisite:** Verify DeerFlow's `trigger_phrases` matching works with `[SKILL:xxx]` tags in the message. If it only matches against the skill file's `trigger_phrases` list, we need to include those phrases in the message as well.

**Approach:**
1. In `skill_loader.py`, add a `trigger_phrases: list[str]` field to `SkillConfig` (read from skill frontmatter)
2. In `_build_message()`, include trigger phrases in the message text
3. Keep context data in the message (until U2.2 MCP migration completes), but format it as readable text rather than opaque JSON

**Verification:** DeerFlow correctly routes to the intended skill based on trigger phrase matching. Agent output quality unchanged.

---

## Phase 3: Enhancement (Low Risk)

### U3.1 — Gateway API proxy endpoints

**Drift addressed:** D8

**Implements:** Alignment Plan U8 (previously planned but not implemented)

**Files:**
- `server/apps/agent/app/routers/cache.py` (extend) or new `app/routers/gateway.py`
- `server/apps/agent/tests/unit/test_gateway_router.py`

**Endpoints:**
- `GET /internal/models` — proxy to DeerFlow `GET /api/models`
- `PUT /internal/skills/{name}` — proxy to `PUT /api/skills/{name}`
- `DELETE /internal/threads/{id}` — proxy to `DELETE /api/threads/{id}`

All three require `X-Agent-Token` header. Path parameters validated against `_SAFE_ID_PATTERN` before forwarding (SSRF prevention).

**Configuration:** `DEERFLOW_GATEWAY_URL` from `AgentSettings` (already defined).

**Verification:** `pytest tests/unit/test_gateway_router.py -v` passes.

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
  U1.1 (remove thinking_enabled from stream)
  U1.2 (deprecate raw text path)
  U1.3 (document thinking invariant)
  → All parallel, zero dependencies

Phase 2 (decoupling):
  U2.1 (eliminate _init_lock) — independent
  U2.2 (MCP for all capabilities) — independent but benefits from U2.3
  U2.3 (natural language trigger) — prerequisite: verify DeerFlow trigger_phrases behavior
  → U2.1 and U2.2 can proceed in parallel

Phase 3 (enhancement):
  U3.1 (Gateway API proxy) — depends on U2.1 (config isolation for clean Gateway interaction)
  U3.2 (Suggestions API) — depends on U3.1 (needs Gateway endpoint)
  U3.3 (Dynamic capabilities) — depends on U3.1 (needs Gateway endpoint)
  → U3.2 and U3.3 can proceed in parallel after U3.1
```

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Monkey-patching `get_app_config()` breaks on DeerFlow upgrade | Medium | High | Wrap patch in try/except with fallback to current `_init_lock` behavior; add integration test |
| DeerFlow `trigger_phrases` matching doesn't work with `[SKILL:xxx]` tags | Medium | Low | Include actual trigger phrases in message text; keep JSON fallback |
| MCP tool latency adds overhead vs pre-fetched context | Low | Medium | Measure p50/p95 latency before/after; keep `_build_context()` as fallback |
| Gateway API endpoints not available in vendored DeerFlow version | Low | Medium | Check DeerFlow version and available endpoints before implementing U3.1 |
| Removing `stream_dispatch()` breaks unknown consumers | Low | High | grep all router files for `stream_dispatch` references; verify frontend only uses NDJSON |

---

## Out of Scope

- Postgres checkpointer migration (separate initiative)
- APScheduler job activation (Phase 0 constraint)
- JSONL file migration to object storage
- Frontend UI for Gateway API management (follow-up after U3.1)
- `reasoning_effort` parameter support (covered by Chat UX Fusion Plan U2)
- SubtaskCard multi-subtask visualization (covered by Chat UX Fusion Plan)
