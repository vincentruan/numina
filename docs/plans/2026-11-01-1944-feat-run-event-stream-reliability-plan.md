---
title: Run Event Stream Reliability - Plan
type: feat
date: 2026-11-01
topic: run-event-stream-reliability
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Every agent run's lifecycle events are persistently recorded and queryable, and the chat frontend can recover from SSE disconnections without losing messages — bringing chat to parity with the task page's existing resilience.
- **Authority:** Issues #172 (T12) and #173 (T13), part of #168 (P1: Run Event Stream).
- **Means:** Backend structured event store + frontend `Last-Event-ID` via `readSSEStream` (KTD2).
- **Execution:** `code` — ships as one PR (backend + frontend are tightly coupled via the event ID contract).

---

## Progress Tracker

> Last updated: 2026-11-01

| Unit | Status | Evidence |
|------|--------|----------|
| U1 — Run event store module | ✅ **COMPLETE** | 10 unit tests pass |
| U2 — Worker event emission hooks | ✅ **COMPLETE** | 5 integration tests pass |
| U3 — Event query API endpoint | ✅ **COMPLETE** | 7 integration tests pass |
| U3b — T13 reattach endpoint | ✅ **COMPLETE** | 4 integration tests pass (bonus, not in original scope) |
| U4 — Frontend Last-Event-ID reconnection | ⬜ **NOT STARTED** | — |
| U5 — Frontend integration tests | ⬜ **NOT STARTED** | — |

**Backend total: 26/26 tests passing.**

### Implementation notes (from completed work)

- **U2 simplification:** Instead of wrapping `bridge.publish()` calls directly, event recording was placed at the natural semantic points: `run.start`/`run.end` in `worker.py:run_agent()` (the try/finally block), and `llm.ai.response`/`llm.tool.result` in `run_pipeline.py:_StreamForwarder` (the existing SSE frame forwarding loop). All calls are best-effort (wrapped in `try/except` with `pass` or `warning` log) so event recording failures never break the run.
- **U3b bonus:** The reattach endpoint (`GET /threads/{thread_id}/runs/{run_id}/stream`) was added as part of T13 — it was not in the original brainstorm but is needed for the frontend `Last-Event-ID` reconnection to work. It attaches to an existing run's Redis buffer without creating a new run, with cross-tenant isolation checks.
- **Lifespan not modified:** The plan mentioned modifying `lifespan.py` to instantiate the event store, but the implementation uses a lazy singleton (`_get_event_store()` in `run_event_store.py`) instead, avoiding import-time config access. No lifespan changes were needed.

### Pending lint fixes (backend, before commit)

Ruff found 4 issues in the implemented code — fix before committing:

| File | Rule | Fix |
|------|------|-----|
| `run_pipeline.py:16` | I001 — import block unsorted | Move `run_event_store` import below `schemas/context` ( alphabetical within local group) |
| `run_pipeline.py:888` | SIM105 — `try/except/pass` | Replace with `contextlib.suppress(Exception)` |
| `run_pipeline.py:938` | SIM105 — `try/except/pass` | Replace with `contextlib.suppress(Exception)` |
| `worker.py:27` | F401 — unused import | Remove `RunEventStore` (only `_get_event_store` is used) |

---

## Product Contract

### Summary

Two layers of run event stream reliability: a backend event store that persistently records structured run lifecycle events (start/end, LLM responses, tool results) queryable by thread and family, and a frontend `Last-Event-ID` reconnection mechanism in the chat composable that replays missing events after SSE disconnect. Together they ensure no event is lost in transit and every run is auditable.

### Problem Frame

Agent runs currently lack structured persistent event recording. The only record is `session_journal.py`, which is a stub (all methods are no-ops). This makes debugging failed runs, auditing agent behavior, and understanding tool usage impossible after the fact.

Simultaneously, the chat frontend (`useThreadChat.ts`) does not track SSE event IDs or send `Last-Event-ID` on reconnect. Under weak network conditions, a mid-stream disconnect loses all events after the last client-side render — messages silently disappear. The task page (`useTaskResume.ts`) already solved this problem via `Last-Event-ID` tracking and Redis buffer replay, but the chat path was never updated.

### Requirements

**Event persistence (backend)**

