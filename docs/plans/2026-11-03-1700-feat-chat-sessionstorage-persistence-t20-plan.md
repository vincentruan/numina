---
title: Chat SessionStorage Persistence - Plan
type: feat
date: 2026-11-03
topic: chat-sessionstorage-persistence-t20
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Chat streaming state survives page navigation and refresh, restoring the visible UI instantly from a sessionStorage snapshot while SSE reconnection replays incremental updates.
- **Product authority:** Frontend chat composable (`useThreadChat`) and its interaction with the SSE reconnection path (`streamChatRun`, `readSSEStream`).
- **Execution profile:** Code — frontend TypeScript changes in `frontend/apps/main/src/composables/ai-chat/`.

---

## Product Contract

### Summary

Add sessionStorage persistence to `useThreadChat`, replicating the `useReportStream` pattern (`numina:report-stream-state`). On page leave during an active stream, snapshot the current visible state (messages, tool calls, run_id, thread_id, status). On mount, restore the snapshot for instant UI, then reconnect SSE via `Last-Event-ID` to replay incremental updates. Dedup by message/tool-call IDs to handle snapshot-replay overlap. Clear on terminal state.

### Problem Frame

Users navigating away from `/ai/chat` during an active AI stream lose their place. The chat UI goes blank on return until the checkpointer's SSE replay catches up — which can take several seconds for long conversations. The report module already solves this with `useReportStream`'s sessionStorage pattern, but chat has no equivalent.

The gap is specifically the **instant UI restore** before SSE replay delivers events. The reconnection infrastructure (StreamBridge, RunManager, Last-Event-ID) already works; what's missing is the frontend-side snapshot that lets the UI render immediately on mount.

### Key Decisions

- **T20 and T21 are decoupled.** T20 proceeds as a pure frontend sessionStorage task. T21 (sync→async evaluation) concluded that DeerFlow upstream (harness b3f23326) does not support async streaming — `DeerFlowClient.stream()` is a synchronous generator. The current ThreadPoolExecutor bridge is correct and stable. The SSE wire format is identical regardless of sync/async backend, so T21's conclusion does not change T20's implementation. (session-settled: user-directed — chosen over coupling T20 to T21: SSE protocol is stable across sync/async boundary)
- **Medium persistence scope.** Persist messages snapshot + reconnection credentials (run_id, thread_id, status). Restore shows snapshot immediately, SSE replay fills incremental deltas. (session-settled: user-directed — chosen over minimal (reconnect-only) and full (all state): balances instant UI with dedup complexity)
- **Page-leave trigger only.** Save state only on `abort(keepRunning=true)` (page leave during active stream). No periodic snapshots during streaming. (session-settled: user-directed — chosen over periodic + event-driven: simplest pattern, matches useReportStream, covers the primary use case)

### Requirements

**Persistence**

- R1. When the user navigates away from `/ai/chat` during an active stream (status is `connecting` or `streaming`), the composable saves a snapshot to `sessionStorage` under key `numina:chat-stream-state`.
- R2. The snapshot includes: `status`, `threadId`, `runId`, `messages[]` (current visible messages including in-progress streaming text), `toolCalls[]`, `planningSteps[]`, and `lastEventId` (for SSE reconnection).

**Restore**

- R3. On composable mount, if `sessionStorage` contains a snapshot with status `connecting` or `streaming`, restore the snapshot to populate the UI immediately.
- R4. After restoring, initiate SSE reconnection via `Last-Event-ID` using the saved `runId` and `lastEventId`. The reconnection replays events from the StreamBridge buffer; the UI merges replay events with the restored snapshot.

**Dedup**

- R5. When merging SSE replay events with the restored snapshot, dedup by message ID and tool-call ID. If an event's ID already exists in the restored state, skip it. This prevents double-display when the replay overlaps with the snapshot.

**Clear**

- R6. Clear the `sessionStorage` snapshot when the stream reaches a terminal state (`completed`, `error`, or user-initiated `idle`). A fresh generation also clears any stale snapshot.

### Key Flows

