# AI Chat Redesign — Design Spec

> **Status:** Design approved, pending implementation planning
> **Date:** 2026-06-18 (updated 2026-06-18)
> **Designer:** Claude (brainstorming with user)

## Overview

Rewrite the AI Chat page to replicate DeerFlow's chat interaction pattern using LangGraph SDK streaming. The existing `AIChatPage.vue` is replaced with a new component hierarchy at the same `/ai/chat` route.

### Core Philosophy

Numina's agent module wraps DeerFlow. Beyond tenant isolation and availability, all customizations are "over-engineering." The design mirrors DeerFlow's architecture and UX patterns directly, adapting only where Vue/H5 constraints or Numina's proxy layer require it.

---

## 1. Current State — What Already Exists

The Phase 3 AI Chat refactor already implemented most DeerFlow-mirrored components under `components/ai-chat/`. These are **preserved and reused** — the redesign adds the top-level orchestration layer on top.

### Already Implemented

| File | Purpose | Reuse? |
|------|---------|--------|
| `pages/AIChatPage.vue` | Current monolithic chat page | **Replace** with new hierarchy |
| `components/ai-chat/InputBox.vue` | Textarea + mode/model selector + suggestions | **Preserve**, minor interface updates |
| `components/ai-chat/ModeSelector.vue` | 4-mode segmented control (flash/thinking/pro/ultra) | **Preserve** |
| `components/ai-chat/ModelSelectorPopup.vue` | Agent/model picker popup | **Preserve** |
| `components/ai-chat/WelcomeExamples.vue` | Welcome suggestion cards | **Preserve**, integrate into WelcomePage |
| `components/ai-chat/MessageGroup.vue` | Message group renderer (human/assistant/processing) | **Preserve** |
| `components/ai-chat/MarkdownContent.vue` | Markdown rendering | **Preserve** |
| `components/ai-chat/ChainOfThought.vue` | CoT reasoning display | **Preserve** |
| `components/ai-chat/ChainOfThoughtSearchResults.vue` | Search results in CoT | **Preserve** |
| `components/ai-chat/CodeBlock.vue` | Code block with copy | **Preserve** |
| `components/ai-chat/CopyButton.vue` | Copy to clipboard | **Preserve** |
| `components/ai-chat/SubtaskCard.vue` | Sub-agent task card | **Preserve** |
| `components/ai-chat/ArtifactFileList.vue` | Artifact file list | **Preserve** |
| `components/ai-chat/ArtifactPreviewPopup.vue` | Artifact preview popup | **Preserve** |
| `components/ai-chat/TokenUsage.vue` | Token usage display | **Preserve** |
| `components/ai-chat/FlipDisplay.vue` | Title change animation | **Preserve** |
| `components/ai-chat/ShimmerText.vue` | Shimmer loading effect | **Preserve** |
| `components/ai-chat/ShineBorder.vue` | Border glow effect | **Preserve** |
| `components/ai-chat/AuroraText.vue` | Aurora text effect | **Preserve** |
| `components/ai-chat/SuggestionChip.vue` | Suggestion chip | **Preserve** |
| `components/ai-chat/SuggestionConfirmDialog.vue` | Confirm dialog for actions | **Preserve** |
| `composables/ai-chat/useThreadChat.ts` | LangGraph SDK stream composable (228 lines) | **Rewrite** — too coupled to old page |
| `composables/ai-chat/useMessageGroups.ts` | Message grouping logic | **Preserve** |
| `composables/ai-chat/useArtifacts.ts` | Artifact state | **Preserve** |
| `composables/ai-chat/useSubtasks.ts` | Subtask state | **Preserve** |
| `composables/ai-chat/useTenantAiResources.ts` | Agent/mode/provider resolution | **Preserve** |
| `api/sessions.ts` | LangGraph SDK proxy calls (search, patch, delete) | **Preserve** |
| `stores/ai.ts` | AI provider config store | **Preserve** |
| `types/ai-chat/message-group.ts` | ChatMessage, MessageGroup, Artifact, ToolCallSummary types | **Preserve** |
| `types/ai-chat/input-mode.ts` | InputMode, SubmitPayload types | **Preserve** |
| `types/ai-chat/subtask.ts` | Subtask types | **Preserve** |
| `utils/ai-chat/messageAdapter.ts` | LangGraph message → UI message | **Preserve** |
| `utils/ai-chat/messageGroups.ts` | Message grouping | **Preserve** |
| `utils/ai-chat/reasoning-filter.ts` | Reasoning content filtering | **Preserve** |
| `utils/ai-chat/tool-explainer.ts` | Tool call display helpers | **Preserve** |