- R1. Every agent run emits at minimum `run.start` and `run.end` events, persisted to a structured store (not the no-op session journal).
- R2. LLM response events (`llm.ai.response`) and tool result events (`llm.tool.result`) are persisted during the run's dispatch path.
- R3. Events are queryable by `thread_id` and by `family_id`, returning an ordered event list.
- R4. The event schema covers at least: `run.start`, `run.end`, `llm.ai.response`, `llm.tool.result`, and `middleware:*` (extensible).
- R5. Integration tests verify event emission and query for a complete run lifecycle.

**Chat reconnection (frontend)**

- R6. `useThreadChat.ts` tracks the latest SSE event `id:` field during streaming.
- R7. On SSE disconnect/reconnect, the composable sends `Last-Event-ID` header so the backend can replay missing events from the Redis buffer.
- R8. Reconnection works with the existing T7 gap recovery mechanism (checkpoint-based recovery when the Redis buffer is also truncated).
- R9. Integration tests verify Last-Event-ID tracking and reconnection behavior.

### Key Decisions

- **New event store, not session_journal revival.** `session_journal.py` is a stub with no-op methods and JSONL-per-session semantics. The run event store has different requirements (structured query, cross-session aggregation by family_id). A new `run_event_store.py` module is cleaner than retrofitting the stub.
- **Last-Event-ID via SSE id field, not custom event data.** The backend `format_sse` already emits `event_id` in the SSE `id:` field, and `StreamBridge` Redis backend already supports `Last-Event-ID` replay. The frontend only needs to capture the `id:` field and pass it as a header — no new backend endpoint or protocol change required.
- **T7 gap recovery is the fallback when Redis buffer is also lost.** `Last-Event-ID` replay covers the common case (brief disconnect, events still in Redis buffer). When the buffer is truncated (slow client, long disconnect), the existing T7 gap recovery mechanism (checkpoint reload) handles it. The two mechanisms are complementary, not redundant.

### Key Flows

- F1. Run lifecycle event recording
  - **Trigger:** Agent run starts via `worker.run_agent`.
  - **Steps:** Worker emits `run.start` → dispatch proceeds → LLM responses emit `llm.ai.response` → tool results emit `llm.tool.result` → run completes → worker emits `run.end`.
  - **Covered by:** R1, R2, R4

- F2. Event query
  - **Trigger:** Debug/audit request by `thread_id` or `family_id`.
  - **Steps:** API receives query → run_event_store filters by key → returns ordered event list.
  - **Covered by:** R3

- F3. Chat SSE reconnection
  - **Trigger:** SSE connection drops mid-stream in `useThreadChat.ts`.
  - **Steps:** Composable retains last event `id:` → reconnect sends `Last-Event-ID` header → backend replays missing events from Redis buffer → stream continues.
  - **Covered by:** R6, R7, R8

### Acceptance Examples

- AE1. Complete run audit
  - **Covers R1, R2, R4.** Given a chat run that produces 2 LLM responses and 3 tool calls, when querying events by `thread_id`, then the result includes `run.start`, 2× `llm.ai.response`, 3× `llm.tool.result`, and `run.end` in chronological order.

- AE2. Chat reconnection after brief disconnect
  - **Covers R6, R7.** Given an active chat stream where the client received events up to `id: 42`, when the SSE connection drops and reconnects with `Last-Event-ID: 42`, then events 43+ are replayed from the Redis buffer before live events resume.

- AE3. Reconnection with truncated buffer falls back to gap recovery
  - **Covers R7, R8.** Given a chat stream where the Redis buffer was truncated (only events 50+ retained), when the client reconnects with `Last-Event-ID: 42`, the backend detects the gap and the frontend falls back to T7 checkpoint recovery (reload from checkpoint, resume with `input: null`).

### Scope Boundaries

- Frontend debug/audit API for viewing events is deferred — the backend store supports it, but no UI is built in this iteration.
- Changes to the task page (`useTaskResume.ts`) are out of scope — it already works correctly.
- Changes to StreamBridge or `format_sse` are out of scope — both already support the required functionality.
- Event retention / TTL / cleanup policy is deferred to planning.

---

## Planning Contract

### Key Technical Decisions

KTD1. **Event storage: local structured JSONL, not database.** The agent module cannot import from `packages/db` (import direction rule: `apps/` → `packages/`, no sibling app imports). The existing `session_journal.py` pattern writes JSONL to `SESSIONS_DATA_DIR`. The new `run_event_store.py` follows the same pattern: one JSONL file per `family_id`, with structured event records. Query by `thread_id` scans the family's file; query by `family_id` returns all events. This avoids adding backend HTTP round-trips for event persistence and keeps the agent self-contained.