- F1. Page leave during active stream
  - **Trigger:** User navigates away from `/ai/chat` while status is `connecting` or `streaming`.
  - **Steps:** `abort(keepRunning=true)` is called. The composable serializes current `messages[]`, `toolCalls[]`, `planningSteps[]`, `runId`, `threadId`, `lastEventId`, and `status` into a JSON object and writes it to `sessionStorage` under `numina:chat-stream-state`.
  - **Outcome:** State is persisted. The background stream continues running on the server.

- F2. Page return / refresh after leave
  - **Trigger:** User navigates back to `/ai/chat` or refreshes the page.
  - **Steps:** On mount, the composable reads `sessionStorage`. If a snapshot exists with active status, it restores `messages[]`, `toolCalls[]`, `planningSteps[]` to the reactive refs (instant UI). Then it calls `markReconnecting()` and initiates SSE reconnection via `streamChatRun` with `lastEventId` set. SSE events replay from StreamBridge; each event is deduped against the restored state (R5).
  - **Outcome:** User sees the chat UI immediately with the restored state. SSE replay fills in any events that arrived after the snapshot was taken.

- F3. Stream completion after restore
  - **Trigger:** SSE replay delivers the `end` event (status `complete` or `error`).
  - **Steps:** The composable processes the terminal event normally, updating status to `completed` or `error`. The `sessionStorage` snapshot is cleared (R6).
  - **Outcome:** Chat shows the final state. The snapshot is gone, so the next page visit starts fresh.

### Acceptance Examples

- AE1. Page leave and return during streaming
  - **Covers R1, R2, R3, R4, R5.**
  - **Given:** A chat stream is active (status `streaming`), 3 messages visible, 1 tool call in progress.
  - **When:** User navigates to another page, then returns to `/ai/chat`.
  - **Then:** The 3 messages and tool call render immediately from sessionStorage. SSE reconnects and replays any new events. If the replay includes events already in the snapshot (same message IDs), they are skipped.

- AE2. Stream completes while user is away
  - **Covers R3, R6.**
  - **Given:** A chat stream was active when the user left. The stream completes on the server.
  - **When:** User returns to `/ai/chat`.
  - **Then:** The sessionStorage snapshot is restored (showing the state at time of leave). SSE reconnection either replays remaining events or detects the run is already complete. On terminal state, the snapshot is cleared.

- AE3. Fresh conversation after completion
  - **Covers R6.**
  - **Given:** A previous stream completed and its sessionStorage snapshot was cleared.
  - **When:** User starts a new conversation.
  - **Then:** No stale snapshot is restored. The chat starts with an empty state.

### Scope Boundaries

**Deferred for later:**

- Periodic snapshots during streaming (would cover browser crash recovery, not just page leave).
- Full state mirror (goal state, todo state, thinking content) — the medium scope covers the primary use case; full mirror adds schema complexity without proportional UX gain.
- Server-side persistence of streaming state (frontend sessionStorage is sufficient for the stated problem).

**Outside this work:**

- T21 implementation (sync→async migration). T21's evaluation concluded "not feasible short-term without DeerFlow upstream changes." This is a separate architectural task, not part of T20.
- Changes to the SSE protocol, StreamBridge, or RunManager. The existing reconnection infrastructure is reused as-is.

### Sources / Research

- **Reference implementation:** `frontend/apps/main/src/composables/useReportStream.ts` — the `numina:report-stream-state` sessionStorage pattern that T20 replicates. Key functions: `saveStateToStorage()`, `restoreStateFromStorage()`, `clearSavedState()`, `markReconnecting()`.
- **DeerFlow harness API:** `server/apps/agent/deerflow_config/HARNESS_API.md` — confirms `DeerFlowClient.stream()` is a synchronous generator. T21 evaluation basis.
- **Chat composable:** `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` — the target for T20 changes. Currently has no sessionStorage persistence; relies on SSE replay + checkpointer reload.
- **SSE streaming API:** `frontend/apps/main/src/api/ai-chat.ts` — `streamChatRun()` async generator, supports `Last-Event-ID` for reconnection.
- **Backend SSE endpoint:** `server/apps/agent/routers/runs_stream.py` — `POST /api/threads/{id}/runs/stream` with StreamBridge + RunManager lifecycle. Supports reattach via `GET /api/threads/{id}/runs/{run_id}/stream`.
- **Chat types:** `frontend/apps/main/src/types/ai-chat/message-group.ts` — `ChatMessage`, `ToolCallSummary`, `PlanningStep` type definitions.