### What's Missing (the Delta)

| Need | Status |
|------|--------|
| Top-level orchestration component (AIChatBox) | **New** |
| Welcome/chat mode switching | **New** |
| Session sidebar with pinning, date grouping | **New** |
| URL management via history.replaceState | **New** |
| Thread list composable (useThreadList) | **New** |
| Chat session Pinia store | **New** |
| Dedicated API module for LangGraph SDK client | **New** |
| Rewritten useThreadChat (clean interface) | **Rewrite** |
| Route: AIChatPage.vue → pages/ai/chat/index.vue | **Move** |

---

## 2. Component Architecture

### Top-Level Container: `AIChatBox.vue`

Mounted by `pages/ai/chat/index.vue`. Two modes:

| Mode | Condition | Renders |
|------|-----------|---------|
| **Welcome** | No active thread | `WelcomePage` (reuses `WelcomeExamples`) |
| **Chat** | Active thread exists | `MessageList` (reuses `MessageGroup`) + `InputBox` |

```
pages/ai/chat/index.vue        ← Route entry, mounts AIChatBox
└── AIChatBox.vue              ← Root container, mode switch (Welcome / Chat)
    ├── SessionSidebar.vue     ← Click-to-expand sidebar overlay (NEW)
    ├── [Welcome mode]
    │   └── WelcomePage.vue    ← Centered hero (NEW, uses WelcomeExamples)
    └── [Chat mode]
        ├── MessageList.vue    ← Scrollable messages (NEW, uses MessageGroup)
        └── InputBox.vue       ← Existing, preserved
```

### Key Differences from DeerFlow

| Aspect | DeerFlow (React) | Numina (Vue) |
|--------|------------------|--------------|
| State management | React hooks + React Query | Pinia store + composables |
| Stream hook | `useStream` from `@langchain/langgraph-sdk/react` | Custom `useThreadChat` composable |
| Session list | Always-visible sidebar | Click-to-expand sidebar overlay |
| Routing | React Router | `history.replaceState()` |

---

## 3. Data Flow & LangGraph SDK Streaming

### LangGraph SDK Integration

Already a dependency (`@langchain/langgraph-sdk` in `package.json`). Used directly — no additional wrapper.

```typescript
import { Client } from "@langchain/langgraph-sdk";
```

### Client Configuration

```typescript
const client = new Client({
  apiUrl: "/api", // proxied by Numina backend
});
```

The Numina backend proxy (`ai_threads.py`) intercepts all `/api/threads/{path}` requests transparently.

### Stream Modes

```typescript
const stream = client.runs.stream(threadId, assistantId, {
  input: messages,
  streamMode: ["messages", "values", "updates"],
});
```

---

## 4. ⚠️ Critical: Backend Streaming Protocol Alignment

### Current Problem (MUST FIX)

Numina currently has **two conflicting streaming protocols** for chat:

| Protocol | Content-Type | Endpoints | Issue |
|----------|-------------|-----------|-------|
| LangGraph SSE | `text/event-stream` | `POST /api/threads/{id}/runs/stream` | ✅ Correct (runs.py) |
| NDJSON events | `application/x-ndjson` | `GET /api/v1/ai/sessions/{id}/events` (via `agent_dispatch.py` → `EventStreamBuilder`) | ❌ Chat must be removed |

The NDJSON protocol used for chat history loading (`streamSessionEvents` → `GET /api/v1/ai/sessions/{id}/events`) is a **Numina invention** that:
1. Breaks compatibility with `@langchain/langgraph-sdk/react`'s `useStream` hook
2. Requires custom frontend parsing (`streamSessionEvents` → NDJSON reader)
3. Cannot use `onCreated`, `onUpdateEvent`, `onCustomEvent` lifecycle hooks
4. Prevents thread history loading via `client.runs.list(threadId)` + `client.runs.get(threadId, runId)/messages`
5. Bypasses LangGraph checkpointer for message retrieval

**Note:** The NDJSON protocol is also used by non-chat capabilities (alerts, allocation, disposal, liability, report, spending_leak, time_machine). Those are **NOT affected** by this change — they use `agent_dispatch.py` directly for capability-specific streaming and don't need the LangGraph SDK chat lifecycle. Only the chat NDJSON path is being removed.

### Target State

**Only one streaming protocol**: LangGraph SSE (`text/event-stream`), as already implemented in `runs.py`.

**Remove these from chat path**:
- `frontend/api/sessions.ts::streamSessionEvents()` — NDJSON reader for chat history loading
- `frontend/pages/AIChatPage.vue` lines that import and call `streamSessionEvents` (line 311, 1047)
- All other capability routers (alerts, allocation, disposal, liability, report, spending_leak, time_machine) continue using `agent_dispatch.py` → `EventStreamBuilder` for their own NDJSON streams — those are **NOT removed**