KTD2. **Frontend SSE: switch from SDK `client.runs.stream()` to `readSSEStream`.** The LangGraph SDK's `runs.stream()` does not expose a way to pass custom HTTP headers like `Last-Event-ID`. The `@numina/shared` package already exports `readSSEStream` (used by `subscribeTaskStream` in the task page), which accepts custom headers. The chat composable will construct the SSE request manually (POST to `/api/threads/{id}/runs/stream`) and use `readSSEStream` to parse frames, enabling `Last-Event-ID` support. This is the same approach proven in the task page.

KTD3. **Event emission: hook into `bridge.publish` calls in worker.py.** The worker already calls `bridge.publish(run_id, event, data)` for every SSE frame. The event store wraps or observes these calls to persist structured events. The cleanest approach: inject the event store into `run_agent()` and call `event_store.record()` alongside each `bridge.publish()`. This keeps event emission co-located with the existing publish calls and avoids duplicating the event routing logic.

### Assumptions

- Event volume per family is moderate (chat interactions, not high-frequency streaming). JSONL file scanning for queries is acceptable; if volume grows, a database migration can be done later.
- The SSE gateway's existing `Last-Event-ID` handling (reading the header, passing to `bridge.subscribe`) is sufficient — no backend changes needed for reconnection support.
- The `readSSEStream` handler interface (`onMessage`, `onCustom`, `onEnd`, `onError`, `onMetadata`, `onGap`) covers all event types the chat composable currently processes from the SDK's `StreamChunk`.

---

## Implementation Units

### U1. Run event store module ✅ COMPLETE

**Goal:** Create a structured event persistence module that records run lifecycle events to local JSONL files, queryable by `thread_id` and `family_id`.

**Requirements:** R1, R2, R3, R4

**Dependencies:** none

**Files:**
- `server/apps/agent/services/run_event_store.py` (new) ✅
- `server/tests/agent/unit/test_run_event_store.py` (new) ✅

**Approach:**
1. Define event schema as a Pydantic model: `RunEvent(event_type: str, run_id: str, thread_id: str, family_id: str, timestamp: str, data: dict)`.
2. `RunEventStore` class with methods: `record(event)`, `query_by_thread(thread_id)`, `query_by_family(family_id)`.
3. Storage: one JSONL file per `family_id` under `{SESSIONS_DATA_DIR}/run_events/{family_id}.jsonl`.
4. Each line is a JSON-serialized `RunEvent`.
5. Query methods read the file, filter by `thread_id` (or return all for `family_id`), sort by `timestamp`.
6. Thread-safe writes via file locking or append-only mode (JSONL is append-friendly).

**Patterns to follow:**
- `server/apps/agent/services/session_journal.py` — file path resolution, `SESSIONS_DATA_DIR` usage
- Pydantic v2 models per `server/AGENTS.md`

**Test scenarios:**
- Record a `run.start` event, verify it appears in the JSONL file
- Record multiple events for the same `thread_id`, verify `query_by_thread` returns them in order
- Record events for different `family_id`s, verify file isolation
- Query by `family_id` returns all events for that family
- Empty query returns empty list (no crash on missing file)

**Verification:** Unit tests pass; JSONL file is human-readable.

---

### U2. Worker event emission hooks ✅ COMPLETE

**Goal:** Wire the event store into the worker dispatch path so every run emits structured events.

**Requirements:** R1, R2, R4, R5

**Dependencies:** U1

**Files:**
- `server/apps/agent/services/runtime/worker.py` (modify) ✅ — `run.start` (line ~362) and `run.end` (line ~439, in `finally` block)
- `server/apps/agent/services/runtime/run_pipeline.py` (modify) ✅ — `llm.ai.response` (line ~889) and `llm.tool.result` (line ~939) in `_StreamForwarder`
- `server/tests/agent/integration/test_run_event_emission.py` (new) ✅

**Deviation from plan:** Instead of modifying `lifespan.py` to instantiate the event store, the implementation uses the lazy singleton `_get_event_store()` from `run_event_store.py`. This avoids import-time config access and keeps the lifespan unchanged.

