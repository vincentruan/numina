import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock vue-i18n — preserve createI18n (used by @/i18n which @/api/index
// imports) so the i18n graph loads cleanly, while forcing useI18n().t to
// return the key verbatim. Mirrors useThreadChat.compact.spec.ts.
vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }),
  }
})

vi.mock('../useSubtasks', () => ({
  useUpdateSubtask: () => ({ handleTaskEvent: vi.fn() }),
}))

vi.mock('@/api/ai-chat', () => ({
  getClient: vi.fn(() => ({ runs: { cancel: vi.fn().mockResolvedValue(undefined) } })),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
  compactThread: vi.fn(),
  getThreadGoal: vi.fn(),
  setThreadGoal: vi.fn(),
  clearThreadGoal: vi.fn(),
  streamChatRun: vi.fn(),
}))

vi.mock('@/api/sessions', () => ({
  submitMessageFeedback: vi.fn(),
  getSessionFeedback: vi.fn(),
}))

vi.mock('vant', () => ({
  showSuccessToast: vi.fn(),
  showFailToast: vi.fn(),
  showToast: vi.fn(),
}))

const STORAGE_KEY = 'numina:chat-stream-state'

/** Minimal in-memory sessionStorage so the persistence helpers can be exercised. */
function installSessionStorage() {
  const store = new Map<string, string>()
  Object.defineProperty(globalThis, 'sessionStorage', {
    configurable: true,
    value: {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => { store.set(k, v) },
      removeItem: (k: string) => { store.delete(k) },
      clear: () => { store.clear() },
      key: (i: number) => Array.from(store.keys())[i] ?? null,
      get length() { return store.size },
    },
  })
  return store
}

function makeMessage(id: string, type: 'human' | 'ai' | 'tool', content: string) {
  return {
    id,
    type,
    role: type === 'human' ? 'user' as const : 'assistant' as const,
    content,
    displayTime: '2026-11-03T12:00:00.000Z',
  }
}