**Keep and enhance**:
- `routers/runs.py` — already uses LangGraph SSE format, the canonical path for chat
- `routers/threads.py` — already implements standard thread CRUD + state + history
- `services/agent_dispatch.py` — continues to exist for non-chat capability streaming (alerts, allocation, etc.)

### Migration Plan

#### Phase A: Backend — Add Missing LangGraph Endpoints

1. **Add** missing LangGraph Platform endpoints to `routers/runs.py`:

| Endpoint | Purpose | DeerFlow Reference |
|----------|---------|-------------------|
| `GET /api/threads/{id}/runs` | List runs for history loading | `thread_runs.py:list_runs` |
| `GET /api/threads/{id}/runs/{run_id}` | Get run details | `thread_runs.py:get_run` |
| `GET /api/threads/{id}/runs/{run_id}/messages` | Paginated run messages | `thread_runs.py:list_run_messages` |
| `POST /api/threads/{id}/runs/{run_id}/cancel` | Cancel/stop a run | `thread_runs.py:cancel_run` |
| `GET /api/threads/{id}/runs/{run_id}/join` | Join existing run's SSE | `thread_runs.py:join_run` |
| `GET/POST /api/threads/{id}/runs/{run_id}/stream` | Stream existing/stop-then-stream | `thread_runs.py:stream_existing_run` |

3. **Enhance** `routers/runs.py` — add required request fields for `@langchain/langgraph-sdk` compatibility:

The `@langchain/langgraph-sdk/react` `useStream` hook sends these fields in `RunCreateRequest`. The Numina version must accept them:

```python
class RunCreateRequest(BaseModel):
    assistant_id: str | None = None
    input: dict[str, Any] | None = None
    command: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    context: dict[str, Any] | None = None         # ← ADD: model_name, thinking_enabled, etc.
    webhook: str | None = None                      # ← ADD
    checkpoint_id: str | None = None                # ← ADD: resume from checkpoint
    checkpoint: dict[str, Any] | None = None        # ← ADD
    interrupt_before: list[str] | str | None = None # ← ADD
    interrupt_after: list[str] | str | None = None  # ← ADD
    stream_mode: list[str] | str | None = None      # ← ADD
    stream_subgraphs: bool = False                  # ← ADD: for subagent streaming
    stream_resumable: bool | None = None            # ← ADD: for SSE resumable
    on_disconnect: Literal["cancel", "continue"] = "cancel"  # ← ADD
    multitask_strategy: Literal["reject", "rollback", "interrupt", "enqueue"] = "reject"  # ← ADD
    feedback_keys: list[str] | None = None          # ← ADD
```

4. **Remove** `frontend/api/sessions.ts::streamSessionEvents()` — replace all callers with `client.runs.stream()`.

#### Phase B: Frontend — Switch to useStream() Hook

Replace the custom `useThreadChat` composable with DeerFlow's pattern based on `@langchain/langgraph-sdk/react`'s `useStream`:

```typescript
// Current (WRONG): custom NDJSON parsing
import { streamSessionEvents } from '@/api/sessions'
const reader = await streamSessionEvents(sessionId)
// ... manual NDJSON line parsing ...

// Target (RIGHT): LangGraph SDK useStream
import { useStream } from '@langchain/langgraph-sdk/react'
const thread = useStream({
  client: getAPIClient(),
  assistantId: "lead_agent",
  threadId: currentThreadId,
  reconnectOnMount: true,
  fetchStateHistory: { limit: 1 },
  onCreated: (meta) => {
    history.replaceState(null, "", `/ai/chat?thread_id=${meta.thread_id}`);
    setThreadId(meta.thread_id);
  },
  onFinish: (state) => {
    // Update token usage, invalidate thread list cache
  },
  onError: (error) => {
    // Show error toast, clear optimistic state
  },
  onUpdateEvent: (data) => {
    // Handle title updates from summarization middleware
  },
});
```

### Why This Is Critical

The `useStream` hook from `@langchain/langgraph-sdk/react` provides:

| Feature | useStream (SDK) | Custom NDJSON |
|---------|----------------|---------------|
| Auto-reconnect | ✅ Built-in | ❌ Manual |
| History merging | ✅ Built-in | ❌ Custom |
| Optimistic messages | ✅ First-class | ❌ Manual |
| `onCreated` lifecycle | ✅ Thread ID → URL | ❌ Missing |
| `onUpdateEvent` (title) | ✅ Real-time title updates | ❌ Missing |
| `onFinish` callback | ✅ Token usage + cache | ❌ Missing |
| `onError` handling | ✅ Toast + state cleanup | ❌ Manual |
| Summarization support | ✅ Middleware messages | ❌ Missing |
| Abort/stop | ✅ Cancel run endpoint | ❌ AbortController |
| SSE resumable | ✅ `streamResumable` option | ❌ Not supported |