**Approach:**
1. Instantiate `RunEventStore` in `lifespan.py` (or lazily in `run_agent`).
2. In `run_agent()`, after setting up the bridge, emit `run.start` event with `run_id`, `thread_id`, `family_id`, `app` metadata.
3. After each `bridge.publish()` call that represents an LLM response or tool result, emit the corresponding event (`llm.ai.response` or `llm.tool.result`).
4. In the `finally` block of `run_agent()`, emit `run.end` event with status (success/error).
5. Event data includes: `event_type`, `run_id`, `thread_id`, `family_id`, `timestamp`, and relevant payload (truncated LLM response text, tool name + result summary).

**Patterns to follow:**
- `worker.py:run_agent` — the existing `bridge.publish()` calls are the hook points
- Audit logger pattern (`audit_logger.log_call()`) for structured logging in `finally` blocks

**Test scenarios:**
- Covers AE1. Run a complete agent session, verify `run.start`, `llm.ai.response`, `llm.tool.result`, `run.end` events are recorded
- Verify events are queryable by `thread_id` after the run completes
- Verify `run.end` is emitted even when the run errors (finally block)
- Verify event timestamps are in chronological order

**Verification:** Integration test runs a mock agent session and verifies event store contents.

---

### U3. Event query API endpoint ✅ COMPLETE

**Goal:** Expose an API endpoint for querying recorded events by `thread_id` or `family_id`.

**Requirements:** R3

**Dependencies:** U1

**Files:**
- `server/apps/agent/routers/run_events.py` (new) ✅
- `server/apps/agent/app/main.py` (modify — register router) ✅ (line 313)
- `server/tests/agent/integration/test_run_events_api.py` (new) ✅

**Implementation detail:** The router enforces tenant isolation — `family_id` query param must match `X-Family-Id` header (403 on mismatch), and `thread_id` queries are scoped to the caller's family. Chinese error messages per project convention.

---

### U3b. T13 reattach endpoint ✅ COMPLETE (bonus)

**Goal:** Add a subscribe-only SSE endpoint for reattaching to an in-flight run's event stream, supporting `Last-Event-ID` reconnection.

**Requirements:** Supports R7, R8 (frontend reconnection requires this endpoint)

**Dependencies:** none

**Files:**
- `server/apps/agent/routers/runs_stream.py` (modify) ✅ — `GET /{thread_id}/runs/{run_id}/stream` (line 166)
- `server/tests/agent/integration/test_run_reattach_stream.py` (new) ✅

**Approach:**
1. New `GET` endpoint at `/api/threads/{thread_id}/runs/{run_id}/stream`.
2. Looks up the run via `RunManager.get(run_id)` — returns 404 if not found, thread mismatch, or family mismatch (existence not leaked).
3. Reuses the existing `sse_consumer()` to replay from the Redis buffer — no new consumer logic needed.
4. Does NOT install a disconnect watcher — the primary POST subscriber owns the run lifecycle; disconnecting the reattach must not cancel the run.
5. Also advertises the reattach URL in the primary stream's `Location` response header (line ~161) so the SDK's `streamWithRetry` can derive the reconnect path.

**Verification:** 4 integration tests cover 404 cases (not found, thread mismatch, family mismatch) and successful reattach.

---

### U4. Frontend chat Last-Event-ID reconnection ⬜ NOT STARTED

**Goal:** Enable `useThreadChat.ts` to track SSE event IDs and send `Last-Event-ID` on reconnect.

**Requirements:** R6, R7, R8

**Dependencies:** U3b (reattach endpoint must exist — ✅ complete)

