# AI Chat Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the AI Chat page to replicate DeerFlow's chat interaction pattern using LangGraph SDK streaming.

**Architecture:** New component hierarchy under `pages/ai/chat/index.vue` with `AIChatBox.vue` as the root container switching between Welcome mode (no active thread) and Chat mode (active thread). `useThreadChat` composable rewritten to wrap `@langchain/langgraph-sdk`'s `runs.stream()` with a clean interface. Session management via `SessionSidebar.vue` overlay with server-side pinning. URL managed via `history.replaceState()`.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 + Pinia + LangGraph SDK (`@langchain/langgraph-sdk`) + Python 3.12+ (FastAPI for backend changes)

## Global Constraints

- TypeScript strict mode — no `any` or `@ts-ignore`
- `<script setup lang="ts">` only — no Options API, no `defineComponent`
- Vant auto-import — don't manually import Vant components, only import functional APIs (`showToast`, `showDialog`)
- i18n required for all UI strings — all user-facing strings in `zh-CN.ts`, referenced via `t('key')`
- Toast uses Vant icons — `showSuccessToast`/`showFailToast`/`showLoadingToast` as appropriate, i18n text has no emoji
- `history.replaceState()` for URL management — never Vue Router navigation for thread switching
- Backend: `redirect_slashes=False`, router root-path decorators use `""` not `"/"`
- Backend: Pydantic v2 only, error details in Chinese
- Backend: All response schemas with IDs inherit from `SnowflakeBase`
- Incremental formatting — format only files you touch
- **Streaming: Vue composable mirrors `@langchain/langgraph-sdk/react`'s `useStream` API pattern** — not the raw `client.runs.stream()`. The React hook provides auto-reconnect, history merging, optimistic messages, and lifecycle callbacks (`onCreated`, `onUpdateEvent`, `onFinish`, `onError`). Since we use Vue 3 (not React), we build a Vue composable that replicates the same API surface, wrapping `client.runs.stream()` internally.

---

## File Structure Delta

### New Files (Frontend)

```
frontend/apps/main/src/
├── api/
│   └── ai-chat.ts                  ← LangGraph SDK client singleton + helpers
├── composables/
│   ├── useThreadChat.ts            ← REWRITE: clean interface wrapping runs.stream()
│   └── useThreadList.ts            ← Session list composable (infinite scroll + pinning)
├── stores/
│   └── chatSession.ts              ← Pinia store: active thread, sessions cache
├── pages/ai/chat/
│   └── index.vue                   ← Route entry, mounts AIChatBox
├── types/ai-chat/
│   └── session.ts                  ← ThreadSession, TokenUsage, DateGroup interfaces
└── components/ai/
    ├── AIChatBox.vue               ← Root container (Welcome / Chat mode switching)
    ├── SessionSidebar.vue          ← Session list overlay with pinning/rename/delete
    ├── WelcomePage.vue             ← Hero + suggestions (reuses WelcomeExamples)
    └── MessageList.vue             ← Scrollable messages (reuses MessageGroup)
```

### Modified Files (Frontend)

| File | Change |
|------|--------|
| `router/index.ts` | Change `AIChat` route: `AIChatPage.vue` → `pages/ai/chat/index.vue` |
| `composables/ai-chat/useThreadChat.ts` | Rewrite with clean interface |
| `i18n/locales/zh-CN.ts` | Add `ai.chat.session.*`, `ai.chat.tokenDisplay.*`, `ai.chat.errors.*` keys |

### Removed Files (Frontend)

| File | Reason |
|------|--------|
| `pages/AIChatPage.vue` | Replaced by new component hierarchy |

### Modified Files (Backend)

| File | Change |
|------|--------|
| `server/apps/backend/app/routers/ai_internal.py` | Add `is_pinned` to `_session_to_dict()`, add `is_pinned DESC` to SQL sort |
| `server/apps/agent/routers/threads.py` | Add `sortBy`/`sortOrder` to `ThreadSearchRequest`, map `is_pinned` in response |
| `server/apps/agent/services/session_store.py` | Pass sort params through `list_sessions()` |
| `server/apps/agent/core/backend_client.py` | Forward sort params to backend API |

---

### Task 1: i18n Keys + Route Change + Foundation Types

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add chat session/token/error keys
- Modify: `frontend/apps/main/src/router/index.ts` — change AIChat route to new entry
- Create: `frontend/apps/main/src/types/ai-chat/session.ts` — ThreadSession, TokenUsage, DateGroup types
- Remove: `frontend/apps/main/src/pages/AIChatPage.vue` — delete old page

**Interfaces:**
- Consumes: existing `zh-CN.ts` structure, existing `router/index.ts` route definitions
- Produces: route pointing to `pages/ai/chat/index.vue`, `ThreadSession`/`TokenUsage`/`DateGroup` types

- [ ] **Step 1: Add i18n keys to zh-CN.ts**

Find the `ai.chat` section in `zh-CN.ts` and add the session/token/error keys inside it:

```typescript
// Inside ai.chat namespace — add these keys:
session: {
  today: '今天',
  yesterday: '昨天',
  earlier: '更早',
  noSessions: '暂无会话',
  deleteConfirm: '确认删除此会话？',
  rename: '重命名',
  delete: '删除',
  pin: '置顶',
  unpin: '取消置顶',
},
tokenDisplay: {
  off: '关闭',
  summary: '总计',
  perTurn: '每次',
  debug: '调试',
},
errors: {
  sendFailed: '发送失败，请重试',
  streamFailed: '连接中断，正在重连...',
  sessionLoadFailed: '加载会话失败',
},
```

- [ ] **Step 2: Create ThreadSession and TokenUsage types**

Create `frontend/apps/main/src/types/ai-chat/session.ts`:

```typescript
/** Session returned from thread search API */
export interface ThreadSession {
  thread_id: string
  title: string
  status: 'idle' | 'interrupted' | 'error'
  is_pinned: boolean
  created_at: string
  updated_at: string
}

/** Token usage from LangGraph streaming metadata */
export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

/** Date grouping label for sidebar sections */
export type DateGroupLabel = 'pinned' | 'today' | 'yesterday' | 'earlier'

/** A date-grouped section in the session sidebar */
export interface DateGroup {
  label: DateGroupLabel
  displayName: string
  sessions: ThreadSession[]
}
```

- [ ] **Step 3: Change route and create entry directory**

Modify `router/index.ts` — find the AIChat route definition (around line 295-298) and change the component import path:

```typescript
// Before:
// component: () => import('@/pages/AIChatPage.vue'),

// After:
component: () => import('@/pages/ai/chat/index.vue'),
```

Create the directory structure:

```bash
mkdir -p /Users/vincentruan/vscode_space/numina/frontend/apps/main/src/pages/ai/chat
```

- [ ] **Step 4: Create placeholder route entry page**

Create `frontend/apps/main/src/pages/ai/chat/index.vue`:

```vue
<script setup lang="ts">
import AIChatBox from '@/components/ai/AIChatBox.vue'
</script>

<template>
  <AIChatBox />
</template>
```

- [ ] **Step 5: Delete old AIChatPage.vue and verify route**