Without this migration, every feature above must be reimplemented manually, creating ongoing drift from DeerFlow upstream.

---

## 5. Composable: `useThreadChat.ts` (Rewrite)

Rewritten to wrap `useStream` from `@langchain/langgraph-sdk/react` with Numina's tenant context.

```typescript
function useThreadChat() {
  const messages = ref<ChatMessage[]>([]);
  const isStreaming = ref(false);
  const error = ref<string | null>(null);
  const tokenUsage = ref<TokenUsage | null>(null);

  async function sendMessage(text: string, mode?: InputMode): Promise<void>;
  function cancelStream(): void;
  async function loadHistory(threadId: string): Promise<void>;

  return { messages, isStreaming, error, tokenUsage, sendMessage, cancelStream, loadHistory };
}
```

### Detailed Implementation Pattern

```typescript
import { useStream } from '@langchain/langgraph-sdk/react'
import { getAPIClient } from '@/api/langgraph'
import { useQueryClient } from '@/composables/useQueryClient'

export function useThreadChat(options: {
  threadId?: string | null
  isNewThread?: boolean
  context: LocalSettings['context']
  onSend?: () => void
  onStart?: (threadId: string) => void
  onFinish?: (state: AgentThreadState) => void
}) {
  const queryClient = useQueryClient()
  const [optimisticMessages, setOptimisticMessages] = useState<Message[]>([])
  const [isUploading, setIsUploading] = useState(false)

  const thread = useStream<AgentThreadState>({
    client: getAPIClient(),
    assistantId: "lead_agent",
    threadId: options.threadId,
    reconnectOnMount: true,
    fetchStateHistory: { limit: 1 },
    onCreated(meta) {
      // Update URL + thread ID
      history.replaceState(null, "", `/ai/chat?thread_id=${meta.thread_id}`)
      options.onStart?.(meta.thread_id)
      // Update thread list cache
      upsertThreadInCache(queryClient, {
        thread_id: meta.thread_id,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        metadata: {},
        status: "busy",
        values: { title: "New Chat", messages: [], artifacts: [] },
      })
    },
    onUpdateEvent(data) {
      // Handle title updates from backend summarization
      for (const update of Object.values(data || {})) {
        if (update && "title" in update && update.title) {
          upsertThreadTitleInCache(queryClient, threadIdRef.current, update.title)
        }
      }
    },
    onError(error) {
      setOptimisticMessages([])
      showFailToast(t('aiChat.errors.streamFailed'))
    },
    onFinish(state) {
      options.onFinish?.(state.values)
      invalidateThreadCache(queryClient)
    },
  })

  const sendMessage = async (text: string, files?: File[]) => {
    // 1. Show optimistic user message
    // 2. Upload files if present
    // 3. Submit via thread.submit() with context
    // 4. Handle errors → remove optimistic + show toast
  }

  const cancelStream = () => {
    // Calls POST /api/threads/{id}/runs/{run_id}/cancel
    thread.stop()
  }

  const loadHistory = async (threadId: string) => {
    // Uses client.threads.getState() or useThreadHistory()
  }

  return { thread, messages, isStreaming, error, tokenUsage, sendMessage, cancelStream, loadHistory, isUploading }
}
```

### Attachment Upload Constraints

The input box supports three attachment types: file, image, and camera capture. All three share these constraints:

| Constraint | Value | Notes |
|------------|-------|-------|
| **Max file size (per file)** | 20 MB | Server-side validation mirrors client-side |
| **Max total upload per message** | 50 MB | Sum of all files in a single send |
| **Max files per message** | 10 | UI constraint — more than 10 degrades UX |
| **Allowed image MIME types** | `image/jpeg`, `image/png`, `image/gif`, `image/webp` | No SVG (XSS risk) |
| **Allowed document MIME types** | `application/pdf`, `text/plain`, `text/csv`, `application/json` | Extensible if LLM supports more |
| **Image rendering** | Thumbnail grid (max 4 per row), tap for full-size modal | Reuses existing viewer components if available |
| **Document rendering** | File card: icon + filename + size + download button | No inline preview for non-image files |
| **Server-side rejection** | Return 413 (too large) or 415 (unsupported type) with Chinese detail message | Match existing error convention |
| **Tenant storage quota** | Check family storage quota before accepting upload | If exceeded → 413 with "存储配额不足" |