describe('useThreadChat — T20 sessionStorage persistence', () => {
  let store: Map<string, string>

  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    store = installSessionStorage()
  })

  afterEach(() => {
    store.clear()
  })

  async function loadComposable() {
    const { useThreadChat } = await import('../useThreadChat')
    return useThreadChat()
  }

  describe('save path (abortLocalStream)', () => {
    it('does not write a snapshot when no stream is active', async () => {
      const chat = await loadComposable()
      chat.abortLocalStream()
      expect(store.has(STORAGE_KEY)).toBe(false)
    })

    it('writes a streaming snapshot while a stream is active', async () => {
      // Drive a stream that yields one AI chunk then suspends, so the
      // composable is mid-stream when abortLocalStream runs.
      let releaseStream: (() => void) | null = null
      const gate = new Promise<void>((resolve) => { releaseStream = resolve })
      const mockStreamChatRun = vi.fn().mockImplementation(() => ({
        async *[Symbol.asyncIterator]() {
          yield { event: 'messages-tuple', data: { type: 'ai', id: 'ai-1', content: 'hi' } }
          await gate
          yield { event: 'end', data: { status: 'complete' } }
        },
      }))
      const { streamChatRun } = await import('@/api/ai-chat')
      vi.mocked(streamChatRun).mockImplementation(mockStreamChatRun)

      const chat = await loadComposable()
      const sending = chat.sendMessage('hello', { threadId: 'thread-1' })
      // Let the stream start and the first chunk land.
      await new Promise((r) => setTimeout(r, 0))

      chat.abortLocalStream()

      // Assert while the stream is still suspended — releasing it would run the
      // terminal `end` handler, which correctly clears the snapshot (R6).
      const raw = store.get(STORAGE_KEY)
      expect(raw).toBeTruthy()
      const saved = JSON.parse(raw as string)
      expect(saved.status).toBe('streaming')
      expect(saved.threadId).toBe('thread-1')
      expect(Array.isArray(saved.messages)).toBe(true)

      releaseStream?.()
      await sending.catch(() => {})
    })

    it('does not write a snapshot on user-initiated cancelStream', async () => {
      const chat = await loadComposable()
      chat.cancelStream()
      expect(store.has(STORAGE_KEY)).toBe(false)
    })
  })

  describe('restore path', () => {
    it('starts empty when nothing was saved', async () => {
      const chat = await loadComposable()
      expect(chat.messages.value).toEqual([])
      expect(chat.isLoading.value).toBe(false)
    })

    it('restores messages and loading state from a streaming snapshot', async () => {
      store.set(STORAGE_KEY, JSON.stringify({
        status: 'streaming',
        threadId: 'thread-9',
        runId: 'run-9',
        messages: [makeMessage('human-1', 'human', 'question')],
        planningSteps: [],
        error: null,
      }))

      const chat = await loadComposable()
      expect(chat.messages.value).toHaveLength(1)
      expect(chat.messages.value[0].content).toBe('question')
      expect(chat.isLoading.value).toBe(true)
      expect(chat.runId.value).toBe('run-9')
    })

    it('ignores a completed snapshot (terminal states are not restored)', async () => {
      store.set(STORAGE_KEY, JSON.stringify({
        status: 'completed',
        threadId: 'thread-9',
        runId: 'run-9',
        messages: [makeMessage('human-1', 'human', 'stale')],
        planningSteps: [],
        error: null,
      }))

      const chat = await loadComposable()
      expect(chat.messages.value).toEqual([])
    })

    it('ignores a corrupted snapshot', async () => {
      store.set(STORAGE_KEY, '{not json')
      const chat = await loadComposable()
      expect(chat.messages.value).toEqual([])
    })
  })

  describe('clear path', () => {
    it('clears the snapshot when a stream completes', async () => {
      store.set(STORAGE_KEY, JSON.stringify({
        status: 'streaming',
        threadId: 'thread-1',
        runId: 'run-1',
        messages: [],
        planningSteps: [],
        error: null,
      }))

      const mockStreamChatRun = vi.fn().mockImplementation(() => ({
        async *[Symbol.asyncIterator]() {
          yield { event: 'end', data: { status: 'complete' } }
        },
      }))
      const { streamChatRun } = await import('@/api/ai-chat')
      vi.mocked(streamChatRun).mockImplementation(mockStreamChatRun)

      const chat = await loadComposable()
      await chat.sendMessage('hello', { threadId: 'thread-1' })

      expect(store.has(STORAGE_KEY)).toBe(false)
    })

    it('clears the snapshot when a new generation starts', async () => {
      store.set(STORAGE_KEY, JSON.stringify({
        status: 'streaming',
        threadId: 'thread-old',
        runId: 'run-old',
        messages: [makeMessage('ai-old', 'ai', 'stale reply')],
        planningSteps: [],
        error: null,
      }))

      const mockStreamChatRun = vi.fn().mockImplementation(() => ({
        async *[Symbol.asyncIterator]() {
          yield { event: 'end', data: { status: 'complete' } }
        },
      }))
      const { streamChatRun } = await import('@/api/ai-chat')
      vi.mocked(streamChatRun).mockImplementation(mockStreamChatRun)

      const chat = await loadComposable()
      expect(chat.messages.value).toHaveLength(1) // restored first

      await chat.sendMessage('fresh', { threadId: 'thread-new' })

      // The snapshot itself is gone; the stale message is not part of the new
      // generation's stream. (The restored message object remains in the local
      // array — that is pre-existing sendMessage behaviour, not T20's concern.)
      expect(store.has(STORAGE_KEY)).toBe(false)
    })

    it('clears the snapshot on user-initiated cancel during a stream', async () => {
      let releaseStream: (() => void) | null = null
      const gate = new Promise<void>((resolve) => { releaseStream = resolve })
      const mockStreamChatRun = vi.fn().mockImplementation(() => ({
        async *[Symbol.asyncIterator]() {
          yield { event: 'messages-tuple', data: { type: 'ai', id: 'ai-1', content: 'hi' } }
          await gate
          yield { event: 'end', data: { status: 'complete' } }
        },
      }))
      const { streamChatRun } = await import('@/api/ai-chat')
      vi.mocked(streamChatRun).mockImplementation(mockStreamChatRun)

      const chat = await loadComposable()
      const sending = chat.sendMessage('hello', { threadId: 'thread-1' })
      await new Promise((r) => setTimeout(r, 0))

      // Simulate page-leave save, then an explicit user cancel.
      chat.abortLocalStream()
      expect(store.has(STORAGE_KEY)).toBe(true)
      chat.cancelStream()
      expect(store.has(STORAGE_KEY)).toBe(false)

      releaseStream?.()
      await sending.catch(() => {})
    })
  })

  describe('loadHistory does not destroy the snapshot', () => {
    it('keeps the snapshot when loadHistory cancels an in-flight stream', async () => {
      store.set(STORAGE_KEY, JSON.stringify({
        status: 'streaming',
        threadId: 'thread-1',
        runId: 'run-1',
        messages: [],
        planningSteps: [],
        error: null,
      }))

      const { getClient } = await import('@/api/ai-chat')
      vi.mocked(getClient).mockReturnValue({
        runs: { cancel: vi.fn().mockResolvedValue(undefined) },
        threads: {
          getState: vi.fn().mockResolvedValue({ values: { messages: [] } }),
        },
      } as unknown as ReturnType<typeof getClient>)
      vi.mocked((await import('@/api/sessions')).getSessionFeedback)
        .mockResolvedValue({ data: { items: {} } } as never)

      const chat = await loadComposable()
      await chat.loadHistory('thread-1')

      expect(store.has(STORAGE_KEY)).toBe(true)
    })
  })
})