**Files:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` (modify)
- `frontend/apps/main/src/api/ai-chat.ts` (modify — add SSE helper with headers)

**Approach:**
1. Add a `lastEventId` ref to `useThreadChat` state.
2. Replace `client.runs.stream()` with a manual POST to `/api/threads/{id}/runs/stream` using `readSSEStream` from `@numina/shared`.
3. Parse SSE frames using the existing handler pattern (`onMessage`, `onCustom`, `onEnd`, `onError`, `onMetadata`, `onGap`).
4. On each frame, capture the `id:` field (if present) and update `lastEventId`.
5. On reconnect (retry loop), pass `Last-Event-ID: lastEventId` as a request header.
6. On `gap` event (buffer truncated), fall back to existing T7 checkpoint recovery.
7. The existing retry loop (`SSE_MAX_RETRIES`, exponential backoff) already handles reconnection — just add the header.

**Patterns to follow:**
- `frontend/apps/main/src/api/ai-tasks.ts:subscribeTaskStream` — uses `readSSEStream` with `lastEventId` header
- `frontend/apps/main/src/composables/useTaskResume.ts` — Last-Event-ID tracking pattern

**Test scenarios:**
- Covers AE2. Mock SSE stream with `id:` fields, verify `lastEventId` is updated after each frame
- Mock SSE disconnect + reconnect, verify `Last-Event-ID` header is sent
- Covers AE3. Mock `gap` event, verify fallback to T7 checkpoint recovery
- Verify stream processing (messages-tuple, values, custom events) still works after switching from SDK to `readSSEStream`

**Verification:** Unit tests mock SSE frames; integration test verifies reconnection in dev server.

---

### U5. Frontend integration tests ⬜ NOT STARTED

**Goal:** Verify the complete reconnection flow end-to-end.

**Requirements:** R9

**Dependencies:** U4

**Files:**
- `frontend/apps/main/tests/composables/ai-chat/useThreadChat.reconnect.spec.ts` (new)

**Approach:**
1. Test the full reconnection scenario: stream starts → events arrive with IDs → connection drops → reconnect with `Last-Event-ID` → events replay → stream continues.
2. Test the gap recovery fallback: stream starts → `gap` event → checkpoint reload → resume with `input: null`.
3. Verify no message loss: all events before disconnect are retained, events after reconnect are appended.

**Patterns to follow:**
- `frontend/apps/main/src/composables/ai-chat/__tests__/useThreadChat.compact.spec.ts` — test structure
- `frontend/apps/main/src/api/__tests__/subscribeTaskStream.spec.ts` — SSE mock pattern

**Test scenarios:**
- Full reconnection: 5 events → disconnect → reconnect → 3 more events → verify all 8 events present
- Gap recovery: 5 events → gap → checkpoint reload → verify messages reconstructed from checkpoint
- No duplicate events on reconnect (replayed events are not duplicated)

**Verification:** All tests pass; coverage of reconnection and gap recovery paths.

---

## Verification Contract

### Backend — ✅ COMPLETE (26/26 tests passing)

| Scope | Command | What it proves |
|-------|---------|----------------|
| Backend unit tests | `cd server && uv run pytest tests/agent/unit/test_run_event_store.py -v` | ✅ Event store record/query works (10 tests) |
| Backend integration tests | `cd server && uv run pytest tests/agent/integration/test_run_event_emission.py tests/agent/integration/test_run_events_api.py tests/agent/integration/test_run_reattach_stream.py -v` | ✅ Event emission + API query + reattach work (16 tests) |
| Backend lint + typecheck | `cd server && uv run ruff check apps/agent/services/run_event_store.py apps/agent/routers/run_events.py apps/agent/routers/runs_stream.py` | ⏳ To verify before commit |

### Frontend — ⬜ REMAINING

| Scope | Command | What it proves |
|-------|---------|----------------|
| Frontend unit tests | `cd frontend && pnpm --filter main test:run -- useThreadChat` | SSE processing + reconnection logic |
| Frontend typecheck | `cd frontend && pnpm --filter main typecheck` | No type errors |

### Full regression — to run after U4+U5

| Scope | Command | What it proves |
|-------|---------|----------------|
| Full agent test suite | `cd server && uv run pytest tests/agent/ -v` | No regressions in existing agent tests |

---

## Definition of Done

### Backend — ✅ COMPLETE
- [x] `run_event_store.py` records events to JSONL; query by `thread_id` / `family_id`
- [x] Worker emits `run.start` / `run.end` in try/finally (success and error paths)
- [x] Pipeline emits `llm.ai.response` / `llm.tool.result` during stream forwarding
- [x] API endpoint `GET /run-events` returns events with tenant isolation
- [x] Reattach endpoint `GET /threads/{tid}/runs/{rid}/stream` for Last-Event-ID replay
- [x] 26 backend tests passing (10 unit + 16 integration)

### Frontend — ⬜ REMAINING
- [ ] `useThreadChat.ts` tracks `Last-Event-ID` and sends it on reconnect
- [ ] SSE processing switched to `readSSEStream` (from SDK `client.runs.stream()`)
- [ ] Gap recovery fallback to T7 checkpoint when Redis buffer is truncated
- [ ] Frontend integration tests for reconnection and gap recovery
- [ ] No regressions in existing chat tests

### Overall
- [ ] Product Contract preserved — all R-IDs, F-IDs, AE-IDs addressed
- [ ] Code follows project conventions (ruff, mypy, pnpm lint/typecheck pass)
- [ ] Cleanup: no dead-end or experimental code left in the diff