**DeerFlow alignment:** Verify DeerFlow's upload behavior during implementation. If DeerFlow supports additional file types or has different size limits, adjust accordingly.

### Optimistic UI Pattern

| Action | Optimistic | Fallback on error |
|--------|------------|-------------------|
| Send message | Show user message with "sending" indicator | Remove message + error toast |
| Delete session | Remove from list | Re-add + error toast |
| Rename session | Update title | Revert + error toast |
| Pin/Unpin | Update UI | Revert + error toast |

### Cancellation

- **Stop generation**: POST to cancel endpoint → stops token rendering
- Input box shows "Stop" button during streaming, reverts to "Send" when idle
- On stop: mark the last assistant message as `interrupted`, clear optimistic state

### InputBox Mobile Keyboard Handling

Vant4 is a mobile-first UI library. The chat input bar must handle soft keyboard events properly:

| Aspect | Behavior |
|--------|----------|
| **Viewport tracking** | Use `visualViewport` API (`window.visualViewport.onresize`) to detect keyboard open/close. Do NOT rely on `window.innerHeight` — iOS Safari does not update it during keyboard transitions. |
| **Input bar positioning** | When keyboard opens, adjust the input bar to sit above the keyboard using `visualViewport.height` delta. On iOS, avoid `position: fixed` — Safari ignores it when keyboard is open. Use `position: sticky` with dynamic `bottom` offset instead. |
| **Auto-scroll on keyboard open** | When keyboard opens and the user was at the bottom of the chat, auto-scroll to keep the latest message visible. |
| **Dismiss on scroll** | When the user scrolls up in the message area while the keyboard is open, dismiss the keyboard. |
| **Android** | Standard `resize` behavior — ensure the chat container shrinks correctly. No special handling needed beyond `visualViewport` tracking. |

**Implementation note:** Extract this into a shared `useMobileKeyboard` composable if not already present in the project, since it applies to any page with a fixed-bottom input bar (including `/ai` page).

---

## 6. Composable: `useThreadList.ts` (New)

```typescript
function useThreadList() {
  const sessions = ref<ThreadSession[]>([]);
  const isLoading = ref(false);
  const hasMore = ref(true);

  async function loadMore(): Promise<void>;
  async function refresh(): Promise<void>;
  async function deleteSession(threadId: string): Promise<void>;
  async function renameSession(threadId: string, title: string): Promise<void>;
  async function togglePin(threadId: string, isPinned: boolean): Promise<void>;

  return { sessions, isLoading, hasMore, loadMore, refresh, deleteSession, renameSession, togglePin };
}
```

### Implementation: React Query Pattern

DeerFlow uses `@tanstack/react-query` for thread list management with cache invalidation. In Vue, we use Pinia with manual cache management, or integrate `@tanstack/vue-query` if already present.

```typescript
// API call via LangGraph SDK
const response = await client.threads.search({
  limit: INFINITE_THREADS_PAGE_SIZE,
  offset: pageParam,
  sortBy: "updated_at",
  sortOrder: "desc",
  select: ["thread_id", "updated_at", "values", "metadata"],
}) as AgentThread[]
```

### Thread Search Sort Order

The `/threads/search` endpoint must support `sortBy` and `sortOrder` parameters for correct frontend display:

| Field | Default | Description |
|-------|---------|-------------|
| `sortBy` | `updated_at` | Sort field |
| `sortOrder` | `desc` | Sort direction |
| `metadata.is_pinned` | — | Pinned threads appear first |

**Backend changes required:**

Add to `ThreadSearchRequest`:
```python
class ThreadSearchRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    status: str | None = Field(default=None)
    sortBy: str | None = Field(default="updated_at")       # NEW
    sortOrder: str | None = Field(default="desc")           # NEW
```

`AiSessionRepository.list_sessions()` must forward sort params to `BackendClient.list_sessions()`.

---

## 7. Session Management

### SessionSidebar.vue

Click-to-expand sidebar overlay (from right edge). Aligned with DeerFlow's `RecentChatList`.

#### Layout

```
┌──────────────────────────────┐
│  [Close] 会话历史             │
├──────────────────────────────┤
│ 📌 置顶                      │  ← Pinned section (if any)
│ ├ 会话标题 1           [···]  │
├──────────────────────────────┤
│ 今天                         │  ← Today group
│ ├ 会话标题 3           [···]  │
├──────────────────────────────┤
│ 昨天                         │  ← Yesterday group
├──────────────────────────────┤
│ 更早                         │  ← Older
└──────────────────────────────┘
```

