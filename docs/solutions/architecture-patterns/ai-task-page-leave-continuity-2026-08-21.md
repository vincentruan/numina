---
date: 2026-08-21
module: ai-chat, dashboard
problem_type: runtime-error
tags: [ai-task, page-leave, sse, keepalive, lifecycle, bridge-consumer]
applies_when: "User navigates away from an active AI task page and the task gets interrupted or lost"
---

# AI Task Page-Leave Continuity

## Problem

When a user navigates away from a page with an active AI task (chat, narrative, report, etc.), the task gets interrupted:

1. **Chat (P0)**: Frontend SSE proxy breaks → backend proxy loop exits → AITask marked completed immediately → agent run cancelled (default `on_disconnect=cancel`) → user returns to find incomplete task with no recovery path.

2. **Narrative on KeepAlive Dashboard (P1)**: `onUnmounted` fires on KeepAlive deactivate → calls `cleanup()` which resets all state → user returns to find empty card even though task is still running.

## Context

The AI task system has two disconnect paths with different semantics:

- **Bridge consumer** (`_spawn_lifecycle_consumer`): Independent background asyncio task that subscribes to the bridge stream and survives SSE disconnect. Calls `complete_task()` on "end" event. Used by report, coach, wish-advice, narrative.
- **Direct SSE proxy**: Backend proxies agent SSE to frontend. When frontend disconnects, proxy loop breaks. Used by chat.

The agent's `sse_consumer` checks `record.on_disconnect` — `"cancel"` (default) aborts the background task, `"continue"` lets it run to completion.

Frontend `useTaskResume` has two teardown methods:
- `disconnect()`: Lightweight — aborts SSE, stops polling, preserves state for re-activation.
- `cleanup()`: Full teardown — resets all state including `taskId`, `status`, `task`.

Vue 3 KeepAlive pages fire `onDeactivated` on navigation away and `onUnmounted` only when permanently destroyed. Using `cleanup()` in `onUnmounted` without `disconnect()` in `onDeactivated` loses state on every tab switch.

## Solution

### Fix 1: Chat page-leave continuity

**Backend** (`routers/ai_chat.py`):
1. Set `"on_disconnect": "continue"` in the agent request — the agent run survives frontend disconnect.
2. Extract `run_id` from `Content-Location` response header for lifecycle tracking.
3. On client disconnect, spawn `_spawn_lifecycle_consumer` to detect agent completion via the bridge and mark the AITask later.
4. On natural stream end (no disconnect), mark completed immediately as before.

**Agent** (`runtime/worker.py`):
- Emit `chat.completed` custom event at the end of `_run_numina_agent` for lifecycle tracking. The `END_SENTINEL` (published by `RunPipeline.__aexit__`) triggers `complete_task()` in the lifecycle consumer.

**Frontend** (`useThreadChat.ts` + `AIChatBox.vue`):
- New `abortLocalStream()` function: aborts SSE locally WITHOUT sending `client.runs.cancel()` to the agent. The agent run continues in the background.
- `AIChatBox.onUnmounted` uses `abortLocalStream()` instead of `cancelStream()`.
- User returns → `checkChatTask()` detects running AITask → `loadHistory()` reloads from checkpointer.

### Fix 2: Narrative KeepAlive lifecycle

**Frontend** (`DashboardNarrativeCard.vue`):
- Add `onDeactivated` handler: clears `taskCheckTimer`, aborts in-flight SSE, calls `resumeHandle.disconnect()` (lightweight).
- Simplify `onUnmounted` to just `resumeHandle.cleanup()` (full teardown only when permanently destroyed).

## Prevention

1. **New AI task types**: Always set `on_disconnect: "continue"` in agent request + spawn lifecycle consumer on disconnect. Never rely on the SSE proxy loop to mark task completion.
2. **KeepAlive pages with AI tasks**: Always pair `onDeactivated` (disconnect) with `onUnmounted` (cleanup). Use `disconnect()` for tab switches, `cleanup()` for permanent destruction.
3. **Frontend SSE cleanup**: Distinguish between "user explicitly cancelled" (`cancelStream()` → sends server cancel) and "user navigated away" (`abortLocalStream()` → local abort only, agent continues).
4. **Test checklist**: When adding AI task features, verify page-leave behavior by navigating away mid-task and returning. The task should resume or show completion state.