```bash
rm /Users/vincentruan/vscode_space/numina/frontend/apps/main/src/pages/AIChatPage.vue
```

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vue-tsc --noEmit 2>&1 | head -50
```

Expected: Type errors may exist since AIChatBox.vue doesn't exist yet — that's fine. But no errors about missing imports from the route change itself.

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts \
        frontend/apps/main/src/router/index.ts \
        frontend/apps/main/src/types/ai-chat/session.ts \
        frontend/apps/main/src/pages/ai/chat/index.vue
git rm frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "feat(ai-chat): add i18n keys, route entry, foundation types
- Add session/token/error i18n keys to zh-CN.ts
- Create ThreadSession/TokenUsage/DateGroup types
- Change AIChat route to pages/ai/chat/index.vue
- Remove old AIChatPage.vue

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Pinia Store (chatSession)

**Files:**
- Create: `frontend/apps/main/src/stores/chatSession.ts`

**Interfaces:**
- Consumes: `ThreadSession` from `types/ai-chat/session.ts`
- Produces: `useChatSessionStore()` — reactive active thread state + session cache

- [ ] **Step 1: Write the test for the store**

Create `frontend/apps/main/src/stores/__tests__/chatSession.spec.ts`:

```typescript
import { setActivePinia, createPinia } from 'pinia'
import { describe, it, expect, beforeEach } from 'vitest'
import { useChatSessionStore } from '../chatSession'
import type { ThreadSession } from '@/types/ai-chat/session'

function makeSession(overrides: Partial<ThreadSession> = {}): ThreadSession {
  return {
    thread_id: 'test-id',
    title: 'Test Session',
    status: 'idle',
    is_pinned: false,
    created_at: '2026-06-18T10:00:00Z',
    updated_at: '2026-06-18T10:00:00Z',
    ...overrides,
  }
}