Each session row shows: title (truncated 1 line), relative timestamp, context menu (`···`) with Rename, Pin/Unpin, Delete.

#### Date Grouping

```
if (pinned) → "📌 置顶"
else if (updated_at is today) → "今天"
else if (updated_at is yesterday) → "昨天"
else → "更早"
```

#### Infinite Scroll

IntersectionObserver on last item → `loadMore()`.

### Pinning

- `AIChatSession.is_pinned` already exists on model — stored server-side
- Frontend calls `PATCH /api/threads/{id}` with `{"metadata": {"is_pinned": true|false}}`
- Search results sorted by `is_pinned DESC, updated_at DESC`

### Backend Changes Required

**`AiSessionRepository.list_sessions()`** — pass sort params through to `BackendClient.list_sessions()`.

**`list_sessions()` in `backend_client.py`** — forward sort params to backend API.

**Backend `GET /internal/ai/sessions`** — update SQL query to:
- Include `is_pinned` in SELECT
- Sort by `is_pinned DESC, updated_at DESC`

**`_session_to_dict()`** — add `"is_pinned": s.is_pinned`.

**`search_threads` in `threads.py`** — map `r.get("is_pinned", False)` into response metadata.

---

## 8. Error Handling & Stability

### SDK Auto-Reconnect

LangGraph SDK's built-in retry handles transient failures. `useThreadChat` wraps the stream with exponential backoff:

```
stream error → wait 1s → retry → wait 2s → retry → wait 4s → fail
```

### Error States

| Scenario | User Sees | Recovery |
|----------|-----------|----------|
| Stream connection lost | Reconnecting banner | Auto-retry with backoff |
| Send failed | Error toast + unsent message | Manual retry |
| Session list load failed | Error toast + retry button | Pull-to-refresh |
| Delete/rename failed | Error toast, optimistic revert | Manual retry |

### Refresh Recovery

When a page refresh occurs:

1. Read `thread_id` from URL query param (`/ai/chat?thread_id=xxx`)
2. Call `client.threads.get(threadId)` to verify thread exists (404 → redirect to welcome)
3. Call `client.threads.getState(threadId)` to load messages
4. Mount chat mode with loaded messages

**If stop/cancel was in-flight during refresh:**
- The LangGraph checkpointer stores the interrupted state
- `useStream` with `reconnectOnMount: true` picks up the last checkpoint
- No dirty content is appended

### Token Usage Display

4 modes (toggle in UI), **default: Summary**:

| Mode | Display |
|------|---------|
| Off | Hidden |
| Summary | Total tokens below last AI response |
| Per Turn | Tokens below each AI response |
| Debug | Full breakdown per turn |

Reuses existing `TokenUsage.vue` component.

Data source: `GET /api/threads/{thread_id}/token-usage` (already implemented in `threads.py`)

---

## 9. 4-Mode System

| Mode | Value | Backend Behavior |
|------|-------|-----------------|
| Flash | `flash` | No thinking/reasoning |
| Thinking | `thinking` | Shows reasoning chain |
| Pro | `pro` | Enables plan_mode |
| Ultra | `ultra` | plan_mode + subagent_enabled |

### Model Capability Validation

The mode system must respect model capabilities:

| Capability | Effect |
|------------|--------|
| `supports_thinking` | If false → force `flash` mode, disable thinking/pro/ultra |
| `supports_reasoning_effort` | If true → show reasoning effort selector (minimal/low/medium/high) |

**Flow:**
1. User selects model → check `supports_thinking`
2. If model doesn't support thinking → force `flash` mode
3. If model supports reasoning effort → show effort selector below mode selector
4. Reasoning effort maps to mode: `ultra`=high, `pro`=medium, `thinking`=low, `flash`=minimal

Model selector is NOT shown in the chat input box. Models are configured by the family admin in the AI settings page. The input box only shows the mode selector.

---

## 10. Title Generation

### DeerFlow's Approach (Reuse)

DeerFlow generates titles via the LangGraph summarization middleware. The agent graph's `title` channel is populated by a summarization node during/after the first response. The frontend receives title updates through:

1. **`onUpdateEvent`**: Backend sends `{"SummarizationMiddleware.before_model": {"title": "..."}}`
2. **`onFinish`**: Final state includes `state.values.title`

The frontend updates the title reactively — no polling, no separate API call.

### Numina Implementation

The current `_generate_and_save_title` in `runs.py` fires a background task to generate a title after the stream ends. This is **incompatible** with the DeerFlow pattern because:

1. Title arrives after the stream completes, not during it
2. Uses a separate LLM call instead of the agent's summarization node
3. Writes to `AiSessionRepository` instead of updating the checkpointer's `title` channel