Product Contract unchanged.

---

## Planning Contract

### Key Technical Decisions

KTD1. **`lastEventId` promotion to ref.** Currently `lastEventId` is a local variable inside `sendMessage()` (line 1327 of `useThreadChat.ts`). To persist it across page navigation, it must become a module-level `ref<string | null>`. This is a minimal change — the local variable is replaced by the ref, and all read/write sites use `.value`. Governs R2, R4.

KTD2. **Snapshot schema mirrors `useReportStream` shape.** The `SavedChatState` interface follows the same pattern as `SavedStreamState` in `useReportStream.ts` — a flat JSON-serializable object with status, IDs, and state arrays. This keeps the implementation familiar and the storage key naming consistent (`numina:chat-stream-state`). Governs R1, R2.

KTD3. **Dedup via `messageIdentity()` function.** The composable already has a `messageIdentity()` helper (line 259) that extracts a stable ID from a `ChatMessage`. The dedup logic reuses this function rather than inventing a new identity scheme. Tool calls are deduped by their `id` field. Governs R5.

KTD4. **Restore + reconnect, not restore-only.** On mount, the composable restores the snapshot AND initiates SSE reconnection via the existing `streamChatRun` `lastEventId` parameter. This matches the `useReportStream` pattern where `markReconnecting()` + SSE replay work together. The snapshot provides instant UI; SSE replay fills deltas. Governs R3, R4.

### Assumptions

- The `streamChatRun()` API function already supports `lastEventId` in its options (confirmed at `frontend/apps/main/src/api/ai-chat.ts` line 102-104). No backend changes needed.
- The `onUnmounted` lifecycle hook in the composable's caller already triggers `abortLocalStream()`. The sessionStorage save is added inside `abortLocalStream()` — no new lifecycle hook needed.
- `sessionStorage` is available in all target browsers (mobile H5 + desktop). Quota exceeded errors are caught and silently ignored (matching `useReportStream` pattern).

---

## Implementation Units

### U1. Promote `lastEventId` to ref and define storage helpers

**Goal:** Make `lastEventId` persistent across the composable lifecycle and create the sessionStorage save/restore/clear infrastructure.

**Requirements:** R1, R2, R6

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` (modify)
- `frontend/apps/main/src/composables/ai-chat/__tests__/useThreadChat.sessionStorage.spec.ts` (create)

**Approach:**
1. Add module-level constant `SESSION_STORAGE_KEY = 'numina:chat-stream-state'` (following `useReportStream` naming).
2. Define `SavedChatState` interface with fields: `status`, `threadId`, `runId`, `lastEventId`, `messages` (serialized `ChatMessage[]`), `planningSteps`, `error`.
3. Add `ref<string | null>` for `lastEventId` at module level (near `runId` ref, line 587). Replace the local `let lastEventId = ''` in `sendMessage()` with reads/writes to `lastEventId.value`.
4. Implement three internal functions: `saveChatStateToStorage()`, `restoreChatStateFromStorage()`, `clearChatStateFromStorage()`. Each wraps `sessionStorage.setItem/getItem/removeItem` in try/catch (matching `useReportStream` error handling).
5. `saveChatStateFromStorage()` serializes: `isLoading.value` → status mapping (`true` → `'streaming'`), `currentThreadId`, `runId.value`, `lastEventId.value`, `messages.value` (filtered to visible messages), `planningSteps.value`, `error.value`.
6. `restoreChatStateFromStorage()` deserializes and populates refs. Only restores if saved status was `'streaming'` or `'connecting'` (terminal states are not restored — matching `useReportStream` guard at line 179).
7. Call `clearChatStateFromStorage()` in: `cancelStream()`, terminal state handling (end event with `complete`/`error`), and `sendMessage()` start (fresh generation clears stale snapshot).

**Patterns to follow:** `useReportStream.ts` lines 36-37 (SESSION_STORAGE_KEY), 121-193 (SavedStreamState + save/restore/clear functions).

**Test scenarios:**
- `saveChatStateToStorage()` writes valid JSON to sessionStorage with correct key
- `restoreChatStateFromStorage()` returns null when no saved state exists
- `restoreChatStateFromStorage()` returns null when saved status is `completed` or `error` (terminal state guard)
- `restoreChatStateFromStorage()` populates refs when saved status is `streaming`
- `clearChatStateFromStorage()` removes the key from sessionStorage
- All functions handle `sessionStorage` unavailability gracefully (try/catch)

**Verification:** Unit tests pass. `lastEventId` ref is readable/writable from `sendMessage()` and exposed in the composable return.

---

### U2. Save state on page leave

**Goal:** When the user navigates away during an active stream, persist the current chat state to sessionStorage.

**Requirements:** R1, R2

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` (modify)

