/**
 * Tests for the chat SSE reconnection path (Last-Event-ID).
 *
 * Covers the two layers involved:
 * - `readSSEStream` surfacing SSE `id:` fields via `onEventId`
 * - `streamChatRun` sending `Last-Event-ID` and yielding SDK-shaped frames
 *
 * The reconnect contract: the client remembers the last SSE id it saw and
 * sends it back as `Last-Event-ID` on the next attempt, so the backend
 * replays buffered events the client missed during the disconnect.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readSSEStream } from '@numina/shared'
import { streamChatRun } from '../ai-chat'
import type { ChatStreamChunk } from '../ai-chat'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// streamChatRun reads the family id from the stores; stub both so the
// request-building path runs without a Pinia instance.
vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({ family: { id: 'family-1' } }),
}))
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { family_id: 'family-1' } }),
}))

function makeSSEResponse(chunks: string[]): Response {
  let chunkIndex = 0
  const encoder = new TextEncoder()

  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (chunkIndex < chunks.length) {
        controller.enqueue(encoder.encode(chunks[chunkIndex]))
        chunkIndex++
      } else {
        controller.close()
      }
    },
  })

  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

/** Format one frame exactly as the backend's format_sse emits it. */
function frame(event: string, data: unknown, id?: string): string {
  const lines = [`event: ${event}`, `data: ${JSON.stringify(data)}`]
  if (id) lines.push(`id: ${id}`)
  lines.push('', '')
  return lines.join('\n')
}

/**
 * Build a response from complete frames. The reader splits on '\n' and keeps
 * the trailing partial line in its buffer, so every line must be terminated —
 * frames are joined and a final newline appended.
 */
function framesResponse(frames: string[]): Response {
  return makeSSEResponse([frames.join('\n') + '\n'])
}

describe('readSSEStream — SSE id capture', () => {
  it('surfaces the id field of each frame', async () => {
    const ids: string[] = []
    const response = framesResponse([frame('messages-tuple', { type: 'ai', content: 'hi' }, '1'),
      frame('messages-tuple', { type: 'ai', content: ' there' }, '2'),
      frame('end', { status: 'success' }, '3'),
    ])

    await readSSEStream(response, {
      onMessage: () => {},
      onCustom: () => {},
      onError: () => {},
      onEnd: () => {},
      onEventId: id => ids.push(id),
    })

    expect(ids).toEqual(['1', '2', '3'])
  })

  it('ignores frames without an id', async () => {
    const ids: string[] = []
    const response = framesResponse([frame('messages-tuple', { type: 'ai', content: 'a' }),
      frame('messages-tuple', { type: 'ai', content: 'b' }, '7'),
    ])

    await readSSEStream(response, {
      onMessage: () => {},
      onCustom: () => {},
      onError: () => {},
      onEnd: () => {},
      onEventId: id => ids.push(id),
    })

    expect(ids).toEqual(['7'])
  })

  it('dispatches messages-tuple frames to onMessage', async () => {
    const messages: Array<{ event: string; data: unknown }> = []
    const response = framesResponse([frame('messages-tuple', { type: 'ai', content: 'hello' }, '1'),
    ])

    await readSSEStream(response, {
      onMessage: (event, data) => messages.push({ event, data }),
      onCustom: () => {},
      onError: () => {},
      onEnd: () => {},
    })

    expect(messages).toHaveLength(1)
    expect(messages[0].event).toBe('messages-tuple')
    expect(messages[0].data).toEqual({ type: 'ai', content: 'hello' })
  })

  it('still dispatches every other frame type unchanged', async () => {
    const seen: string[] = []
    const response = framesResponse([frame('metadata', { run_id: 'run-1' }, '1'),
      frame('messages-tuple', { type: 'ai', content: 'x' }, '2'),
      frame('custom', { type: 'tool_call' }, '3'),
      frame('gap', { checkpoint_id: 'ck-1' }, '4'),
      frame('end', { status: 'success' }, '5'),
    ])

    await readSSEStream(response, {
      onMessage: (event) => seen.push(event),
      onCustom: () => seen.push('custom'),
      onError: () => seen.push('error'),
      onMetadata: () => seen.push('metadata'),
      onGap: () => seen.push('gap'),
      onEnd: () => seen.push('end'),
    })

    expect(seen).toEqual([
      'metadata',
      'messages-tuple',
      'custom',
      'gap',
      'end',
    ])
  })
})