**Fix:** Remove the background title generation task. Instead, ensure the Numina agent graph writes a `title` value to the checkpointer's channel values during execution. The `onUpdateEvent` handler in `useStream` will pick it up automatically.

If the agent graph does not currently generate titles, add a lightweight summarization node to the graph (not a separate LLM call — use the existing response's first user message to derive a title).

**Fallback:** On the frontend, derive the title from the first user message content (truncated to 20 chars). This is applied only if the backend hasn't provided a title yet:

```typescript
const sessionTitle = computed(() => {
  // Prefer backend-generated title
  if (backendTitle.value) return backendTitle.value
  // Fallback: first user message
  const firstUser = messages.value.find(m => m.type === 'human')
  if (!firstUser) return t('aiChat.newChat')
  const text = textOfMessage(firstUser) ?? ''
  return text.length > 20 ? text.slice(0, 20) + '…' : text
})
```

---

## 11. Tenant Security & Resource Isolation

### Principle

All model, MCP, skill, websearch, subagent, upload, artifact, thread, run, and suggestion operations are validated against the requesting family/tenant/user on the backend. The frontend only displays what the backend allows.

### Backend Enforcement

| Resource | Validation | Error |
|----------|-----------|-------|
| Thread | `X-Family-Id` header matches thread owner | 404 |
| Run | Thread ownership validated at run creation | 403 |
| Model | Only models returned by family's AI config | 400 |
| MCP | Only tools enabled in family's MCP config | 400 |
| Skill | Only skills allowed by family's skill config | 400 |
| Upload | Scoped to thread's family | 403 |
| Artifact | Scoped to thread's family | 404 |

### Frontend Display

The `useTenantAiResources` composable already filters available resources by tenant. No additional frontend changes needed — but verify that:

- Model list in settings page only shows models returned by family's AI config
- Mode selector respects `supports_thinking` from the selected model
- File upload endpoint validates `X-Family-Id`
- Thread list only shows threads belonging to the current family

---

## 12. Welcome Mode & URL Management

### WelcomePage.vue

When `chatSession.activeThreadId === null`, the page shows:

- **Hero section**: Centered logo/icon + title
- **Suggestion quick actions**: Reuses `WelcomeExamples` component. Clicking one:
  1. Creates a new thread via `client.threads.create()`
  2. Sends the suggestion's prompt as the first message
  3. Transitions to Chat mode (streaming response)

### URL Management

Uses `history.replaceState()` to manage thread ID in URL — NOT Vue Router navigation:

| Action | URL |
|--------|-----|
| No active thread | `/ai/chat` |
| Active thread | `/ai/chat?thread_id=<id>` |
| Switch thread | `replaceState({thread_id: newId})` |
| Close/delete thread | `replaceState({})` → Welcome mode |

This prevents Vue Router from remounting the page on thread switch, preserving composable state.

### Refresh Recovery Flow

```
Page load → read URL query param `thread_id`
  ├── No thread_id → Welcome mode
  └── Has thread_id → 
       ├── client.threads.get(threadId) → 404 → Welcome mode (redirect)
       └── 200 → Chat mode with loaded history
```

---

## 13. File Structure — Delta

### New Files to Create

```
frontend/apps/main/src/
├── api/
│   └── langgraph.ts                 ← LangGraph SDK client singleton + helpers (NEW)
├── composables/
│   ├── useThreadChat.ts             ← Rewrite: based on useStream() (REWRITE)
│   └── useThreadList.ts             ← Session list composable (NEW)
├── stores/
│   └── chatSession.ts               ← Pinia store: active thread, sessions cache (NEW)
├── pages/ai/chat/
│   └── index.vue                    ← New route entry, mounts AIChatBox (NEW)
└── components/ai/
    ├── AIChatBox.vue                ← Root container (NEW)
    ├── SessionSidebar.vue           ← Session list overlay (NEW)
    ├── WelcomePage.vue              ← Hero + suggestions (NEW)
    └── MessageList.vue              ← Scrollable messages (NEW)
```

### Files to Modify

| File | Change |
|------|--------|
| `router/index.ts` | Change `AIChat` route from `AIChatPage.vue` → `pages/ai/chat/index.vue` |
| `composables/ai-chat/useThreadChat.ts` | Rewrite with useStream() pattern |

### Files to Remove

| File | Reason |
|------|--------|
| `pages/AIChatPage.vue` | Replaced by new component hierarchy |
| `api/sessions.ts::streamSessionEvents()` | NDJSON protocol removed |

### Backend Files to Remove

| File | Reason |
|------|--------|
| (none — `agent_dispatch.py` stays for non-chat capabilities) | Only NDJSON chat path is removed; `streamSessionEvents()` frontend code is deleted, replaced by `client.threads.getState()` |

### Backend Files to Modify

| File | Change |
|------|--------|
| `routers/runs.py` | Add missing RunCreateRequest fields + run CRUD endpoints |
| `routers/threads.py` | Add sortBy/sortOrder to ThreadSearchRequest; add is_pinned to search response |

### Data Types (reuse existing types from `types/ai-chat/message-group.ts`)

Additional types needed in `types/ai-chat/`:

```typescript
// Session-specific types (add to types/ai-chat/ or new types/ai-chat/session.ts)
interface ThreadSession {
  thread_id: string;
  title: string;
  status: "idle" | "interrupted" | "error";
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}
```

### i18n Keys (`zh-CN.ts`)

```typescript
// Add under 'ai.chat' namespace
ai: {
  chat: {
    // ... existing keys preserved ...
    session: {
      today: "今天",
      yesterday: "昨天",
      earlier: "更早",
      noSessions: "暂无会话",
      deleteConfirm: "确认删除此会话？",
      rename: "重命名",
      delete: "删除",
      pin: "置顶",
      unpin: "取消置顶",
    },
    tokenDisplay: {
      off: "关闭",
      summary: "总计",
      perTurn: "每次",
      debug: "调试",
    },
    errors: {
      sendFailed: "发送失败，请重试",
      streamFailed: "连接中断，正在重连...",
      sessionLoadFailed: "加载会话失败",
    },
  },
}
```

---

## 14. Implementation Order

Each phase produces independently testable work:

### Phase 1: Backend Protocol Alignment ⚠️ CRITICAL

1. Enhance `routers/runs.py` — add all missing `RunCreateRequest` fields (context, stream_subgraphs, multitask_strategy, etc.)
2. Add missing endpoints to `routers/runs.py`: list runs, get run, list run messages, cancel run, join run, stream existing run
3. Add sortBy/sortOrder to `ThreadSearchRequest` in `threads.py`
4. Remove background title generation task (`_generate_and_save_title` in `runs.py`); ensure agent graph writes `title` channel instead
5. Remove `streamSessionEvents()` from `frontend/api/sessions.ts` — replace with `client.threads.getState()` for history loading
6. Remove NDJSON history loading from `AIChatPage.vue` (lines 1047-1163)
7. Verify with `uv run pytest apps/agent/tests/ -v`

**Note:** Non-chat capabilities (alerts, allocation, disposal, etc.) continue using `agent_dispatch.py` → `EventStreamBuilder` for their NDJSON streams. Only the chat NDJSON path is being removed.

### Phase 2: Foundation

7. Route change + `pages/ai/chat/index.vue` entry + `AIChatBox.vue` with welcome/chat mode switching
8. Create `api/langgraph.ts` — LangGraph SDK client singleton

### Phase 3: Session State

9. `chatSession` Pinia store + URL management via `history.replaceState()`
10. Implement `useThreadList` composable with LangGraph SDK `client.threads.search()`

### Phase 4: Streaming Rewrite

11. Rewrite `useThreadChat` composable — based on `useStream()` from `@langchain/langgraph-sdk/react`
12. Remove NDJSON `streamSessionEvents()` callers
13. `MessageList.vue` using `useThreadChat` output

### Phase 5: Welcome Mode

14. `WelcomePage.vue` wrapping `WelcomeExamples` + thread creation on suggestion click

### Phase 6: Session List

15. `SessionSidebar.vue` with pinning/rename/delete + date grouping

### Phase 7: Polish

16. Error handling, reconnection, optimistic UI, token usage integration
17. Refresh recovery flow
18. Title generation (verify agent graph integration)

### Phase 8: Cleanup

19. Remove old `AIChatPage.vue`, old NDJSON files
20. Verify end-to-end with `pnpm typecheck && pnpm -r test:run`

---

## 15. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| NDJSON removal breaks existing users | High — existing sessions won't load | Medium | Migrate session data from JSONL to checkpointer before removing NDJSON code |
| useStream() API changes in langgraph-sdk | Medium — stream handling breaks | Low | Pin `@langchain/langgraph-sdk` version, test after upgrade |
| DeerFlow adapter raw_stream_dispatch doesn't support all stream modes | High — missing events | Medium | Verify stream mode support against DeerFlow harness API before implementation |
| Thread search sort params not supported by BackendClient | Medium — wrong sort order | Medium | Add sort params to backend HTTP calls, fall back to client-side sort |
| Agent graph doesn't write title channel | Low — titles use fallback | High | Accept first-message fallback; add graph node in future iteration |