**Approach:**
1. In `abortLocalStream()` (line 1915), add a guard: if `isLoading.value` is true (stream is active), call `saveChatStateToStorage()` before aborting.
2. The save captures the current state snapshot — messages visible at the moment of leave, the active runId, and the lastEventId received so far.
3. Do NOT save on `cancelStream()` — that's a user-initiated cancel, not a page leave. The user explicitly stopped the stream; there's nothing to restore.

**Patterns to follow:** `useReportStream.ts` lines 238-249 (`abort(keepRunning=true)` path that calls `saveStateToStorage()`).

**Test scenarios:**
- `abortLocalStream()` with `isLoading=true` writes state to sessionStorage
- `abortLocalStream()` with `isLoading=false` does NOT write to sessionStorage (no active stream)
- `cancelStream()` does NOT write to sessionStorage (user-initiated cancel)
- Saved state includes current messages, runId, threadId, lastEventId

**Verification:** Manual test: start a chat stream, navigate away, return — sessionStorage has the snapshot. Unit tests pass.

---

### U3. Restore state on mount and reconnect SSE

**Goal:** When the composable mounts and finds a saved snapshot, restore it for instant UI and initiate SSE reconnection.

**Requirements:** R3, R4

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` (modify)

**Approach:**
1. At composable initialization (after refs are declared), call `restoreChatStateFromStorage()`. If it returns a saved state, populate `messages.value`, `planningSteps.value`, `runId.value`, `lastEventId.value`, `error.value` from the snapshot.
2. Set `isLoading.value = true` to show the streaming UI (the restored state was mid-stream).
3. Expose a `markReconnecting()` function (following `useReportStream` pattern) that sets the UI into "reconnecting" mode — shows the streaming indicators while SSE replay catches up.
4. The SSE reconnection is initiated by the page component (e.g., `AIChatPage.vue`) after detecting the restored state. It calls `streamChatRun()` with `lastEventId` set to the restored value, which triggers the backend's `Last-Event-ID` replay from the StreamBridge buffer.
5. Alternatively, if the composable auto-starts streams (e.g., via `useTaskResume`), the reconnection happens automatically when the composable detects `runId` is set and `isLoading` is true.

**Patterns to follow:** `useReportStream.ts` lines 172-197 (`restoreStateFromStorage()` called at line 197 during composable init) and lines 261-269 (`markReconnecting()` function).

**Test scenarios:**
- Composable mount with saved `streaming` state populates messages and sets isLoading=true
- Composable mount with no saved state starts with empty messages and isLoading=false
- Composable mount with saved `completed` state does NOT restore (terminal state guard)
- Restored state exposes correct `runId` and `lastEventId` for SSE reconnection

**Verification:** Manual test: start stream → navigate away → return → messages appear instantly, SSE reconnects. Unit tests pass.

---

### U4. Dedup SSE replay events against restored snapshot

**Goal:** When SSE replay events arrive after a restore, skip events whose IDs already exist in the restored state.

**Requirements:** R5

**Dependencies:** U1, U3

**Files:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` (modify)