describe('streamChatRun — request and frame mapping', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  async function collect(
    chunks: string[],
    options: { lastEventId?: string } = {},
  ): Promise<{ frames: ChatStreamChunk[]; ids: string[] }> {
    mockFetch.mockResolvedValue(makeSSEResponse(chunks))
    const frames: ChatStreamChunk[] = []
    const ids: string[] = []
    for await (const chunk of streamChatRun({
      threadId: 'thread-1',
      input: null,
      streamMode: ['messages-tuple', 'values', 'custom'],
      lastEventId: options.lastEventId,
      onEventId: id => ids.push(id),
    })) {
      frames.push(chunk)
    }
    return { frames, ids }
  }

  it('yields frames in the shape the chat composable consumes', async () => {
    const { frames } = await collect([
      ...frame('metadata', { run_id: 'run-1' }, '1'),
      ...frame('messages-tuple', { type: 'ai', content: 'hello' }, '2'),
      ...frame('end', { status: 'success' }, '3'),
    ])

    expect(frames.map(f => f.event)).toEqual(['metadata', 'messages-tuple', 'end'])
    expect(frames[1].data).toEqual({ type: 'ai', content: 'hello' })
  })

  it('sends Last-Event-ID on reconnect', async () => {
    await collect([...frame('end', { status: 'success' }, '9')], { lastEventId: '42' })

    const [, init] = mockFetch.mock.calls[0]
    expect(init.headers['Last-Event-ID']).toBe('42')
  })

  it('omits Last-Event-ID on the first attempt', async () => {
    await collect([...frame('end', { status: 'success' }, '1')])

    const [, init] = mockFetch.mock.calls[0]
    expect(init.headers['Last-Event-ID']).toBeUndefined()
  })

  it('posts to the run stream endpoint with credentials and family header', async () => {
    await collect([...frame('end', { status: 'success' }, '1')])

    const [url, init] = mockFetch.mock.calls[0]
    expect(url).toContain('/api/threads/thread-1/runs/stream')
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('include')
    expect(init.headers['X-Family-Id']).toBe('family-1')
  })

  it('forwards configurable overrides as config.configurable', async () => {
    mockFetch.mockResolvedValue(framesResponse([frame('end', { status: 'success' }, '1')]))
    for await (const _ of streamChatRun({
      threadId: 'thread-1',
      input: { messages: [] },
      streamMode: ['values'],
      configurable: { thinking_enabled: true },
    })) {
      void _
    }

    const [, init] = mockFetch.mock.calls[0]
    expect(JSON.parse(init.body).config).toEqual({ configurable: { thinking_enabled: true } })
  })

  it('surfaces a request failure as a thrown error so the caller retries', async () => {
    mockFetch.mockResolvedValue(new Response('nope', { status: 500 }))

    const run = async () => {
      for await (const _ of streamChatRun({
        threadId: 'thread-1',
        input: null,
        streamMode: ['values'],
      })) {
        void _
      }
    }
    await expect(run()).rejects.toThrow('stream.request_failed:500')
  })
})

describe('chat reconnection — no message loss across a disconnect', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('replays from the last seen id and keeps every frame', async () => {
    // Attempt 1: frames 1-2 arrive, then the connection drops mid-stream
    // (no `end` frame — the reader just closes).
    mockFetch.mockResolvedValueOnce(
      framesResponse([frame('messages-tuple', { type: 'ai', content: 'part one ' }, '1'),
        frame('messages-tuple', { type: 'ai', content: 'part two ' }, '2'),
      ]),
    )

    let lastEventId = ''
    const attempt1: ChatStreamChunk[] = []
    for await (const chunk of streamChatRun({
      threadId: 'thread-1',
      input: { messages: [] },
      streamMode: ['messages-tuple'],
      onEventId: id => { lastEventId = id },
    })) {
      attempt1.push(chunk)
    }

    // The client remembered the last id it actually saw.
    expect(lastEventId).toBe('2')

    // Attempt 2: reconnect with Last-Event-ID; backend replays 3+.
    mockFetch.mockResolvedValueOnce(
      framesResponse([frame('messages-tuple', { type: 'ai', content: 'part three' }, '3'),
        frame('end', { status: 'success' }, '4'),
      ]),
    )

    const attempt2: ChatStreamChunk[] = []
    for await (const chunk of streamChatRun({
      threadId: 'thread-1',
      input: null,
      streamMode: ['messages-tuple'],
      lastEventId: lastEventId || undefined,
      onEventId: id => { lastEventId = id },
    })) {
      attempt2.push(chunk)
    }

    // Reconnect carried the resume cursor.
    const [, reconnectInit] = mockFetch.mock.calls[1]
    expect(reconnectInit.headers['Last-Event-ID']).toBe('2')

    // Nothing was lost: both attempts' frames are present and in order.
    const all = [...attempt1, ...attempt2]
    const text = all
      .filter(f => f.event === 'messages-tuple')
      .map(f => (f.data as { content: string }).content)
      .join('')
    expect(text).toBe('part one part two part three')

    // The reconnect resumed from the checkpoint, not by re-sending the message.
    expect(JSON.parse(reconnectInit.body).input).toBeNull()
    expect(lastEventId).toBe('4')
  })
})