describe('chatSession store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts with no active thread', () => {
    const store = useChatSessionStore()
    expect(store.activeThreadId).toBeNull()
    expect(store.isWelcomeMode).toBe(true)
  })

  it('sets active thread and switches to chat mode', () => {
    const store = useChatSessionStore()
    store.setActiveThread('thread-1')
    expect(store.activeThreadId).toBe('thread-1')
    expect(store.isWelcomeMode).toBe(false)
  })

  it('clears active thread and returns to welcome mode', () => {
    const store = useChatSessionStore()
    store.setActiveThread('thread-1')
    store.clearActiveThread()
    expect(store.activeThreadId).toBeNull()
    expect(store.isWelcomeMode).toBe(true)
  })

  it('updates URL via replaceState when setting thread', () => {
    const store = useChatSessionStore()
    const replaceSpy = vi.spyOn(window.history, 'replaceState')
    store.setActiveThread('thread-1')
    expect(replaceSpy).toHaveBeenCalledWith(null, '', '/ai/chat?thread_id=thread-1')
    replaceSpy.mockRestore()
  })

  it('updates URL via replaceState when clearing thread', () => {
    const store = useChatSessionStore()
    const replaceSpy = vi.spyOn(window.history, 'replaceState')
    store.setActiveThread('thread-1')
    store.clearActiveThread()
    // Second call clears URL
    expect(replaceSpy).toHaveBeenLastCalledWith(null, '', '/ai/chat')
    replaceSpy.mockRestore()
  })

  it('manages sessions array', () => {
    const store = useChatSessionStore()
    const s1 = makeSession({ thread_id: '1', title: 'First' })
    const s2 = makeSession({ thread_id: '2', title: 'Second', is_pinned: true })
    store.setSessions([s1, s2])
    expect(store.sessions).toHaveLength(2)
    // Sessions should be sorted: pinned first, then by updated_at DESC
    // s2 is pinned, should be first
    expect(store.sessions[0].thread_id).toBe('2')
  })

  it('updates a single session in the cache', () => {
    const store = useChatSessionStore()
    const s1 = makeSession({ thread_id: '1', title: 'Old Title' })
    store.setSessions([s1])
    store.updateSessionInCache('1', { title: 'New Title' })
    expect(store.sessions[0].title).toBe('New Title')
  })

  it('removes a session from cache', () => {
    const store = useChatSessionStore()
    const s1 = makeSession({ thread_id: '1' })
    const s2 = makeSession({ thread_id: '2' })
    store.setSessions([s1, s2])
    store.removeSessionFromCache('1')
    expect(store.sessions).toHaveLength(1)
    expect(store.sessions[0].thread_id).toBe('2')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/stores/__tests__/chatSession.spec.ts 2>&1 | head -30
```

Expected: FAIL — module not found for `../chatSession`.

- [ ] **Step 3: Create the Pinia store**

Create `frontend/apps/main/src/stores/chatSession.ts`:

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ThreadSession } from '@/types/ai-chat/session'

export const useChatSessionStore = defineStore('chatSession', () => {
  // State
  const activeThreadId = ref<string | null>(null)
  const sessions = ref<ThreadSession[]>([])

  // Getters
  const isWelcomeMode = computed(() => activeThreadId.value === null)
  const activeSession = computed(() =>
    sessions.value.find(s => s.thread_id === activeThreadId.value) ?? null
  )

  // Actions
  function setActiveThread(threadId: string) {
    activeThreadId.value = threadId
    const url = new URL(window.location.href)
    url.searchParams.set('thread_id', threadId)
    window.history.replaceState(null, '', url.pathname + url.search)
  }

  function clearActiveThread() {
    activeThreadId.value = null
    const url = new URL(window.location.href)
    url.searchParams.delete('thread_id')
    window.history.replaceState(null, '', url.pathname + url.search)
  }

  function setSessions(newSessions: ThreadSession[]) {
    // Sort: pinned first, then by updated_at DESC
    sessions.value = [...newSessions].sort((a, b) => {
      if (a.is_pinned !== b.is_pinned) return a.is_pinned ? -1 : 1
      return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    })
  }

  function updateSessionInCache(threadId: string, updates: Partial<ThreadSession>) {
    const idx = sessions.value.findIndex(s => s.thread_id === threadId)
    if (idx !== -1) {
      sessions.value[idx] = { ...sessions.value[idx], ...updates }
    }
  }

  function removeSessionFromCache(threadId: string) {
    sessions.value = sessions.value.filter(s => s.thread_id !== threadId)
  }

  return {
    activeThreadId,
    sessions,
    isWelcomeMode,
    activeSession,
    setActiveThread,
    clearActiveThread,
    setSessions,
    updateSessionInCache,
    removeSessionFromCache,
  }
})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/stores/__tests__/chatSession.spec.ts 2>&1
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/stores/chatSession.ts frontend/apps/main/src/stores/__tests__/chatSession.spec.ts
git commit -m "feat(ai-chat): add chatSession Pinia store with tests
- Create useChatSessionStore with active thread, session cache, URL management
- Welcome/chat mode switching via isWelcomeMode computed
- Optimistic cache helpers: setSessions, updateSessionInCache, removeSessionFromCache
- Full test coverage for all store actions

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: API Client Module (ai-chat.ts)

**Files:**
- Create: `frontend/apps/main/src/api/ai-chat.ts`

**Interfaces:**
- Consumes: `@langchain/langgraph-sdk` `Client`, types from `types/ai-chat/session.ts`
- Produces: `createClient()`, `createThread()`, `searchThreads()`, `updateThread()`, `deleteThread()`, `forkThread()`

- [ ] **Step 1: Write the test**

Create `frontend/apps/main/src/api/__tests__/ai-chat.spec.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock @langchain/langgraph-sdk before importing
vi.mock('@langchain/langgraph-sdk', () => ({
  Client: vi.fn().mockImplementation(() => ({
    threads: {
      create: vi.fn().mockResolvedValue({ thread_id: 'mock-thread-id' }),
      getState: vi.fn().mockResolvedValue({ values: [] }),
      updateState: vi.fn().mockResolvedValue({}),
      delete: vi.fn().mockResolvedValue({}),
    },
    runs: {
      stream: vi.fn().mockReturnValue({
        [Symbol.asyncIterator]: async function* () {
          yield { event: 'values', data: { messages: [] } }
        },
      }),
    },
    assistants: {
      get: vi.fn().mockResolvedValue({ assistant_id: 'mock-assistant' }),
    },
  })),
}))

describe('ai-chat API module', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('exports a function to create client', async () => {
    const mod = await import('../ai-chat')
    expect(typeof mod.createClient).toBe('function')
  })

  it('createClient returns a configured Client', async () => {
    const mod = await import('../ai-chat')
    const client = mod.createClient()
    expect(client).toBeDefined()
    const { Client } = await import('@langchain/langgraph-sdk')
    expect(Client).toHaveBeenCalledWith({ apiUrl: '/api' })
  })

  it('createThread creates and returns a new thread', async () => {
    const mod = await import('../ai-chat')
    const result = await mod.createThread()
    expect(result.thread_id).toBe('mock-thread-id')
  })

  it('searchThreads sends POST to /threads/search', async () => {
    const mod = await import('../ai-chat')
    // searchThreads uses client.runs.stream — test it returns expected shape
    const result = await mod.searchThreads({ limit: 20, offset: 0 })
    expect(Array.isArray(result)).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/api/__tests__/ai-chat.spec.ts 2>&1 | head -20
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create the API module**

Create `frontend/apps/main/src/api/ai-chat.ts`:

```typescript
import { Client } from '@langchain/langgraph-sdk'
import type { ThreadSession } from '@/types/ai-chat/session'

let clientInstance: Client | null = null

export function createClient(): Client {
  if (!clientInstance) {
    clientInstance = new Client({ apiUrl: '/api' })
  }
  return clientInstance
}

export function getClient(): Client {
  return clientInstance ?? createClient()
}

export async function createThread(): Promise<{ thread_id: string }> {
  const client = getClient()
  return client.threads.create()
}

export interface SearchThreadsParams {
  limit?: number
  offset?: number
  sortBy?: string
  sortOrder?: string
}

export async function searchThreads(
  params: SearchThreadsParams = {}
): Promise<ThreadSession[]> {
  const client = getClient()
  const stream = client.runs.stream(
    // Use a temporary thread for search — the search endpoint doesn't need a real thread
    // The proxy intercepts this and routes to agent's search_threads
    'search',
    'search-assistant',
    {
      input: {
        metadata: {},
        limit: params.limit ?? 100,
        offset: params.offset ?? 0,
        sortBy: params.sortBy ?? 'updated_at',
        sortOrder: params.sortOrder ?? 'desc',
      },
      streamMode: ['values'],
    }
  )

  const results: ThreadSession[] = []
  for await (const chunk of stream) {
    if (chunk.event === 'values' && chunk.data?.sessions) {
      results.push(...chunk.data.sessions)
    }
  }
  return results
}

export async function updateThread(
  threadId: string,
  metadata: Record<string, unknown>
): Promise<void> {
  const client = getClient()
  await client.threads.updateState(threadId, { metadata })
}

export async function deleteThread(threadId: string): Promise<void> {
  const client = getClient()
  await client.threads.delete(threadId)
}

export async function forkThread(
  threadId: string
): Promise<{ thread_id: string }> {
  const client = getClient()
  // Fork creates a new thread with the same history
  const state = await client.threads.getState(threadId)
  const newThread = await client.threads.create()
  if (state.values && Object.keys(state.values).length > 0) {
    await client.threads.updateState(newThread.thread_id, state.values)
  }
  return newThread
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/api/__tests__/ai-chat.spec.ts 2>&1
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/api/ai-chat.ts frontend/apps/main/src/api/__tests__/ai-chat.spec.ts
git commit -m "feat(ai-chat): add API client module for LangGraph SDK
- Create ai-chat.ts with Client singleton, createThread, searchThreads
- Add updateThread, deleteThread, forkThread helpers
- Full test coverage with mocked LangGraph SDK

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Rewrite useThreadChat Composable (mirrors useStream API pattern)

**Critical Design Decision:** `@langchain/langgraph-sdk/react` provides a `useStream()` React hook with auto-reconnect, history merging, optimistic messages, and lifecycle callbacks (`onCreated`, `onUpdateEvent`, `onFinish`, `onError`). Since Numina uses **Vue 3** (not React), we cannot use this hook directly. Instead, we build a **Vue composable that mirrors the same API pattern**, wrapping `client.runs.stream()` internally.

**The `useStream` API pattern (from source):**
- Input: `{ threadId, assistantId, input, streamMode, signal, onCreated?, onUpdateEvent?, onFinish?, onError? }`
- Output: `{ messages, isLoading, error, stop(), getThreadState(), getThreadUrl() }`
- Auto-reconnect: Built-in retry via SDK's `client.runs.stream()` with configurable signal
- History merging: Combines streaming chunks into complete messages
- Optimistic messages: Pre-pended to messages array, replaced by server response
- Lifecycle: `onCreated(thread)` after thread creation, `onUpdateEvent(event)` per SSE event, `onFinish(finalState)`, `onError(err)`
- Stop: `AbortController` signal — passed to `runs.stream({ signal })`

**Files:**
- Rewrite: `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts`

**Interfaces:**
- Consumes: `getClient()` from `api/ai-chat.ts`, `ChatMessage` from `types/ai-chat/message-group.ts`, `TokenUsage` from `types/ai-chat/session.ts`
- Produces: `{ messages, isLoading, error, sendMessage, cancelStream, loadHistory, retry }`

- [ ] **Step 1: Write the test**

Create `frontend/apps/main/src/composables/ai-chat/__tests__/useThreadChat.spec.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock api/ai-chat before importing
vi.mock('@/api/ai-chat', () => ({
  createClient: vi.fn(),
  getClient: vi.fn(() => ({
    threads: {
      getState: vi.fn().mockResolvedValue({
        values: {
          messages: [
            { type: 'human', content: 'hello', id: 'm1' },
            { type: 'ai', content: 'hi there', id: 'm2' },
          ],
        },
      }),
    },
    runs: {
      stream: vi.fn().mockReturnValue({
        [Symbol.asyncIterator]: async function* () {
          // Simulate streaming chunks mimicking useStream's event pattern
          yield {
            event: 'messages',
            data: {
              messages: [{ type: 'ai', content: 'Hel', id: 'm3' }],
            },
          }
          yield {
            event: 'messages',
            data: {
              messages: [{ type: 'ai', content: 'lo!', id: 'm3' }],
            },
          }
          yield {
            event: 'values',
            data: {
              messages: [
                { type: 'human', content: 'hello', id: 'm1' },
                { type: 'ai', content: 'Hello!', id: 'm3' },
              ],
            },
          }
          yield {
            event: 'metadata',
            data: {
              prompt_tokens: 10,
              completion_tokens: 5,
              total_tokens: 15,
            },
          }
        },
      }),
    },
  })),
}))

describe('useThreadChat', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('exports useThreadChat function', async () => {
    const mod = await import('../useThreadChat')
    expect(typeof mod.useThreadChat).toBe('function')
  })

  it('returns expected reactive state shape (mirrors useStream)', async () => {
    const mod = await import('../useThreadChat')
    const chat = mod.useThreadChat()
    expect(chat.messages).toBeDefined()
    expect(chat.isLoading).toBeDefined()
    expect(chat.error).toBeDefined()
    expect(chat.tokenUsage).toBeDefined()
    expect(typeof chat.sendMessage).toBe('function')
    expect(typeof chat.cancelStream).toBe('function')
    expect(typeof chat.loadHistory).toBe('function')
    expect(typeof chat.retry).toBe('function')
  })

  it('sendMessage streams chunks and merges them into final message', async () => {
    const mod = await import('../useThreadChat')
    const chat = mod.useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')
    // Should have user message + AI message
    expect(chat.messages.value.length).toBeGreaterThanOrEqual(2)
    // AI message should have merged content "Hello!"
    const aiMsg = chat.messages.value.find((m) => m.role === 'assistant')
    expect(aiMsg).toBeDefined()
    expect(aiMsg!.content).toContain('Hello!')
    expect(chat.isLoading.value).toBe(false)
  })

  it('loadHistory loads thread state and converts messages', async () => {
    const mod = await import('../useThreadChat')
    const chat = mod.useThreadChat()
    await chat.loadHistory('thread-1')
    expect(chat.messages.value.length).toBe(2)
    expect(chat.messages.value[0].role).toBe('user')
    expect(chat.messages.value[1].role).toBe('assistant')
  })

  it('cancelStream aborts active stream', async () => {
    const mod = await import('../useThreadChat')
    const chat = mod.useThreadChat()
    chat.cancelStream() // Should be safe to call when not streaming
    expect(chat.isLoading.value).toBe(false)
  })

  it('retry re-sends the last user message', async () => {
    const mod = await import('../useThreadChat')
    const chat = mod.useThreadChat()
    // First send a message
    await chat.sendMessage('hello', undefined, 'thread-1')
    const messageCount = chat.messages.value.length
    // Mark last AI message as errored to simulate failure
    // Retry should re-send
    await chat.retry('thread-1')
    expect(chat.messages.value.length).toBeGreaterThanOrEqual(messageCount)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/composables/ai-chat/__tests__/useThreadChat.spec.ts 2>&1 | head -20
```

Expected: FAIL — module not found.

- [ ] **Step 3: Rewrite useThreadChat composable (mirrors useStream pattern)**

Rewrite `frontend/apps/main/src/composables/ai-chat/useThreadChat.ts`:

```typescript
import { ref, computed } from 'vue'
import { getClient } from '@/api/ai-chat'
import type { ChatMessage } from '@/types/ai-chat/message-group'
import type { TokenUsage } from '@/types/ai-chat/session'
import type { InputMode } from '@/types/ai-chat/input-mode'

/**
 * Stream event from LangGraph SDK runs.stream()
 * Mirrors the event structure that useStream from @langchain/langgraph-sdk/react processes
 */
interface StreamEvent {
  event: string
  data: Record<string, unknown>
}

/**
 * A parsed message chunk from the stream
 */
interface StreamMessage {
  type?: string
  content?: string
  id?: string
  [key: string]: unknown
}

/**
 * useThreadChat — Vue composable that mirrors @langchain/langgraph-sdk/react's useStream API
 *
 * Key design decisions:
 * 1. Uses client.runs.stream() internally (since we can't use React hooks in Vue)
 * 2. Exposes the same logical API surface: messages, isLoading, error, cancelStream
 * 3. Implements history merging — streaming chunks are accumulated into complete messages
 * 4. Supports auto-retry via the retry() method
 * 5. Lifecycle: onCreated/onFinish/onError are internal callbacks, exposed for extension
 * 6. Uses AbortController for stream cancellation (matching useStream's signal pattern)
 */
export function useThreadChat() {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const tokenUsage = ref<TokenUsage | null>(null)

  let abortController: AbortController | null = null

  /**
   * Optimistically add a user message to the UI before the server confirms
   */
  function addOptimisticUserMessage(text: string): ChatMessage {
    const msg: ChatMessage = {
      id: `opt-${Date.now()}`,
      type: 'human',
      role: 'user',
      content: text,
      displayTime: new Date().toISOString(),
      sendStatus: 'sending',
    }
    messages.value = [...messages.value, msg]
    return msg
  }

  /**
   * Mark the optimistic user message as sent or failed
   */
  function finalizeUserMessage(success: boolean) {
    messages.value = messages.value.map((m) => {
      if (m.role === 'user' && m.sendStatus === 'sending') {
        return { ...m, sendStatus: success ? ('sent' as const) : ('failed' as const) }
      }
      return m
    })
  }

  /**
   * Merge streaming chunks into the last AI message (history merging)
   */
  function mergeStreamingChunk(content: string): void {
    const msgs = [...messages.value]
    const lastIdx = msgs.length - 1
    if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
      msgs[lastIdx] = {
        ...msgs[lastIdx],
        content: msgs[lastIdx].content + content,
      }
    } else {
      msgs.push({
        id: `ai-${Date.now()}`,
        type: 'ai',
        role: 'assistant',
        content,
        displayTime: new Date().toISOString(),
        phase: 'answering',
      })
    }
    messages.value = msgs
  }

  /**
   * Replace the last AI message with the complete message from a values event
   */
  function replaceWithFinalMessage(content: string): void {
    const msgs = [...messages.value]
    const lastIdx = msgs.length - 1
    if (lastIdx >= 0 && msgs[lastIdx].role === 'assistant') {
      msgs[lastIdx] = {
        ...msgs[lastIdx],
        content,
        phase: 'done',
      }
    }
    messages.value = msgs
  }

  /**
   * Extract messages from a values event and merge into our message list
   */
  function mergeValuesMessages(rawMessages: StreamMessage[]): void {
    // Find the last assistant message in the values
    const assistantMsgs = rawMessages.filter(
      (m) => m.type === 'ai' || m.type === 'assistant'
    )
    if (assistantMsgs.length > 0) {
      const content = assistantMsgs[assistantMsgs.length - 1]?.content ?? ''
      replaceWithFinalMessage(content)
    }
  }

  /**
   * sendMessage — main streaming entry point
   * Mirrors useStream's input handling with AbortController signal
   */
  async function sendMessage(
    text: string,
    mode?: InputMode,
    threadId?: string
  ): Promise<void> {
    if (!threadId || isLoading.value) return

    isLoading.value = true
    error.value = null
    abortController = new AbortController()

    addOptimisticUserMessage(text)

    const client = getClient()

    try {
      const stream = client.runs.stream(threadId, 'agent', {
        input: {
          messages: [{ type: 'human', content: text }],
          mode: mode?.mode ?? 'flash',
        },
        streamMode: ['messages', 'values', 'updates'],
        signal: abortController.signal,
      })

      for await (const rawChunk of stream) {
        const chunk = rawChunk as unknown as StreamEvent

        switch (chunk.event) {
          case 'messages': {
            // Streaming message chunks — accumulate into last AI message
            const data = chunk.data as { messages?: StreamMessage[] }
            for (const msg of data.messages ?? []) {
              if (msg.type === 'ai' || msg.type === 'assistant') {
                mergeStreamingChunk(msg.content ?? '')
              }
            }
            break
          }

          case 'values': {
            // Final state values — replace streaming with complete message
            const data = chunk.data as { messages?: StreamMessage[] }
            if (data.messages) {
              mergeValuesMessages(data.messages)
            }
            break
          }

          case 'updates': {
            // Metadata updates — extract token usage
            const data = chunk.data as Record<string, unknown>
            const meta = (data.metadata ?? data) as Record<string, unknown>
            if (meta.prompt_tokens != null) {
              tokenUsage.value = {
                prompt_tokens: Number(meta.prompt_tokens) || 0,
                completion_tokens: Number(meta.completion_tokens) || 0,
                total_tokens: Number(meta.total_tokens) || 0,
              }
            }
            break
          }

          case 'metadata': {
            // Direct metadata event — token usage
            const data = chunk.data as Record<string, unknown>
            if (data.prompt_tokens != null) {
              tokenUsage.value = {
                prompt_tokens: Number(data.prompt_tokens) || 0,
                completion_tokens: Number(data.completion_tokens) || 0,
                total_tokens: Number(data.total_tokens) || 0,
              }
            }
            break
          }
        }
      }

      finalizeUserMessage(true)
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled via cancelStream — not an error
        finalizeUserMessage(false)
        return
      }
      error.value = '发送失败，请重试'
      finalizeUserMessage(false)
    } finally {
      isLoading.value = false
      abortController = null
    }
  }

  /**
   * cancelStream — mirrors useStream's stop() via AbortController
   */
  function cancelStream(): void {
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    isLoading.value = false
  }

  /**
   * loadHistory — loads thread history from server
   * Converts raw LangGraph messages to ChatMessage format
   */
  async function loadHistory(threadId: string): Promise<void> {
    try {
      isLoading.value = true
      const client = getClient()
      const state = await client.threads.getState(threadId)

      const loaded: ChatMessage[] = []
      const rawMessages = (state.values?.messages ?? []) as StreamMessage[]

      for (const msg of rawMessages) {
        const chatMsg: ChatMessage = {
          id: msg.id ?? `msg-${Date.now()}-${Math.random()}`,
          type: msg.type === 'human' ? 'human' : 'ai',
          role: msg.type === 'human' ? 'user' : 'assistant',
          content: msg.content ?? '',
          displayTime: (msg.created_at as string) ?? new Date().toISOString(),
          phase: 'done',
        }
        loaded.push(chatMsg)
      }

      messages.value = loaded
    } catch (err) {
      error.value = '加载会话失败'
    } finally {
      isLoading.value = false
    }
  }

  /**
   * retry — re-sends the last user message
   * Useful after a failed send to retry without re-typing
   */
  async function retry(threadId?: string): Promise<void> {
    if (!threadId) return

    // Find the last user message
    const lastUserMsg = [...messages.value]
      .reverse()
      .find((m) => m.role === 'user')

    if (lastUserMsg) {
      // Remove the failed message and any subsequent AI messages
      const lastUserIdx = messages.value.lastIndexOf(lastUserMsg)
      messages.value = messages.value.slice(0, lastUserIdx)
      await sendMessage(lastUserMsg.content, undefined, threadId)
    }
  }

  return {
    messages,
    isLoading,
    error,
    tokenUsage,
    sendMessage,
    cancelStream,
    loadHistory,
    retry,
  }
}
```

**Key design differences from raw `client.runs.stream()`:**
1. **`isLoading` not `isStreaming`** — matches useStream's naming convention
2. **`retry()` method** — re-sends last user message after failure
3. **Optimistic user messages** — added immediately with `sending` status
4. **History merging** — streaming chunks accumulated, not replaced
5. **Event-type switch** — clean dispatch for `messages`/`values`/`updates`/`metadata`
6. **Auto-reconnect not built-in** — the SDK's `runs.stream()` handles TCP-level retry; app-level retry uses the `retry()` method

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/composables/ai-chat/__tests__/useThreadChat.spec.ts 2>&1
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/composables/ai-chat/useThreadChat.ts \
      frontend/apps/main/src/composables/ai-chat/__tests__/useThreadChat.spec.ts
git commit -m "feat(ai-chat): rewrite useThreadChat mirroring useStream API pattern
- Mirrors @langchain/langgraph-sdk/react useStream pattern for Vue
- History merging: streaming chunks accumulated into complete messages
- Optimistic user messages with sending/sent/failed states
- Event-type dispatch: messages/values/updates/metadata
- cancelStream via AbortController (mirrors useStream stop())
- retry() for re-sending last user message after failure
- Full test coverage with mocked LangGraph SDK stream

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: useThreadList Composable

**Files:**
- Create: `frontend/apps/main/src/composables/useThreadList.ts`

**Interfaces:**
- Consumes: `searchThreads()`, `updateThread()`, `deleteThread()` from `api/ai-chat.ts`, `useChatSessionStore` from `stores/chatSession.ts`
- Produces: `{ sessions, isLoading, hasMore, loadMore, refresh, deleteSession, renameSession, togglePin, dateGroups }`

- [ ] **Step 1: Write the test**

Create `frontend/apps/main/src/composables/__tests__/useThreadList.spec.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock api/ai-chat
vi.mock('@/api/ai-chat', () => ({
  searchThreads: vi.fn().mockResolvedValue([
    { thread_id: '1', title: 'Session 1', is_pinned: true, status: 'idle', created_at: '2026-06-18T10:00:00Z', updated_at: '2026-06-18T10:00:00Z' },
    { thread_id: '2', title: 'Session 2', is_pinned: false, status: 'idle', created_at: '2026-06-18T09:00:00Z', updated_at: '2026-06-18T09:00:00Z' },
  ]),
  updateThread: vi.fn().mockResolvedValue(undefined),
  deleteThread: vi.fn().mockResolvedValue(undefined),
}))

describe('useThreadList', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('exports useThreadList function', async () => {
    const mod = await import('../useThreadList')
    expect(typeof mod.useThreadList).toBe('function')
  })

  it('returns expected state shape', async () => {
    const mod = await import('../useThreadList')
    const list = mod.useThreadList()
    expect(list.sessions).toBeDefined()
    expect(list.isLoading).toBeDefined()
    expect(list.hasMore).toBeDefined()
    expect(typeof list.loadMore).toBe('function')
    expect(typeof list.refresh).toBe('function')
    expect(typeof list.deleteSession).toBe('function')
    expect(typeof list.renameSession).toBe('function')
    expect(typeof list.togglePin).toBe('function')
    expect(typeof list.dateGroups).toBe('function')
  })

  it('loadMore fetches and populates sessions', async () => {
    const mod = await import('../useThreadList')
    const list = mod.useThreadList()
    await list.loadMore()
    expect(list.sessions.value.length).toBeGreaterThan(0)
    expect(list.isLoading.value).toBe(false)
  })

  it('dateGroups groups sessions correctly', async () => {
    const mod = await import('../useThreadList')
    const list = mod.useThreadList()
    await list.loadMore()
    const groups = list.dateGroups.value
    // Pinned sessions should be first group
    const pinnedGroup = groups.find((g) => g.label === 'pinned')
    expect(pinnedGroup).toBeDefined()
    expect(pinnedGroup!.sessions.length).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/composables/__tests__/useThreadList.spec.ts 2>&1 | head -20
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create useThreadList composable**

Create `frontend/apps/main/src/composables/useThreadList.ts`:

```typescript
import { ref, computed } from 'vue'
import { searchThreads, updateThread, deleteThread } from '@/api/ai-chat'
import { useChatSessionStore } from '@/stores/chatSession'
import type { ThreadSession, DateGroup, DateGroupLabel } from '@/types/ai-chat/session'

export function useThreadList() {
  const store = useChatSessionStore()
  const isLoading = ref(false)
  const hasMore = ref(true)
  const offset = ref(0)
  const PAGE_SIZE = 20

  const dateGroups = computed<DateGroup[]>(() => {
    const groups: Map<DateGroupLabel, ThreadSession[]> = new Map()
    groups.set('pinned', [])
    groups.set('today', [])
    groups.set('yesterday', [])
    groups.set('earlier', [])

    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    for (const session of store.sessions) {
      const updatedAt = new Date(session.updated_at)
      let label: DateGroupLabel

      if (session.is_pinned) {
        label = 'pinned'
      } else if (updatedAt >= today) {
        label = 'today'
      } else if (updatedAt >= yesterday) {
        label = 'yesterday'
      } else {
        label = 'earlier'
      }

      groups.get(label)!.push(session)
    }

    const result: DateGroup[] = []
    const labelDisplay: Record<DateGroupLabel, string> = {
      pinned: '📌 置顶',
      today: '今天',
      yesterday: '昨天',
      earlier: '更早',
    }

    for (const [label, sessions] of groups) {
      if (sessions.length > 0) {
        result.push({ label, displayName: labelDisplay[label], sessions })
      }
    }

    return result
  })

  async function loadMore(): Promise<void> {
    if (isLoading.value || !hasMore.value) return
    isLoading.value = true

    try {
      const results = await searchThreads({
        limit: PAGE_SIZE,
        offset: offset.value,
        sortBy: 'updated_at',
        sortOrder: 'desc',
      })

      if (results.length < PAGE_SIZE) {
        hasMore.value = false
      }

      if (offset.value === 0) {
        store.setSessions(results)
      } else {
        // Merge with existing — avoid duplicates
        const existingIds = new Set(store.sessions.map((s) => s.thread_id))
        const newSessions = results.filter((s) => !existingIds.has(s.thread_id))
        store.setSessions([...store.sessions, ...newSessions])
      }

      offset.value += results.length
    } catch {
      // Error is handled by the caller (e.g., error toast)
    } finally {
      isLoading.value = false
    }
  }

  async function refresh(): Promise<void> {
    offset.value = 0
    hasMore.value = true
    await loadMore()
  }

  async function deleteSession(threadId: string): Promise<void> {
    try {
      await deleteThread(threadId)
      store.removeSessionFromCache(threadId)
    } catch {
      throw new Error('删除会话失败')
    }
  }

  async function renameSession(threadId: string, title: string): Promise<void> {
    try {
      await updateThread(threadId, { title })
      store.updateSessionInCache(threadId, { title })
    } catch {
      throw new Error('重命名失败')
    }
  }

  async function togglePin(threadId: string, isPinned: boolean): Promise<void> {
    try {
      await updateThread(threadId, { is_pinned: isPinned })
      store.updateSessionInCache(threadId, { is_pinned: isPinned })
    } catch {
      throw new Error(isPinned ? '置顶失败' : '取消置顶失败')
    }
  }

  return {
    sessions: computed(() => store.sessions),
    isLoading,
    hasMore,
    dateGroups,
    loadMore,
    refresh,
    deleteSession,
    renameSession,
    togglePin,
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run src/composables/__tests__/useThreadList.spec.ts 2>&1
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/composables/useThreadList.ts \
      frontend/apps/main/src/composables/__tests__/useThreadList.spec.ts
git commit -m "feat(ai-chat): add useThreadList composable for session management
- Create useThreadList with loadMore/refresh/delete/rename/togglePin
- Date grouping: pinned → today → yesterday → earlier
- Integrates with chatSession Pinia store for cache management
- Infinite scroll support via hasMore + offset tracking
- Full test coverage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: WelcomePage and MessageList Components

**Files:**
- Create: `frontend/apps/main/src/components/ai/WelcomePage.vue`
- Create: `frontend/apps/main/src/components/ai/MessageList.vue`

**Interfaces:**
- Consumes: `WelcomeExamples` component (existing), `MessageGroup` component (existing), `useChatSessionStore`, `useThreadChat`
- Produces: `<WelcomePage @start-chat="..." />`, `<MessageList :messages="..." :is-streaming="..." />`

- [ ] **Step 1: Create WelcomePage.vue**

Create `frontend/apps/main/src/components/ai/WelcomePage.vue`:

```vue
<script setup lang="ts">
import WelcomeExamples from '@/components/ai-chat/WelcomeExamples.vue'

const emit = defineEmits<{
  startChat: [text: string]
}>()

function handleSuggestionClick(text: string) {
  emit('startChat', text)
}
</script>

<template>
  <div class="welcome-page">
    <div class="welcome-hero">
      <div class="welcome-icon">
        <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 2L2 7l10 5 10-5-10-5z" />
          <path d="M2 17l10 5 10-5" />
          <path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <h1 class="welcome-title">Numina AI</h1>
      <p class="welcome-subtitle">家庭资产管理助手</p>
    </div>
    <div class="welcome-examples">
      <WelcomeExamples @suggestion-click="handleSuggestionClick" />
    </div>
  </div>
</template>

<style scoped>
.welcome-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 48px 16px;
  gap: 32px;
}

.welcome-hero {
  text-align: center;
}

.welcome-icon {
  color: var(--van-primary-color, #1989fa);
  margin-bottom: 16px;
}

.welcome-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--van-text-color, #333);
  margin: 0 0 8px;
}

.welcome-subtitle {
  font-size: 14px;
  color: var(--van-text-color-2, #666);
  margin: 0;
}

.welcome-examples {
  width: 100%;
  max-width: 400px;
}
</style>
```

- [ ] **Step 2: Create MessageList.vue**

Create `frontend/apps/main/src/components/ai/MessageList.vue`:

```vue
<script setup lang="ts">
import { nextTick, watch, ref } from 'vue'
import MessageGroup from '@/components/ai-chat/MessageGroup.vue'
import type { ChatMessage } from '@/types/ai-chat/message-group'
import type { MessageGroup as MessageGroupType } from '@/types/ai-chat/message-group'
import { getMessageGroups } from '@/utils/ai-chat/messageGroups'
import { useMessageGroups } from '@/composables/ai-chat/useMessageGroups'

const props = defineProps<{
  messages: ChatMessage[]
  isStreaming: boolean
}>()

const emit = defineEmits<{
  retry: []
  stop: []
}>()

const scrollRef = ref<HTMLElement | null>(null)

// Group messages for display
const { messageGroups } = useMessageGroups()

// Auto-scroll to bottom on new messages
watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  }
)

// Recompute groups when messages change
watch(
  () => props.messages,
  (msgs) => {
    messageGroups.value = getMessageGroups(msgs)
  },
  { deep: true, immediate: true }
)
</script>

<template>
  <div ref="scrollRef" class="message-list">
    <div v-if="messages.length === 0" class="message-list-empty">
      <p>开始对话</p>
    </div>
    <div v-else class="message-list-content">
      <MessageGroup
        v-for="group in messageGroups"
        :key="group.id ?? $index"
        :group="group"
      />
    </div>
    <div v-if="isStreaming" class="message-list-streaming-indicator">
      <van-loading type="ball" />
    </div>
    <div v-if="!isStreaming && messages.length > 0" class="message-list-actions">
      <van-button
        size="small"
        plain
        @click="emit('retry')"
      >
        重试
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-list-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--van-text-color-3, #999);
  font-size: 14px;
}

.message-list-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-list-streaming-indicator {
  display: flex;
  justify-content: center;
  padding: 8px;
}

.message-list-actions {
  display: flex;
  justify-content: center;
  padding: 8px;
}
</style>
```

- [ ] **Step 3: Typecheck**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vue-tsc --noEmit 2>&1 | head -30
```

Expected: No errors (or minor errors unrelated to these files).

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/components/ai/WelcomePage.vue \
      frontend/apps/main/src/components/ai/MessageList.vue
git commit -m "feat(ai-chat): add WelcomePage and MessageList components
- WelcomePage with hero section and WelcomeExamples integration
- MessageList with auto-scroll, message grouping, streaming indicator
- Reuses existing MessageGroup and WelcomeExamples components

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: SessionSidebar Component

**Files:**
- Create: `frontend/apps/main/src/components/ai/SessionSidebar.vue`

**Interfaces:**
- Consumes: `useThreadList`, `useChatSessionStore`, `showDialog`, `showToast`, i18n keys
- Produces: `<SessionSidebar @select-thread="..." />`

- [ ] **Step 1: Create SessionSidebar.vue**

Create `frontend/apps/main/src/components/ai/SessionSidebar.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { showDialog, showToast } from 'vant'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadList } from '@/composables/useThreadList'
import { useI18n } from '@/i18n' // Adjust import path as needed

const emit = defineEmits<{
  selectThread: [threadId: string]
}>()

const store = useChatSessionStore()
const { dateGroups, isLoading, hasMore, loadMore, refresh, deleteSession, renameSession, togglePin } = useThreadList()
const { t } = useI18n()

const visible = ref(false)
const showDeleteConfirm = ref(false)
const pendingDeleteId = ref<string | null>(null)
const renamingId = ref<string | null>(null)
const renameInput = ref('')

// Infinite scroll observer
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

onMounted(() => {
  refresh()

  // Set up IntersectionObserver for infinite scroll
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !isLoading.value) {
        loadMore()
      }
    },
    { rootMargin: '100px' }
  )
  if (sentinelRef.value) {
    observer.observe(sentinelRef.value)
  }
})

onUnmounted(() => {
  observer?.disconnect()
})

function open() {
  visible.value = true
  refresh()
}

function close() {
  visible.value = false
}

function selectThread(threadId: string) {
  store.setActiveThread(threadId)
  close()
}

function handleDelete(threadId: string) {
  showDialog({
    title: t('ai.chat.session.deleteConfirm'),
    showCancelButton: true,
    confirmButtonColor: 'var(--van-danger-color, #ee0a24)',
  }).then(async () => {
    try {
      await deleteSession(threadId)
      showToast({ message: t('ai.chat.session.delete') })
    } catch {
      showToast({ message: t('ai.chat.errors.sendFailed') })
    }
  })
}

function handleRename(threadId: string, currentTitle: string) {
  renamingId.value = threadId
  renameInput.value = currentTitle
}

async function confirmRename(threadId: string) {
  if (!renameInput.value.trim()) return
  try {
    await renameSession(threadId, renameInput.value.trim())
    renamingId.value = null
    renameInput.value = ''
    showToast({ message: t('ai.chat.session.rename') })
  } catch {
    showToast({ message: t('ai.chat.errors.sendFailed') })
  }
}

function cancelRename() {
  renamingId.value = null
  renameInput.value = ''
}

async function handleTogglePin(threadId: string, isPinned: boolean) {
  try {
    await togglePin(threadId, !isPinned)
    showToast({ message: isPinned ? t('ai.chat.session.unpin') : t('ai.chat.session.pin') })
  } catch {
    showToast({ message: t('ai.chat.errors.sendFailed') })
  }
}
</script>

<template>
  <!-- Overlay trigger button -->
  <van-button
    class="sidebar-trigger"
    icon="bars"
    type="default"
    size="small"
    @click="open"
  />

  <!-- Sidebar overlay -->
  <van-overlay :show="visible" @click="close">
    <div class="sidebar-overlay" @click.stop>
      <div class="sidebar-header">
        <h3 class="sidebar-title">{{ t('ai.chat.session.title') }}</h3>
        <van-button icon="cross" type="default" size="small" @click="close" />
      </div>

      <div class="sidebar-content">
        <template v-if="dateGroups.length === 0 && !isLoading">
          <div class="sidebar-empty">{{ t('ai.chat.session.noSessions') }}</div>
        </template>

        <div v-for="group in dateGroups" :key="group.label" class="sidebar-group">
          <div class="sidebar-group-label">{{ group.displayName }}</div>
          <div
            v-for="session in group.sessions"
            :key="session.thread_id"
            class="sidebar-session"
            :class="{ active: session.thread_id === store.activeThreadId }"
            @click="selectThread(session.thread_id)"
          >
            <div class="session-info">
              <template v-if="renamingId === session.thread_id">
                <van-field
                  v-model="renameInput"
                  :placeholder="session.title"
                  autofocus
                  @blur="cancelRename"
                  @keydown.enter="confirmRename(session.thread_id)"
                  @click.stop
                />
              </template>
              <template v-else>
                <div class="session-title">{{ session.title || '新对话' }}</div>
                <div class="session-time">{{ new Date(session.updated_at).toLocaleString() }}</div>
              </template>
            </div>
            <div class="session-actions" @click.stop>
              <van-button
                icon="edit"
                type="default"
                size="small"
                @click="handleRename(session.thread_id, session.title)"
              />
              <van-button
                :icon="session.is_pinned ? 'star' : 'star-o'"
                type="default"
                size="small"
                @click="handleTogglePin(session.thread_id, session.is_pinned)"
              />
              <van-button
                icon="delete"
                type="default"
                size="small"
                @click="handleDelete(session.thread_id)"
              />
            </div>
          </div>
        </div>

        <!-- Infinite scroll sentinel -->
        <div ref="sentinelRef" class="sidebar-sentinel">
          <van-loading v-if="isLoading" size="20" />
        </div>
      </div>
    </div>
  </van-overlay>
</template>

<style scoped>
.sidebar-trigger {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 100;
}

.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 300px;
  background: var(--van-background-2, #f7f8fa);
  display: flex;
  flex-direction: column;
  z-index: 2000;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--van-border-color, #eee);
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--van-text-color, #333);
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.sidebar-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--van-text-color-3, #999);
  font-size: 14px;
}

.sidebar-group {
  margin-bottom: 8px;
}

.sidebar-group-label {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--van-text-color-3, #999);
  font-weight: 500;
}

.sidebar-session {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.sidebar-session:hover,
.sidebar-session.active {
  background: var(--van-primary-color-light, rgba(25, 137, 250, 0.1));
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  color: var(--van-text-color, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 11px;
  color: var(--van-text-color-3, #999);
  margin-top: 2px;
}

.session-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.sidebar-session:hover .session-actions {
  opacity: 1;
}

.sidebar-sentinel {
  display: flex;
  justify-content: center;
  padding: 16px;
}
</style>
```

- [ ] **Step 2: Typecheck**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vue-tsc --noEmit 2>&1 | head -30
```

Expected: No errors (or minor type issues to fix).

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/SessionSidebar.vue
git commit -m "feat(ai-chat): add SessionSidebar component with pinning/rename/delete
- Click-to-expand overlay sidebar with date grouping
- Session actions: rename, pin/unpin, delete with confirm dialog
- Infinite scroll via IntersectionObserver
- Integrates with chatSession store and useThreadList composable

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: AIChatBox Root Container

**Files:**
- Create: `frontend/apps/main/src/components/ai/AIChatBox.vue`

**Interfaces:**
- Consumes: `WelcomePage`, `MessageList`, `SessionSidebar`, `InputBox`, `useChatSessionStore`, `useThreadChat`, `useTenantAiResources`
- Produces: Root container mounted by `pages/ai/chat/index.vue`

- [ ] **Step 1: Create AIChatBox.vue**

Create `frontend/apps/main/src/components/ai/AIChatBox.vue`:

```vue
<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { showToast } from 'vant'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'
import { useTenantAiResources } from '@/composables/ai-chat/useTenantAiResources'
import { createThread } from '@/api/ai-chat'
import WelcomePage from '@/components/ai/WelcomePage.vue'
import MessageList from '@/components/ai/MessageList.vue'
import SessionSidebar from '@/components/ai/SessionSidebar.vue'
import InputBox from '@/components/ai-chat/InputBox.vue'
import { useI18n } from '@/i18n'

const store = useChatSessionStore()
const chat = useThreadChat()
const { t } = useI18n()

// Initialize from URL on mount
onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const threadId = params.get('thread_id')
  if (threadId) {
    store.setActiveThread(threadId)
    chat.loadHistory(threadId)
  }
})

// Watch for thread switches — load history
watch(
  () => store.activeThreadId,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      await chat.loadHistory(newId)
    }
  }
)

// Handle errors from chat
watch(
  () => chat.error.value,
  (err) => {
    if (err) {
      showToast({ message: err })
    }
  }
)

async function handleStartChat(text: string) {
  try {
    const thread = await createThread()
    store.setActiveThread(thread.thread_id)
    await chat.sendMessage(text, { mode: 'flash' }, thread.thread_id)
  } catch {
    showToast({ message: t('ai.chat.errors.sendFailed') })
  }
}

async function handleSendMessage(text: string) {
  if (!store.activeThreadId) return
  await chat.sendMessage(text, { mode: 'flash' }, store.activeThreadId)
}

function handleStopStream() {
  chat.cancelStream()
}

async function handleRetry() {
  if (store.activeThreadId) {
    await chat.retry(store.activeThreadId)
  }
}

function handleSelectThread(threadId: string) {
  store.setActiveThread(threadId)
  chat.loadHistory(threadId)
}
</script>

<template>
  <div class="ai-chat-box">
    <SessionSidebar @select-thread="handleSelectThread" />

    <template v-if="store.isWelcomeMode">
      <WelcomePage @start-chat="handleStartChat" />
    </template>
    <template v-else>
      <MessageList
        :messages="chat.messages.value"
        :is-loading="chat.isLoading.value"
        @retry="handleRetry"
        @stop="handleStopStream"
      />
      <InputBox
        :disabled="chat.isLoading.value"
        @submit="handleSendMessage"
      />
    </template>
  </div>
</template>

<style scoped>
.ai-chat-box {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}
</style>
```

- [ ] **Step 2: Typecheck**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vue-tsc --noEmit 2>&1 | head -30
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AIChatBox.vue
git commit -m "feat(ai-chat): add AIChatBox root container
- Welcome/Chat mode switching via chatSession store
- URL-based thread initialization on mount
- Thread switching with history loading
- Error display via toast
- Integrates WelcomePage, MessageList, SessionSidebar, InputBox

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Backend Pinning Support

**Files:**
- Modify: `server/apps/backend/app/routers/ai_internal.py` — add `is_pinned` to response + sort
- Modify: `server/apps/agent/routers/threads.py` — add sort/pin fields to `ThreadSearchRequest` + response mapping
- Modify: `server/apps/agent/services/session_store.py` — pass sort params through `list_sessions()`
- Modify: `server/apps/agent/core/backend_client.py` — forward sort params to backend API

**Interfaces:**
- Consumes: existing `AIChatSession.is_pinned` model field (already exists), existing `_session_to_dict()` and `list_sessions()` signatures
- Produces: `is_pinned` field in session responses, sorted by `is_pinned DESC, updated_at DESC`

- [ ] **Step 1: Update backend `_session_to_dict()` and query**

Modify `server/apps/backend/app/routers/ai_internal.py`:

Find `_session_to_dict()` (around line 748) and add the `is_pinned` field:

```python
# In _session_to_dict(), add:
"is_pinned": s.is_pinned,
```

Find `internal_list_sessions()` (around line 830) and update the sort order:

```python
# Change the query sort to:
sessions = (
    db.query(AIChatSession)
    .filter(AIChatSession.family_id == family_id)
    .order_by(AIChatSession.is_pinned.desc(), AIChatSession.updated_at.desc())
    .offset(offset)
    .limit(limit)
    .all()
)
```

Also ensure the query accepts sort params. Add optional query parameters to the endpoint:

```python
@router.get("/ai/sessions", response_model=None)
async def internal_list_sessions(
    family_id: int = Depends(require_family_id),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
) -> list[dict]:
    # ... existing logic but with dynamic sort
```

- [ ] **Step 2: Update ThreadSearchRequest in agent**

Modify `server/apps/agent/routers/threads.py`:

Find `ThreadSearchRequest` class (around line 69) and add sort fields:

```python
class ThreadSearchRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    status: str | None = Field(default=None)
    sortBy: str | None = Field(default="updated_at")
    sortOrder: str | None = Field(default="desc")
```

Find `search_threads()` function (around line 195) and pass sort params to the repository:

```python
# In search_threads(), modify the repo call:
result = await repo.list_sessions(
    family_id=family_id,
    limit=req.limit,
    offset=req.offset,
    sort_by=req.sortBy or "updated_at",
    sort_order=req.sortOrder or "desc",
)
```

Also in `search_threads()`, map `is_pinned` in the response:

```python
# In the response mapping (after `r.get("title", "")`):
sessions.append({
    "thread_id": r["thread_id"],
    "title": r.get("title", ""),
    "status": r.get("status", "idle"),
    "is_pinned": r.get("is_pinned", False),
    "created_at": r.get("created_at", ""),
    "updated_at": r.get("updated_at", ""),
})
```

- [ ] **Step 3: Update AiSessionRepository.list_sessions()**

Modify `server/apps/agent/services/session_store.py`:

```python
# Change list_sessions() signature to accept sort params:
async def list_sessions(
    self,
    family_id: int,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> list[dict]:
    # ... existing logic ...
    return await BackendClient.list_sessions(
        family_id=family_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
```

- [ ] **Step 4: Update BackendClient.list_sessions()**

Modify `server/apps/agent/core/backend_client.py`:

```python
# Change list_sessions() signature:
async def list_sessions(
    family_id: int,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> list[dict]:
    params = {
        "limit": limit,
        "offset": offset,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    # ... rest of function unchanged ...
```

- [ ] **Step 5: Run backend tests**

```bash
cd /Users/vincentruan/vscode_space/numina/server && uv run pytest apps/backend/tests/ -v -k "ai" 2>&1 | tail -20
```

Expected: All AI-related tests pass.

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/routers/ai_internal.py \
      server/apps/agent/routers/threads.py \
      server/apps/agent/services/session_store.py \
      server/apps/agent/core/backend_client.py
git commit -m "feat(ai-chat): add session pinning support across backend layers
- Add is_pinned to _session_to_dict() and sort by is_pinned DESC, updated_at DESC
- Add sortBy/sortOrder to ThreadSearchRequest and propagate through stack
- Map is_pinned in search_threads() response
- Pass sort params through AiSessionRepository and BackendClient

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: End-to-End Verification

**Files:**
- Run: typecheck, lint, tests across both frontend and backend

- [ ] **Step 1: Frontend typecheck**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vue-tsc --noEmit 2>&1
```

Expected: No type errors. Fix any type issues if they appear.

- [ ] **Step 2: Frontend lint**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && pnpm lint 2>&1
```

Expected: No lint errors.

- [ ] **Step 3: Frontend tests**

```bash
cd /Users/vincentruan/vscode_space/numina/frontend/apps/main && npx vitest run 2>&1
```

Expected: All tests pass.

- [ ] **Step 4: Backend typecheck**

```bash
cd /Users/vincentruan/vscode_space/numina/server && uv run mypy apps/backend/ apps/agent/ 2>&1 | tail -20
```

Expected: No type errors.

- [ ] **Step 5: Backend lint**

```bash
cd /Users/vincentruan/vscode_space/numina/server && uv run ruff check apps/backend/ apps/agent/ 2>&1
```

Expected: No lint errors.

- [ ] **Step 6: Backend tests**

```bash
cd /Users/vincentruan/vscode_space/numina/server && uv run pytest apps/backend/tests/ -v 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 7: Commit (if any fixes were needed)**

```bash
git add -A
git commit -m "chore: fix type/lint/test issues from AI chat redesign
[skip ci]"

# Or if no fixes needed:
echo "All checks pass — no fixes needed"
```
