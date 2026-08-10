import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'

// Mock dependencies
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }),
}))

vi.mock('@/api/ai-chat', () => ({
  getClient: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
}))

// Mock the sessions API module (used by feedback hydration/submit)
vi.mock('@/api/sessions', () => ({
  submitMessageFeedback: vi.fn(),
  getSessionFeedback: vi.fn().mockResolvedValue({ data: { items: {} } }),
}))

vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({ family: { id: 'fam-1' } }),
}))

import { getClient, createThread } from '@/api/ai-chat'

function makeMockStream(events: Array<{ event: string; data?: unknown }>) {
  return {
    async *[Symbol.asyncIterator]() {
      for (const ev of events) {
        yield ev
      }
    },
  }
}

describe('useThreadChat — U1 SSE extensions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(createThread).mockResolvedValue({ thread_id: 'thread-1' } as never)
  })

  it('parses custom tool_call event into planningSteps', async () => {
    const mockStream = makeMockStream([
      { event: 'custom', data: { type: 'tool_call', tool_call_id: 'tc-1', tool_name: 'web_search', args: { query: 'test' } } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    expect(chat.planningSteps.value).toHaveLength(1)
    expect(chat.planningSteps.value[0].toolName).toBe('web_search')
    expect(chat.planningSteps.value[0].status).toBe('done') // marked done on end
  })

  it('parses custom suggestions event into suggestions ref', async () => {
    const mockStream = makeMockStream([
      { event: 'messages-tuple', data: { type: 'ai', content: 'Hello!', id: 'ai-1' } },
      { event: 'custom', data: { type: 'suggestions', suggestions: ['Q1', 'Q2', 'Q3'] } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    // After stream ends, suggestions are cleared from standalone ref (Issue 1 fix)
    // and attached inline to the last AI message instead
    expect(chat.suggestions.value).toEqual([])
    const lastAi = chat.messages.value.filter(m => m.type === 'ai').pop()
    expect(lastAi?.suggestions).toEqual(['Q1', 'Q2', 'Q3'])
  })

  it('captures metadata run_id', async () => {
    const mockStream = makeMockStream([
      { event: 'metadata', data: { run_id: 'run-abc' } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    expect(chat.runId.value).toBe('run-abc')
  })

  it('cancelStream passes the real run_id to runs.cancel', async () => {
    // runs.cancel is async in the SDK — the mock must return a Promise so
    // cancelStream's .catch(() => {}) chaining does not blow up.
    const cancelMock = vi.fn().mockResolvedValue(undefined)
    const mockStream = makeMockStream([
      { event: 'metadata', data: { run_id: 'run-xyz' } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: cancelMock },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    // metadata event has been processed, so runId is captured
    expect(chat.runId.value).toBe('run-xyz')

    chat.cancelStream()
    expect(cancelMock).toHaveBeenCalledWith('thread-1', 'run-xyz')
  })

  it('extracts usage_metadata from values events', async () => {
    const mockStream = makeMockStream([
      {
        event: 'values',
        data: {
          messages: [{
            id: 'ai-1',
            type: 'ai',
            content: 'Answer',
            usage_metadata: { input_tokens: 100, output_tokens: 50 },
          }],
        },
      },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    const aiMsg = chat.messages.value.find(m => m.id === 'ai-1')
    expect(aiMsg?.usageMetadata).toEqual({ inputTokens: 100, outputTokens: 50 })
  })

  it('clears planningSteps at start of each sendMessage', async () => {
    const mockStream1 = makeMockStream([
      { event: 'custom', data: { type: 'tool_call', tool_call_id: 'tc-1', tool_name: 'web_search', args: {} } },
      { event: 'end', data: null },
    ])
    const mockStream2 = makeMockStream([
      { event: 'end', data: null },
    ])
    let callCount = 0
    vi.mocked(getClient).mockReturnValue({
      runs: {
        stream: () => (++callCount === 1 ? mockStream1 : mockStream2),
        cancel: vi.fn(),
      },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')
    expect(chat.planningSteps.value).toHaveLength(1)

    await chat.sendMessage('follow-up', undefined, 'thread-1')
    expect(chat.planningSteps.value).toHaveLength(0)
  })

  it('retries on stream error and succeeds', async () => {
    vi.useFakeTimers()
    let callCount = 0
    vi.mocked(getClient).mockReturnValue({
      runs: {
        stream: () => {
          callCount++
          if (callCount === 1) {
            return {
              async *[Symbol.asyncIterator]() {
                throw new Error('Network error')
              },
            }
          }
          return makeMockStream([{ event: 'end', data: null }])
        },
        cancel: vi.fn(),
      },
    } as never)

    const chat = useThreadChat()
    const promise = chat.sendMessage('hello', undefined, 'thread-1')

    // Advance through first retry delay (1s)
    await vi.advanceTimersByTimeAsync(1000)
    await promise

    expect(callCount).toBe(2)
    expect(chat.error.value).toBeNull()
    vi.useRealTimers()
  }, 10000)

  it('retries with input:null when prior attempt already streamed AI content (no duplicate user message)', async () => {
    // Regression: when the first attempt streamed an AI greeting and then the
    // backend sent an `error` event (worker.py completion_status defaults to
    // "error" when DeerFlow emits an error frame mid-stream), finalizeAllInProgress
    // flipped the AI message to phase='done' before throwing. The retry's
    // hasPriorProgress check only looked for phase==='answering', so it returned
    // false → re-sent the user message → backend re-executed the LLM with a NEW
    // message id → mergeValuesMessages (dedup by id) appended a duplicate
    // greeting instead of merging. Each of 3 retries produced a fresh duplicate
    // until SSE_MAX_RETRIES exhausted and the last was flagged error — matching
    // the reported "greeting output, then repeated twice, third attempt failed".
    // Fix: hasPriorProgress keys off any AI message that arrived after this
    // turn's user message, regardless of phase. Retry must pass input:null.
    vi.useFakeTimers()
    const streamCalls: Array<{ input: unknown }> = []
    let callCount = 0
    vi.mocked(getClient).mockReturnValue({
      runs: {
        stream: (_threadId: string, _agent: string, opts: { input?: unknown }) => {
          callCount++
          streamCalls.push({ input: opts?.input ?? null })
          if (callCount === 1) {
            // First attempt: stream an AI greeting, then error mid-stream.
            return makeMockStream([
              { event: 'messages-tuple', data: { type: 'ai', id: 'ai-1', content: '你好，我是数鸣。' } },
              { event: 'error', data: { message: 'upstream error' } },
            ])
          }
          // Retry succeeds.
          return makeMockStream([{ event: 'end', data: { status: 'complete' } }])
        },
        cancel: vi.fn(),
      },
    } as never)

    const chat = useThreadChat()
    const promise = chat.sendMessage('帮我看看家庭财务近况', undefined, 'thread-1')
    await vi.advanceTimersByTimeAsync(1000)
    await promise

    // First attempt sends the user message; retry must resume with input:null.
    expect(streamCalls).toHaveLength(2)
    expect(streamCalls[0].input).not.toBeNull()
    expect(streamCalls[1].input).toBeNull()
    // No duplicate AI greeting — the original is the only one.
    const aiMessages = chat.messages.value.filter(m => m.type === 'ai')
    expect(aiMessages).toHaveLength(1)
    expect(aiMessages[0].content).toBe('你好，我是数鸣。')
    vi.useRealTimers()
  }, 10000)

  it('sets error after 3 consecutive failures', async () => {
    vi.useFakeTimers()
    vi.mocked(getClient).mockReturnValue({
      runs: {
        stream: () => ({
          async *[Symbol.asyncIterator]() {
            throw new Error('Network error')
          },
        }),
        cancel: vi.fn(),
      },
    } as never)

    const chat = useThreadChat()
    const promise = chat.sendMessage('hello', undefined, 'thread-1')

    // Advance through retry delays: 1s, 2s, 4s
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(2000)
    await vi.advanceTimersByTimeAsync(4000)
    await promise

    // 1 initial + 3 retries = 4 total attempts
    expect(chat.error.value).toBe('Network error')
    vi.useRealTimers()
  }, 15000)

  it('exposes isStreaming as computed alias', () => {
    const chat = useThreadChat()
    expect(chat.isStreaming.value).toBe(false)
  })

  it('does not add human messages from values events (skips [SKILL:chat] wrapper)', async () => {
    // The agent adapter wraps the user message as `[SKILL:chat]\n{json}` for
    // the DeerFlow harness. LangGraph persists that wrapper as the human message
    // and replays it via values events. The optimistic message (with the user's
    // original text) is authoritative — the wrapper must not produce a duplicate
    // human bubble showing raw JSON.
    const mockStream = makeMockStream([
      {
        event: 'values',
        data: {
          messages: [
            { id: 'human-backend-1', type: 'human', content: '[SKILL:chat]\n{"free_text":"hello"}' },
            { id: 'ai-1', type: 'ai', content: 'Answer' },
          ],
        },
      },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    const humanMessages = chat.messages.value.filter(m => m.type === 'human')
    expect(humanMessages).toHaveLength(1)
    expect(humanMessages[0].content).toBe('hello')
    expect(humanMessages[0].sendStatus).toBe('sent')
  })

  it('transitions optimistic user message sendStatus from sending to sent', async () => {
    const mockStream = makeMockStream([
      { event: 'metadata', data: { run_id: 'run-1' } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    const humanMsg = chat.messages.value.find(m => m.type === 'human')
    expect(humanMsg?.sendStatus).toBe('sent')
  })

  it('strips [SKILL:chat] wrapper and recovers free_text on loadHistory', async () => {
    const skillWrapper = '[SKILL:chat]\n' + JSON.stringify({
      family_id: 'fam-1',
      free_text: '用户原始输入',
    }, null, 2)
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: vi.fn(), cancel: vi.fn() },
      threads: {
        getState: vi.fn().mockResolvedValue({
          values: {
            messages: [
              { id: 'human-1', type: 'human', content: skillWrapper },
              { id: 'ai-1', type: 'ai', content: 'AI 回复' },
            ],
          },
        }),
      },
    } as never)

    const chat = useThreadChat()
    await chat.loadHistory('thread-1')

    const humanMsg = chat.messages.value.find(m => m.type === 'human')
    expect(humanMsg?.content).toBe('用户原始输入')
    expect(humanMsg?.content).not.toContain('[SKILL:')
  })

  it('marks ALL AI messages done on end (not just the last) so streaming indicators stop', async () => {
    // A single turn can emit multiple AI messages: a tool-call message then a
    // text-reply message (or a summarization-leak message then the real reply).
    // The end handler must mark every AI message 'done', not just the last -
    // otherwise earlier ones stay phase='answering' and their StreamingIndicator
    // (three-dot animation) never stops. This also breaks the next turn's
    // hasPriorProgress check, leaving the follow-up user bubble on "发送中".
    const mockStream = makeMockStream([
      { event: 'metadata', data: { run_id: 'run-1' } },
      { event: 'messages', data: { type: 'ai', id: 'ai-toolcall', content: '', tool_calls: [{ id: 'tc-1', name: 'search', args: {} }] } },
      { event: 'messages', data: { type: 'ai', id: 'ai-reply', content: 'Final answer' } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    const aiMessages = chat.messages.value.filter(m => m.type === 'ai')
    expect(aiMessages).toHaveLength(2)
    // Both AI messages must be 'done', not just the last - otherwise the
    // three-dot StreamingIndicator stays visible on the earlier one forever.
    expect(aiMessages[0].phase).toBe('done')
    expect(aiMessages[1].phase).toBe('done')
  })

  it('follow-up sendStatus is sent even when a prior turn had multiple AI messages', async () => {
    // Regression: after a turn that left a non-last AI message at phase='answering',
    // the next sendMessage's hasPriorProgress check returned true (because it
    // scans for any AI message with phase='answering'), so setUserMsgStatus was
    // skipped and the follow-up user bubble stayed on "发送中".
    const chat = useThreadChat()

    // Turn 1: multiple AI messages, all should be marked done by end
    const mockStream1 = makeMockStream([
      { event: 'metadata', data: { run_id: 'run-1' } },
      { event: 'messages', data: { type: 'ai', id: 'ai-toolcall', content: '', tool_calls: [{ id: 'tc-1', name: 'search', args: {} }] } },
      { event: 'messages', data: { type: 'ai', id: 'ai-reply', content: 'Answer 1' } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream1, cancel: vi.fn() },
    } as never)
    await chat.sendMessage('first', undefined, 'thread-1')

    // Turn 2: follow-up on the same thread
    const mockStream2 = makeMockStream([
      { event: 'metadata', data: { run_id: 'run-2' } },
      { event: 'messages', data: { type: 'ai', id: 'ai-reply-2', content: 'Answer 2' } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream2, cancel: vi.fn() },
    } as never)
    await chat.sendMessage('second', undefined, 'thread-1')

    // The follow-up user message must transition to 'sent', not stay 'sending'
    const humanMessages = chat.messages.value.filter(m => m.type === 'human')
    expect(humanMessages).toHaveLength(2)
    expect(humanMessages[1].sendStatus).toBe('sent')
  })
})