**Approach:**
1. Add a `restoredMessageIds` set (module-level ref or local variable) that tracks message IDs from the restored snapshot.
2. When the composable restores from sessionStorage (U3), populate `restoredMessageIds` with the IDs of all restored messages (using `messageIdentity()` at line 259).
3. In the SSE event handlers (`mergeMessagesTuple`, `mergeValuesMessages`), before adding a new message or tool call, check if its ID is in `restoredMessageIds`. If yes, skip it.
4. After the SSE replay catches up (e.g., after a `values` event with a full state snapshot), clear `restoredMessageIds` — the canonical state has superseded the restored snapshot.
5. Tool call dedup: check `toolCall.id` before adding to any tool-call tracking array.

**Patterns to follow:** `useReportStream.ts` lines 348-349 (tool call dedup: `if (id && toolCalls.value.some(c => c.id === id)) continue`) and lines 372-373 (tool result dedup).

**Test scenarios:**
- SSE replay event with message ID matching restored snapshot is skipped
- SSE replay event with new message ID (not in snapshot) is added normally
- After full `values` event, restoredMessageIds is cleared and subsequent events are not deduped
- Tool call with duplicate ID is skipped; new tool call is added

**Verification:** Manual test: start stream → navigate away → return → SSE replays → no duplicate messages visible. Unit tests pass.

---

### U5. Clear snapshot on terminal state

**Goal:** Ensure the sessionStorage snapshot is cleared when the stream completes, errors, or a new generation starts.

**Requirements:** R6

**Dependencies:** U1

**Files:**
- `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts` (modify)

**Approach:**
1. In the SSE `end` event handler, when status is `complete` or `error`, call `clearChatStateFromStorage()`.
2. In `cancelStream()`, call `clearChatStateFromStorage()` (user explicitly cancelled — no restore needed).
3. At the start of `sendMessage()`, call `clearChatStateFromStorage()` (fresh generation — stale snapshot from a previous run should not interfere).
4. This follows the `useReportStream` pattern where `setTerminalStatus()` (line 167) clears saved state, and `reset()` (line 217) also clears it.

**Patterns to follow:** `useReportStream.ts` lines 154-160 (`clearSavedState()`), 167-170 (`setTerminalStatus()` calls `clearSavedState()`), 235 (`reset()` calls `clearSavedState()`).

**Test scenarios:**
- SSE `end` event with status `complete` clears sessionStorage
- SSE `end` event with status `error` clears sessionStorage
- `cancelStream()` clears sessionStorage
- `sendMessage()` start clears sessionStorage (fresh generation)
- After clear, a subsequent mount finds no saved state

**Verification:** Manual test: complete a stream → check sessionStorage is empty. Start new stream → no stale snapshot. Unit tests pass.

---

## Verification Contract

| Check | Command | Scope |
|-------|---------|-------|
| Type check | `pnpm -r typecheck` | All TypeScript compiles without errors |
| Lint | `pnpm -r lint` | No lint violations |
| Unit tests | `pnpm -r test:run` | All existing + new sessionStorage tests pass |
| New test file | `frontend/apps/main/src/composables/ai-chat/__tests__/useThreadChat.sessionStorage.spec.ts` | Covers U1-U5 test scenarios |

---

## Definition of Done

- [ ] U1-U5 implemented and all unit tests pass
- [ ] `lastEventId` promoted to ref, no regressions in existing `sendMessage()` flow
- [ ] Page leave during stream → sessionStorage has snapshot → return → UI restores instantly
- [ ] SSE reconnection after restore → no duplicate messages (dedup works)
- [ ] Terminal state (complete/error/cancel) → sessionStorage cleared
- [ ] New conversation → no stale snapshot restored
- [ ] `pnpm -r typecheck && pnpm -r lint && pnpm -r test:run` all pass
- [ ] No changes to backend, SSE protocol, or StreamBridge (frontend-only change)
