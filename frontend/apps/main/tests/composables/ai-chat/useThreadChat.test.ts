import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'

// Mock dependencies
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/api/ai-chat', () => ({
  getClient: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
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
    expect(chat.planningSteps.value[0].icon).toBe('search')
    expect(chat.planningSteps.value[0].status).toBe('done') // marked done on end
  })

  it('parses custom suggestions event into suggestions ref', async () => {
    const mockStream = makeMockStream([
      { event: 'custom', data: { type: 'suggestions', suggestions: ['Q1', 'Q2', 'Q3'] } },
      { event: 'end', data: null },
    ])
    vi.mocked(getClient).mockReturnValue({
      runs: { stream: () => mockStream, cancel: vi.fn() },
    } as never)

    const chat = useThreadChat()
    await chat.sendMessage('hello', undefined, 'thread-1')

    expect(chat.suggestions.value).toEqual(['Q1', 'Q2', 'Q3'])
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
})
