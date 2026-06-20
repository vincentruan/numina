---
date: 2026-06-20
topic: deerflow-sse-protocol-alignment
---

# DeerFlow SSE Protocol Alignment — Gap Closure & Implementation Plan

## Summary

Align Numina's AI chat streaming protocol with DeerFlow 2.0's three-track SSE format by adding the missing `custom` (skill/tool progress) and `values` (state snapshot) event tracks, converting the backend→frontend protocol from NDJSON to native SSE, and reusing DeerFlow's existing event-handling code paths where possible.

---

## Problem Frame

Numina's AI chat stack has three layers: Frontend (Vue) → Backend (FastAPI proxy) → Agent (DeerFlowClient). The current backend→frontend protocol uses NDJSON (`application/x-ndjson`), while DeerFlow's native protocol uses SSE (`text/event-stream`) with three event tracks:

1. **`messages`** — Token stream (AI response text, thinking blocks)
2. **`custom`** — Structured skill/tool progress events (Docker sandbox execution, Deep Research progress, subtask cards, suggestions)
3. **`values`** — State snapshots (plan todos, conversation state for session replay)

Numina currently only forwards the `messages` track (via `token.stream` events). The `custom` and `values` events from DeerFlow's raw stream are consumed internally by the adapter but never forwarded to the frontend. This means:
- Skill/tool progress is invisible to users
- No subtask cards or structured progress UI
- No state snapshot data for session replay enhancements
- Frontend can't render the rich process visualization that DeerFlow supports

---

## Requirements

### Protocol Alignment

- R1. Convert backend→frontend streaming from NDJSON (`application/x-ndjson`) to native SSE (`text/event-stream`) with named event types, matching DeerFlow's `format_sse()` pattern
- R2. Forward `messages-tuple` events from DeerFlow's raw stream as SSE `messages` events to the frontend, including both thinking blocks and text content
- R3. Forward `custom` events from DeerFlow's raw stream as SSE `custom` events, preserving the structured data payload (tool calls, skill progress, subtask cards, suggestions)
- R4. Forward `values` events from DeerFlow's raw stream as SSE `values` events, preserving state snapshot data (plan todos, conversation state)
- R5. Forward `error` and `end` sentinel events in SSE format

### Agent-Side Event Pipeline

- R6. In `adapter.py`'s `raw_stream_dispatch()`, categorize each LangGraph event by type and yield typed tuples instead of raw events, preserving the event type distinction for downstream consumers
- R7. In `runs.py`'s `_sse_generator()`, emit `custom` events for tool calls, skill progress, and suggestions — not just the current `end`-only pattern
- R8. In the agent's chat router (`routers/chat.py`), forward all three event tracks when proxying to the backend, not just text content

### Backend Proxy Alignment

- R9. In `ai_chat.py`'s `proxy_stream()` generator, detect and forward SSE events from the agent service for all three tracks
- R10. Maintain backward compatibility for clients that still consume NDJSON (graceful period or version header)

### Cleanup & Resource Safety

- R11. Ensure `try/finally` in all streaming generators cleans up resources (HTTP connections, thread pool slots) regardless of which event track is being consumed
- R12. Ensure `GeneratorExit` (client disconnect) in the frontend closes the backend proxy stream, which in turn closes the agent's DeerFlow stream

---

## Key Decisions

- **Reuse DeerFlow's `format_sse()` function** — The agent's `runs.py` already defines `format_sse()` matching DeerFlow's canonical pattern; extend it for all event types rather than inventing a new format
- **Three-track event passthrough** — Rather than transforming events, pass through the DeerFlow event type and data structure with minimal adaptation (just serialize `data` to JSON)
- **NDJSON→SSE at the agent level** — The agent service already has access to raw LangGraph events via `raw_stream_dispatch()`; convert to SSE there rather than adding complexity to the backend proxy
- **Backend proxy as transparent relay** — The backend `ai_chat.py` proxies the agent's SSE stream without inspecting event types, simplifying maintenance
- **Thread-safe event queue** — The existing `asyncio.Queue` pattern in `raw_stream_dispatch()` already supports multi-type events; extend it to carry type annotations

---

## Key Flows

- F1. **Chat stream with full event tracks**
  - **Trigger:** User sends a message via `/ai/chat/stream`
  - **Steps:**
    1. Backend creates/loads session, sends to agent via `/runs/{thread_id}/stream`
    2. Agent's `_sse_generator()` iterates `raw_stream_dispatch()` yielding typed events
    3. For each raw event, `format_sse()` wraps it as `event: {type}\ndata: {json}\n\n`
    4. Agent yields events for all three tracks: `messages`, `custom`, `values`
    5. Backend proxies SSE bytes directly to frontend without parsing
    6. Frontend's EventSource or fetch stream dispatches by `event:` type
  - **Covered by:** R1-R9

- F2. **Tool call visualization via custom events**
  - **Trigger:** DeerFlow emits a tool call during agent execution
  - **Steps:**
    1. `raw_stream_dispatch()` yields the `messages-tuple` event with tool_calls
    2. Agent's SSE generator wraps as `event: custom\ndata: {"type":"tool_call","tool_name":"...","args":{...}}\n\n`
    3. Backend proxies to frontend
    4. Frontend renders tool call card in the chat UI
  - **Covered by:** R3, R6, R7

