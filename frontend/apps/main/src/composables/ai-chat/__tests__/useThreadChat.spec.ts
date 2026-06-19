import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock the API client
const mockStream = vi.fn()
const mockClient = { runs: { stream: mockStream } }
vi.mock('@/api/ai-chat', () => ({
  getClient: () => mockClient,
  createThread: vi.fn().mockResolvedValue({ thread_id: 't1' }),
}))

describe('useThreadChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default stream mock — returns a simple async iterable
    mockStream.mockImplementation(function* () {
      yield { event: 'messages', data: [{ type: 'ai', content: 'Hello' }] }
    })
  })

  it('sendMessage creates thread and streams response', async () => {
    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    expect(chat.messages.value).toEqual([])
    expect(chat.isLoading.value).toBe(false)
    expect(chat.error.value).toBeNull()

    const promise = chat.sendMessage('Hi')
    // After calling sendMessage, isLoading should be true and optimistic message added
    expect(chat.isLoading.value).toBe(true)
    expect(chat.messages.value.length).toBeGreaterThanOrEqual(1)
    expect(chat.messages.value[0].content).toBe('Hi')

    await promise
    expect(chat.isLoading.value).toBe(false)
    expect(chat.messages.value.length).toBeGreaterThanOrEqual(2)
  })

  it('cancelStream stops loading', async () => {
    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    // Start a stream that never resolves
    mockStream.mockReturnValue(new Promise(() => {}))
    chat.sendMessage('Hi').catch(() => {})

    expect(chat.isLoading.value).toBe(true)
    chat.cancelStream()
    expect(chat.isLoading.value).toBe(false)
  })

  it('loadHistory fetches and merges messages', async () => {
    mockStream.mockImplementation(function* () {
      yield { event: 'values', data: { messages: [
        { type: 'human', content: 'Hi' },
        { type: 'ai', content: 'Hello' },
      ]}}
    })
    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()
    await chat.loadHistory('t1')
    expect(chat.messages.value.length).toBeGreaterThanOrEqual(2)
  })

  it('retry re-sends the last user message', async () => {
    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()
    const promise = chat.sendMessage('Hello')
    await promise
    expect(chat.isLoading.value).toBe(false)

    const prevCount = chat.messages.value.length
    chat.retry().catch(() => {})
    expect(chat.isLoading.value).toBe(true)
    expect(chat.messages.value.length).toBeLessThanOrEqual(prevCount)
  })
})
