---
title: "feat: DeerFlow SSE protocol alignment — three-track event format"
date: 2026-06-20
status: active
origin: docs/brainstorms/2026-06-20-deerflow-sse-protocol-alignment-requirements.md
type: feat
sequence: 001
---

# feat: DeerFlow SSE protocol alignment — three-track event format

**Origin:** `docs/brainstorms/2026-06-20-deerflow-sse-protocol-alignment-requirements.md`  
**Scope:** `server/apps/agent/` + `server/apps/backend/app/routers/ai_chat.py` + tests

---

## Summary

Align Numina's AI chat streaming protocol with DeerFlow 2.0's three-track SSE format by adding the missing `custom` (skill/tool progress) and `values` (state snapshot) event tracks, converting the backend→frontend protocol from NDJSON to native SSE, and reusing DeerFlow's existing `format_sse()` pattern. This closes the gap between Numina's embedded DeerFlow integration and DeerFlow's standalone runtime behavior.

**Stage 1 (U1-U3) is already implemented in the working tree** — `typed_stream_dispatch()` in adapter.py, enhanced `_sse_generator()` in runs.py, and NDJSON→SSE conversion in ai_chat.py. This plan documents all 5 units for completeness and tracks the remaining work in U4-U5.

---

## Problem Frame

Numina's AI chat stack has three layers: Frontend (Vue) → Backend (FastAPI proxy) → Agent (DeerFlowClient). The current backend→frontend protocol uses NDJSON (`application/x-ndjson`), while DeerFlow's native protocol uses SSE (`text/event-stream`) with three event tracks:

1. **`messages`** — Token stream (AI response text, thinking blocks)
2. **`custom`** — Structured skill/tool progress events (Docker sandbox execution, Deep Research progress, subtask cards, suggestions)
3. **`values`** — State snapshots (plan todos, conversation state for session replay)

Numina previously only forwarded the `messages` track (via `token.stream` events). The `custom` and `values` events from DeerFlow's raw stream were consumed internally by the adapter but never forwarded to the frontend.

---

## Requirements

### Protocol Alignment

- R1. Convert backend→frontend streaming from NDJSON (`application/x-ndjson`) to native SSE (`text/event-stream`) with named event types, matching DeerFlow's `format_sse()` pattern
- R2. Forward `messages-tuple` events from DeerFlow's raw stream as SSE `messages` events to the frontend, including both thinking blocks and text content
- R3. Forward `custom` events from DeerFlow's raw stream as SSE `custom` events, preserving the structured data payload (tool calls, skill progress, subtask cards, suggestions)
- R4. Forward `values` events from DeerFlow's raw stream as SSE `values` events, preserving state snapshot data (plan todos, conversation state)
- R5. Forward `error` and `end` sentinel events in SSE format

### Agent-Side Event Pipeline

- R6. In `adapter.py`, add `typed_stream_dispatch()` that categorizes each LangGraph event by type and yields typed tuples `(sse_event_type, data)` instead of raw events
- R7. In `runs.py`'s `_sse_generator()`, emit `custom` events for tool calls, skill progress, and suggestions — not just the current `end`-only pattern
- R8. In the agent's chat router (`routers/chat.py`), forward all three event tracks when proxying to the backend, not just text content

### Backend Proxy Alignment

- R9. In `ai_chat.py`'s `proxy_stream()` generator, detect and forward SSE events from the agent service for all three tracks
- R10. Maintain backward compatibility for clients that still consume NDJSON (graceful period or version header)

### Cleanup & Resource Safety

- R11. Ensure `try/finally` in all streaming generators cleans up resources (HTTP connections, thread pool slots) regardless of which event track is being consumed
- R12. Ensure `GeneratorExit` (client disconnect) in the frontend closes the backend proxy stream, which in turn closes the agent's DeerFlow stream

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **SSE format function** | Reuse DeerFlow's `format_sse()` | The agent's `runs.py` already defines `format_sse(event, data)` matching DeerFlow's canonical `event: {type}\ndata: {json}\n\n` pattern. Extend for all event types rather than inventing a new format. |
| **Event classification layer** | Add `typed_stream_dispatch()` as a new method | Keeps `raw_stream_dispatch()` unchanged for backward compatibility with existing consumers (orchestrator, chat_adapter). The new method wraps it with event type classification. |
| **NDJSON→SSE at the proxy level** | Convert in `ai_chat.py` proxy | The agent still emits NDJSON for legacy capabilities. The backend proxy is the natural conversion point — it reads NDJSON lines from the agent, writes SSE events to the frontend. |
| **Backward compatibility** | Accept header detection | Check `Accept: text/event-stream` to decide format. Default to SSE for new clients, fall back to NDJSON for legacy. |
| **Three-track passthrough** | Minimal adaptation | Pass through the DeerFlow event type and data structure with minimal serialization. Don't transform event payloads. |