- F3. **State snapshot via values events**
  - **Trigger:** DeerFlow emits a `values` event with todos/state
  - **Steps:**
    1. `raw_stream_dispatch()` yields the `values` event
    2. Agent wraps as `event: values\ndata: {"todos":[...]}\n\n`
    3. Backend proxies to frontend
    4. Frontend updates plan/todo state display
  - **Covered by:** R4, R6, R7

---

## Scope Boundaries

- **Frontend Vue components** — Not in scope for this phase; frontend will need updates to consume the new SSE format, but the focus is on backend/agent protocol alignment
- **Session replay** — The `values` track enables future replay but full replay UI is deferred
- **Feedback events** — User feedback (thumbs up/down) events are deferred
- **Artifact events** — Code/file output events are deferred to a later phase

---

## Dependencies / Assumptions

- The agent's `raw_stream_dispatch()` already yields all LangGraph event types including `values` and `messages-tuple` with tool_calls — verified in `adapter.py`
- The backend's `httpx.AsyncClient.stream()` can forward SSE bytes transparently — already proven in `ai_chat.py`'s `proxy_stream()`
- The agent's `runs.py` SSE generator is the primary integration point — it already uses `format_sse()` and `text/event-stream`
- Frontend already uses `EventSource` or `fetch` with `text/event-stream` parsing capability

---

## Implementation Units

### U1. Extend agent `raw_stream_dispatch()` with typed event classification

**Goal:** Add event type annotation to yielded events so SSE generators can dispatch by type without re-parsing.

**Files:**
- `server/apps/agent/services/deerflow_adapter/adapter.py`

**Changes:**
- In `raw_stream_dispatch()`, wrap yielded events in a typed tuple `(event_type: str, event_data: dict)` instead of yielding raw LangGraph event objects
- Classify each event: `messages-tuple` → `"messages"`, `values` → `"values"`, `error` → `"error"`
- Keep the existing `StreamChunk` path for `stream_dispatch()` (used by non-chat capabilities)

**Test scenarios:**
- Verify `values` events are classified as `("values", data)`
- Verify `messages-tuple` events are classified as `("messages", data)`
- Verify error events are classified as `("error", data)`
- Verify backward compatibility — existing consumers (orchestrator, chat_adapter) unaffected

### U2. Enhance agent `runs.py` SSE generator with full event tracks

**Goal:** Emit SSE events for all three tracks from the runs endpoint.

**Files:**
- `server/apps/agent/routers/runs.py`

**Changes:**
- In `_sse_generator()`, iterate `raw_stream_dispatch()` and emit `format_sse(event_type, data)` for each typed event
- Emit `event: messages` for AI text content
- Emit `event: custom` for tool calls and skill progress
- Emit `event: values` for state snapshots
- Keep existing `custom` event for suggestions
- Keep existing `end` sentinel

**Test scenarios:**
- Verify SSE output contains `event: messages`, `event: custom`, `event: values` lines
- Verify `end` event still emitted after stream completes
- Verify error handling sends `event: error` on failure

### U3. Update backend `ai_chat.py` proxy for SSE passthrough

**Goal:** Forward SSE events from agent to frontend without parsing.

**Files:**
- `server/apps/backend/app/routers/ai_chat.py`

**Changes:**
- Change `proxy_stream()` media_type from `application/x-ndjson` to `text/event-stream`
- Forward bytes from agent stream directly without NDJSON line-by-line parsing
- Keep `session.start` event as first event
- Keep answer collection for persistence (collect from `messages` events)
- Add SSE-specific headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`

**Test scenarios:**
- Verify SSE bytes forwarded correctly from agent
- Verify `session.start` event still emitted first
- Verify answer persistence still works with new format
- Verify client disconnect cleanup still works

### U4. Add SSE headers and metadata

**Goal:** Ensure proper SSE streaming behavior across the proxy chain.

**Files:**
- `server/apps/backend/app/routers/ai_chat.py`
- `server/apps/agent/routers/runs.py`

**Changes:**
- Add `Cache-Control: no-cache` header to SSE responses
- Add `X-Accel-Buffering: no` header for nginx compatibility
- Add `Connection: keep-alive` header
- Set `Content-Type: text/event-stream` consistently

### U5. Backward compatibility layer

**Goal:** Support both NDJSON and SSE during migration.

**Files:**
- `server/apps/backend/app/routers/ai_chat.py`

**Changes:**
- Check `Accept` header: if `text/event-stream`, use SSE; otherwise keep NDJSON
- Or add a `/stream/sse` endpoint that uses SSE while `/stream` keeps NDJSON
- Document the deprecation path

---

## Verification

- **Unit tests:** `pytest server/tests/agent/unit/ -v` — verify adapter event classification
- **Integration tests:** `pytest server/tests/agent/integration/ -v` — verify SSE output from runs endpoint
- **Backend tests:** `pytest server/tests/backend/ -v -k "chat"` — verify proxy behavior
- **Manual:** Start agent + backend, send a chat request, observe SSE event types in the response
