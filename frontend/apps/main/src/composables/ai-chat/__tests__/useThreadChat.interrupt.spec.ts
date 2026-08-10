import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock vue-i18n before importing the composable
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }),
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
  compactThread: vi.fn(),
}))

// Mock the sessions API module (used by feedback hydration/submit)
vi.mock('@/api/sessions', () => ({
  submitMessageFeedback: vi.fn(),
  getSessionFeedback: vi.fn().mockResolvedValue({ data: { items: {} } }),
}))

/**
 * DeerFlow ClarificationMiddleware sends ask_clarification as a ToolMessage
 * with artifact.human_input (NOT a custom event with type=interrupt). The
 * adapter preserves the artifact field (sync_tool_patch), so the frontend
 * extracts human_input from the messages-tuple tool chunk into
 * additional_kwargs.interruptData for HumanInputCard rendering.
 */
describe('useThreadChat - clarification artifact extraction', () => {
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
    } as unknown as ReturnType<typeof getClient>)

    const { useThreadChat } = await import('../useThreadChat')
    const chat = useThreadChat()

    await chat.sendMessage('hello', undefined, 'thread-1')
    return chat
  }

  it('extracts human_input from a messages-tuple tool chunk with artifact', async () => {
    const chat = await runWithChunks([
      {
        event: 'messages-tuple',
        data: {
          type: 'tool',
          name: 'ask_clarification',
          content: 'Which category?',
          tool_call_id: 'call-abc',
          artifact: {
            human_input: {
              version: 1,
              kind: 'human_input_request',
              source: 'ask_clarification',
              request_id: 'req-123',
              question: 'Which category?',
              input_mode: 'choice_with_other',
              context: 'Need clarification',
              options: [{ id: 'stock', label: '股票', value: 'stock' }],
            },
          },
        },
      },
      { event: 'end', data: { status: 'success' } },
    ])

    const clarificationMsgs = chat.messages.value.filter(
      m => m.name === 'ask_clarification',
    )
    expect(clarificationMsgs).toHaveLength(1)

    const msg = clarificationMsgs[0]
    expect(msg.type).toBe('tool')
    expect(msg.role).toBe('assistant')
    expect(msg.content).toBe('Which category?')
    expect(msg.tool_call_id).toBe('call-abc')
    expect(msg.additional_kwargs?.interruptData).toEqual({
      question: 'Which category?',
      options: [{ id: 'stock', label: '股票', value: 'stock' }],
      context: 'Need clarification',
      choiceWithOther: true,
      input_mode: 'choice_with_other',
      interrupt_id: 'req-123',
      source: 'ask_clarification',
    })
  })

  it('handles free_text input_mode (no options) gracefully', async () => {
    const chat = await runWithChunks([
      {
        event: 'messages-tuple',
        data: {
          type: 'tool',
          name: 'ask_clarification',
          content: 'Please confirm',
          tool_call_id: 'call-def',
          artifact: {
            human_input: {
              version: 1,
              kind: 'human_input_request',
              source: 'ask_clarification',
              request_id: 'req-456',
              question: 'Please confirm',
              input_mode: 'free_text',
            },
          },
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
    const interruptData = msg.additional_kwargs?.interruptData as Record<string, unknown>
    expect(interruptData.interrupt_id).toBe('req-456')
    expect(interruptData.input_mode).toBe('free_text')
    expect(interruptData.choiceWithOther).toBe(false)
    // options and context should be undefined when not provided
    expect(interruptData.options).toBeUndefined()
    expect(interruptData.context).toBeUndefined()
  })

  it('does not attach interruptData when artifact is absent (non-clarification tool)', async () => {
    const chat = await runWithChunks([
      {
        event: 'messages-tuple',
        data: {
          type: 'tool',
          name: 'getAssetsData',
          content: '{"assets":[]}',
          tool_call_id: 'call-xyz',
        },
      },
      { event: 'end', data: { status: 'success' } },
    ])

    // No clarification message
    const clarificationMsgs = chat.messages.value.filter(
      m => m.name === 'ask_clarification',
    )
    expect(clarificationMsgs).toHaveLength(0)

    // The regular tool message should NOT have interruptData
    const toolMsgs = chat.messages.value.filter(m => m.type === 'tool')
    for (const msg of toolMsgs) {
      expect(msg.additional_kwargs?.interruptData).toBeUndefined()
    }
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
    const lastAiMsg = [...chat.messages.value].reverse().find(m => m.type === 'ai')
    expect(lastAiMsg?.suggestions).toEqual(['opt1', 'opt2'])

    // No clarification message
    const clarificationMsgs = chat.messages.value.filter(
      m => m.name === 'ask_clarification',
    )
    expect(clarificationMsgs).toHaveLength(0)
  })
})