---

## Scope Boundaries

- **Frontend Vue components** — Not in scope for this phase; frontend will need updates to consume the new SSE format, but the focus is on backend/agent protocol alignment
- **Session replay** — The `values` track enables future replay but full replay UI is deferred
- **Feedback events** — User feedback (thumbs up/down) events are deferred
- **Artifact events** — Code/file output events are deferred to a later phase

### Deferred to Follow-Up Work

- Frontend EventSource/fetch stream consumer upgrade to dispatch by `event:` type
- Full session replay UI leveraging `values` track data
- Removal of `_stream_error_event` helper function (replaced by inline SSE error format)

---

## Implementation Units

### U1. Add `typed_stream_dispatch()` to DeerFlowAdapter (COMPLETED)

**Goal:** Add event type annotation to yielded events so SSE generators can dispatch by type without re-parsing.

**Files:**
- `server/apps/agent/services/deerflow_adapter/adapter.py`

**Changes:**
- Added `typed_stream_dispatch()` async generator that wraps `raw_stream_dispatch()` and yields `(sse_event_type, data)` tuples
- Event type mapping:
  - `messages-tuple` → `"messages"` (AI text, tool calls)
  - `values` → `"values"` (state snapshots, plan todos)
  - `end` → `"end"` (stream complete)
  - `error` → `"error"` (stream error)
  - All other types → `"custom"` (tool progress, metadata)
- `raw_stream_dispatch()` is unchanged — existing consumers (orchestrator, chat_adapter) unaffected

**Patterns to follow:** The existing `_async_stream_chunks()` method shows how to wrap and classify DeerFlow events — `typed_stream_dispatch()` follows the same pattern but yields SSE-friendly tuples instead of `StreamChunk` objects.

**Test scenarios:**
- Verify `values` events are classified as `("values", data)`
- Verify `messages-tuple` events are classified as `("messages", data)`
- Verify error events are classified as `("error", data)`
- Verify backward compatibility — existing consumers (orchestrator, chat_adapter) unaffected

**Verification:** `pytest server/tests/agent/unit/ -v` passes

---

### U2. Enhance `runs.py` SSE generator with full event tracks (COMPLETED)

**Goal:** Emit SSE events for all three tracks from the runs endpoint.

**Files:**
- `server/apps/agent/routers/runs.py`

**Changes:**
- `_sse_generator()` now iterates `typed_stream_dispatch()` instead of `raw_stream_dispatch()`
- Emits `event: messages` for AI text content, collecting AI response parts for suggestions
- Emits `event: custom` for tool calls (extracted from AI messages) and skill progress
- Emits `event: values` for state snapshots
- Emits `event: error` on stream failure, then breaks
- Emits `event: end` sentinel
- Keeps existing `suggestions` custom event and title generation in `finally` block

**Patterns to follow:** The `format_sse()` function is reused from DeerFlow's canonical pattern — `event: {type}\ndata: {json}\n\n`.

**Test scenarios:**
- Verify SSE output contains `event: messages`, `event: custom`, `event: values` lines
- Verify tool calls from AI messages are emitted as `event: custom` with `type: tool_call`
- Verify `event: end` still emitted after stream completes
- Verify error handling sends `event: error` on failure
- Verify suggestions and title generation still work

**Verification:** `pytest server/tests/agent/unit/ -v` and `pytest server/tests/agent/integration/ -v`

---

### U3. Update backend `ai_chat.py` proxy for SSE passthrough (COMPLETED)

**Goal:** Forward SSE events from agent to frontend, converting NDJSON to SSE on the fly.

**Files:**
- `server/apps/backend/app/routers/ai_chat.py`

