import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock vue-i18n before importing the composable
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

// Mock subtask composable
vi.mock('../useSubtasks', () => ({
  useUpdateSubtask: () => ({
    handleTaskEvent: vi.fn(),
  }),
}))

// Mock the API module
vi.mock('@/api/ai-chat', () => ({
  getClient: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
}))

describe('useThreadChat — interrupt SSE event handling', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  /**
   * Helper: build a fake SSE stream (AsyncIterable<StreamChunk>) and feed it
   * through the composable's sendMessage path. We mock getClient().runs.stream
   * to yield the supplied chunks, then inspect messages after the stream ends.
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
    } as any)

    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    await chat.sendMessage('hello', undefined, 'thread-1')
    return chat
  }

  it('creates a clarification message on interrupt custom event', async () => {
    const chat = await runWithChunks([
      {
        event: 'custom',
        data: {
          type: 'interrupt',
          question: 'Which category?',
          options: [{ label: '股票', value: 'stock' }],
          context: 'Need clarification',
          interrupt_id: 'interrupt-123',
        },
      },
      { event: 'end', data: { status: 'success' } },
    ])

    // The user message is optimistic + set to 'sent'; the interrupt creates
    // a tool message. We expect at least the clarification message.
    const clarificationMsgs = chat.messages.value.filter(
      m => m.name === 'ask_clarification',
    )
    expect(clarificationMsgs).toHaveLength(1)

    const msg = clarificationMsgs[0]
    expect(msg.type).toBe('tool')
    expect(msg.role).toBe('assistant')
    expect(msg.content).toBe('Which category?')
    expect(msg.tool_call_id).toBe('interrupt-123')
    expect(msg.additional_kwargs?.interruptData).toEqual({
      question: 'Which category?',
      options: [{ label: '股票', value: 'stock' }],
      context: 'Need clarification',
      interrupt_id: 'interrupt-123',
    })
  })

  it('handles interrupt event without options gracefully', async () => {
    const chat = await runWithChunks([
      {
        event: 'custom',
        data: {
          type: 'interrupt',
          question: 'Please confirm',
          interrupt_id: 'intr-456',
        },
      },
      { event: 'end', data: { status: 'success' } },
    ])

    const clarificationMsgs = chat.messages.value.filter(
      m => m.name === 'ask_clarification',
    )
    expect(clarificationMsgs).toHaveLength(1)

    const msg = clarificationMsgs[0]
    expect(msg.content).toBe('Please confirm')
    expect(msg.additional_kwargs?.interruptData).toMatchObject({
      question: 'Please confirm',
      interrupt_id: 'intr-456',
    })
    // options and context should be undefined when not provided
    expect(msg.additional_kwargs?.interruptData.options).toBeUndefined()
    expect(msg.additional_kwargs?.interruptData.context).toBeUndefined()
  })

  it('generates interrupt_id when not provided by backend', async () => {
    const chat = await runWithChunks([
      {
        event: 'custom',
        data: {
          type: 'interrupt',
          question: 'Which one?',
        },
      },
      { event: 'end', data: { status: 'success' } },
    ])

    const clarificationMsgs = chat.messages.value.filter(
      m => m.name === 'ask_clarification',
    )
    expect(clarificationMsgs).toHaveLength(1)

    const data = clarificationMsgs[0].additional_kwargs?.interruptData as any
    expect(data.interrupt_id).toBeTruthy()
    expect(typeof data.interrupt_id).toBe('string')
  })

  it('does not interfere with other custom events', async () => {
    const chat = await runWithChunks([
      {
        event: 'custom',
        data: {
          type: 'tool_call',
          tool_call_id: 'tc-1',
          tool_name: 'search',
          args: '{}',
        },
      },
      {
        event: 'messages-tuple',
        data: {
          type: 'ai',
          content: 'Test response',
          id: 'msg-1',
        },
      },
      {
        event: 'custom',
        data: {
          type: 'suggestions',
          suggestions: ['opt1', 'opt2'],
        },
      },
      { event: 'end', data: { status: 'success' } },
    ])

    // Planning step should exist
    expect(chat.planningSteps.value).toHaveLength(1)
    expect(chat.planningSteps.value[0].toolName).toBe('search')

    // Suggestions should be attached to the last AI message (not standalone)
    // The code clears suggestions.value after attaching to the last AI message
    const lastAiMsg = [...chat.messages.value].reverse().find(m => m.type === 'ai')
    expect(lastAiMsg?.suggestions).toEqual(['opt1', 'opt2'])

    // No clarification message
    const clarificationMsgs = chat.messages.value.filter(
      m => m.name === 'ask_clarification',
    )
    expect(clarificationMsgs).toHaveLength(0)
  })
})
