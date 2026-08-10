import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock vue-i18n — preserve createI18n (used by @/i18n which @/api/index
// imports) so the i18n graph loads cleanly, while forcing useI18n().t to
// return the key verbatim for toast assertions. Mirrors AIChatBox.spec.ts.
vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }),
  }
})

// Mock subtask composable
vi.mock('../useSubtasks', () => ({
  useUpdateSubtask: () => ({
    handleTaskEvent: vi.fn(),
  }),
}))

// Mock the API module (compactThread is exercised in handleCompact tests)
vi.mock('@/api/ai-chat', () => ({
  getClient: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
  compactThread: vi.fn(),
}))

// Mock vant toasts so no DOM is required. handleCompact uses showToast for
// the informational skip path and showSuccessToast/showFailToast for the
// success/failure paths (frontend/CLAUDE.md §Key Invariants).
vi.mock('vant', () => ({
  showSuccessToast: vi.fn(),
  showFailToast: vi.fn(),
  showToast: vi.fn(),
}))

// Toast fns + compactThread are resolved dynamically inside each test (via
// `await import`) so no top-level static import of @/api/ai-chat pulls the
// i18n graph (createI18n) in before the vue-i18n mock settles — mirrors the
// useThreadChat.interrupt.spec.ts pattern.

/**
 * U6 transient bridge + /compact command handler tests.
 *
 * Covers:
 * - summarization values event stores dropped turns in the bridge
 * - canonical history (loadHistory) confirms + prunes the bridge
 * - isWelcomeMode skip (no threadId) → compactSkipped toast
 * - handleCompact success/skipped paths
 *
 * Algorithm ported from DeerFlow hooks.ts:441-545,1277-1322; lifecycle glue
 * rewritten as Vue (reactive ref + watch).
 */
describe('useThreadChat — U6 compact transient bridge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * Helper: build a fake SSE stream and drive it through sendMessage so we can
   * feed a summarization `values` event (shorter message list) and inspect the
   * bridge via visibleMessages.
   */
  async function runWithChunks(
    chunks: Array<{ event: string; data?: unknown }>,
  ) {
    const mockStream = {
      async *[Symbol.asyncIterator]() {
        for (const chunk of chunks) {
          yield chunk
        }
      },
    }
    const mockRunsStream = vi.fn().mockReturnValue(mockStream)
    const { getClient } = await import('@/api/ai-chat')
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: mockRunsStream },
    } as unknown as ReturnType<typeof getClient>)

    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    await chat.sendMessage('hello', undefined, 'thread-1')
    return chat
  }

  function aiMsg(id: string, content = `ai-${id}`) {
    return { type: 'ai', id, content }
  }

  it('summarization values event rescues dropped turns into visibleMessages', async () => {
    // Stream: two AI turns accumulate, then a summarization `values` event
    // arrives carrying ONLY the preserved tail (last message). The dropped
    // first turn must remain visible via the transient bridge so the UI does
    // not flicker.
    const chat = await runWithChunks([
      { event: 'messages-tuple', data: aiMsg('m1', 'first answer') },
      { event: 'messages-tuple', data: aiMsg('m2', 'second answer') },
      // Summarization: values event with a SHORTER list sharing the tail id.
      { event: 'values', data: { messages: [aiMsg('m2', 'second answer')] } },
      { event: 'end', data: { status: 'success' } },
    ])

    // m1 was dropped by the summarization values event; the bridge should
    // keep it visible alongside the canonical tail (m2).
    const visibleIds = chat.visibleMessages.value.map(m => m.id)
    expect(visibleIds).toContain('m1')
    expect(visibleIds).toContain('m2')
  })

  it('loadHistory drains the transient bridge (authoritative reload)', async () => {
    const chat = await runWithChunks([
      { event: 'messages-tuple', data: aiMsg('m1', 'first') },
      { event: 'messages-tuple', data: aiMsg('m2', 'second') },
      { event: 'values', data: { messages: [aiMsg('m2', 'second')] } },
      { event: 'end', data: { status: 'success' } },
    ])
    expect(chat.visibleMessages.value.map(m => m.id)).toContain('m1')

    // Simulate the post-compact history reload: getState returns the short
    // tail. loadHistory is authoritative → bridge is drained.
    const { getClient } = await import('@/api/ai-chat')
    vi.mocked(getClient).mockReturnValue({
      threads: {
        getState: async () => ({ values: { messages: [aiMsg('m2', 'second')] } }),
      },
    } as unknown as ReturnType<typeof getClient>)

    await chat.loadHistory('thread-1')

    // After authoritative reload, the dropped turn is gone (intentionally
    // summarized away) — bridge is empty, visibleMessages === messages.
    expect(chat.visibleMessages.value.map(m => m.id)).toEqual(['m2'])
    expect(chat.visibleMessages.value.map(m => m.id)).not.toContain('m1')
  })

  it('handleCompact with no threadId → compactSkipped toast, no API call', async () => {
    const { showToast } = await import('vant')
    const { compactThread } = await import('@/api/ai-chat')
    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    await chat.handleCompact(null)

    expect(vi.mocked(showToast)).toHaveBeenCalledWith('aiChat.compactSkipped')
    expect(vi.mocked(compactThread)).not.toHaveBeenCalled()
  })

  it('handleCompact success → compactSuccess toast + history reload', async () => {
    const { showSuccessToast } = await import('vant')
    const { compactThread, getClient } = await import('@/api/ai-chat')
    vi.mocked(compactThread).mockResolvedValue({
      compacted: true,
      reason: null,
      removed_count: 3,
      preserved_count: 2,
      summary_updated: true,
      checkpoint_id: 'ckpt-new',
      total_tokens: 100,
    })
    vi.mocked(getClient).mockReturnValue({
      threads: {
        getState: async () => ({ values: { messages: [aiMsg('m2', 'tail')] } }),
      },
    } as unknown as ReturnType<typeof getClient>)

    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    await chat.handleCompact('thread-1')

    expect(vi.mocked(compactThread)).toHaveBeenCalledWith('thread-1')
    expect(vi.mocked(showSuccessToast)).toHaveBeenCalledWith('aiChat.compactSuccess')
  })

  it('handleCompact not compacted (not_enough_messages) → compactSkipped toast', async () => {
    const { showToast } = await import('vant')
    const { compactThread, getClient } = await import('@/api/ai-chat')
    vi.mocked(compactThread).mockResolvedValue({
      compacted: false,
      reason: 'not_enough_messages',
      removed_count: 0,
      preserved_count: 0,
      summary_updated: false,
      checkpoint_id: null,
      total_tokens: 0,
    })
    vi.mocked(getClient).mockReturnValue({
      threads: { getState: async () => ({ values: { messages: [] } }) },
    } as unknown as ReturnType<typeof getClient>)

    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    await chat.handleCompact('thread-1')

    expect(vi.mocked(showToast)).toHaveBeenCalledWith('aiChat.compactSkipped')
  })

  it('handleCompact backend failure → compactFailed toast', async () => {
    const { showFailToast } = await import('vant')
    const { compactThread, getClient } = await import('@/api/ai-chat')
    vi.mocked(compactThread).mockRejectedValue(new Error('压缩对话历史失败'))
    vi.mocked(getClient).mockReturnValue({
      threads: { getState: async () => ({ values: { messages: [] } }) },
    } as unknown as ReturnType<typeof getClient>)

    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    await chat.handleCompact('thread-1')

    expect(vi.mocked(showFailToast)).toHaveBeenCalledWith('aiChat.compactFailed')
  })
})