**Changes:**
- Changed `proxy_stream()` media_type from `application/x-ndjson` to `text/event-stream`
- Added SSE response headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`
- Added `_SSE_TYPE_MAP` dict mapping NDJSON event types to SSE event types
- `session.start` event now emitted in SSE format (`event: session.start\ndata: {...}\n\n`)
- Error events now emitted in SSE format (`event: error\ndata: {...}\n\n`)
- Each NDJSON line from agent is parsed, mapped to SSE type, and emitted as `event: {sse_type}\ndata: {json}\n\n`
- Answer token collection still works by parsing NDJSON lines before SSE conversion
- `stream_session_events` endpoint also updated to `text/event-stream` with SSE headers (raw passthrough from agent's SSE stream)

**Patterns to follow:** The NDJSON-to-SSE conversion pattern uses a type map similar to the agent's `typed_stream_dispatch()`. The SSE header set matches DeerFlow's reference implementation.

**Test scenarios:**
- Verify SSE output contains `event:` prefixed lines
- Verify `session.start` event emitted first in SSE format
- Verify answer persistence still works (tokens collected from NDJSON before SSE conversion)
- Verify error events emitted as `event: error`
- Verify `stream_session_events` endpoint returns `text/event-stream`

**Verification:** `pytest server/tests/backend/ -v -k "chat"` passes. Manual: start agent + backend, send chat request, observe SSE event types in response.

---

### U4. Clean up deprecated helpers and legacy code (PENDING)

**Goal:** Remove or deprecate helper functions and patterns that are no longer needed after the SSE migration.

**Files:**
- `server/apps/backend/app/routers/ai_chat.py`

**Changes:**
- `_stream_error_event()` is no longer called by `proxy_stream()` (error events are now inlined as SSE format). Consider deprecating or removing this function.
- `_collect_answer_token_from_event()` still parses NDJSON lines — this is correct because the proxy receives NDJSON from the agent. However, it should be documented that this function operates on the *internal* NDJSON stream, not the *external* SSE stream.
- The `_SSE_TYPE_MAP` dict added in U3 should be promoted to a module-level constant for reuse and documentation.

**Test scenarios:**
- Verify no dead code paths remain (unused imports, unused functions)
- Verify existing tests still pass with clean code

**Verification:** `ruff check server/apps/backend/app/routers/ai_chat.py` passes cleanly.

---

### U5. Backward compatibility layer (PENDING)

**Goal:** Support both NDJSON and SSE during migration period.

**Files:**
- `server/apps/backend/app/routers/ai_chat.py`

**Changes:**
- Check `Accept` header on the request: if `text/event-stream` is preferred, use SSE format; otherwise fall back to NDJSON
- When falling back to NDJSON, emit events using the original `application/x-ndjson` format
- Document the deprecation path and timeline for NDJSON removal

**Approach options:**
1. **Accept header detection** (recommended) — Single endpoint checks `Accept` header; new frontend sends `Accept: text/event-stream`, legacy sends NDJSON
2. **Dual endpoint** — `/chat/stream` keeps NDJSON, new `/chat/stream/sse` endpoint uses SSE

**Test scenarios:**
- Verify request without `Accept: text/event-stream` header receives NDJSON
- Verify request with `Accept: text/event-stream` header receives SSE
- Verify both paths persist answers correctly

**Verification:** Integration test with both Accept header values, checking Content-Type and event format.

---

## Risks & Dependencies

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Frontend not ready for SSE format | Medium | U5 backward compatibility layer keeps NDJSON working; frontend migration can be gradual |
| Existing NDJSON consumers break | Low | Only `/chat/stream` and `/sessions/{id}/events` endpoints changed; non-streaming endpoints unaffected |
| Agent-side `raw_stream_dispatch()` changes affect other consumers | Low | `typed_stream_dispatch()` is additive — `raw_stream_dispatch()` unchanged |
| Agent sessions endpoint (`/sessions/{id}/events`) doesn't emit SSE yet | Medium | `stream_session_events` proxy uses raw byte passthrough; the agent's sessions router needs its own SSE upgrade |

---

## Open Questions

- Q1. Does the agent's sessions events endpoint (`/sessions/{id}/events`) emit NDJSON or SSE? The proxy uses `aiter_bytes()` passthrough, so the protocol depends on what the agent sends. **Deferred to implementation.**

---

## System-Wide Impact

- **Backend proxy** (`ai_chat.py`): Protocol change from NDJSON→SSE affects Content-Type and event format
- **Agent runs endpoint** (`runs.py`): Enhanced SSE output with all three event tracks
- **Agent adapter** (`adapter.py`): New method added, existing methods unchanged
- **Tests**: Mock stream responses updated to support both `aiter_lines()` and `aiter_bytes()`
- **Frontend**: Must update EventSource/fetch stream parser to dispatch by `event:` type (deferred)

---

## Sources & Research

- DeerFlow reference implementation: `format_sse()` in DeerFlow's gateway services module
- DeerFlow reference streaming endpoint: SSE with three-track events (`messages`, `custom`, `values`)
- Numina existing patterns: `_async_stream_chunks()`, `raw_stream_dispatch()`, `AgentClient.stream()`
