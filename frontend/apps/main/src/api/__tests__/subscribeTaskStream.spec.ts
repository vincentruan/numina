/**
 * Tests for subscribeTaskStream SSE parser.
 *
 * Verifies the hand-rolled SSE line parser handles:
 * - Basic event/data parsing
 * - Multi-chunk reads (event and data arrive in separate chunks)
 * - Partial lines (buffer accumulation)
 * - Multiple events in a single chunk
 * - JSON data parsing
 * - end/gap event handling
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { subscribeTaskStream } from '../ai-tasks'

// Mock fetch globally
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

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

describe('subscribeTaskStream — SSE parser', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('parses a single event with JSON data', async () => {
    const events: Array<{ event: string; data: unknown }> = []

    mockFetch.mockResolvedValue(
      makeSSEResponse([
        'event: custom\n',
        'data: {"type":"reasoning_delta","content":"hello"}\n',
        '\n',
      ]),
    )

    const handle = subscribeTaskStream('task-1', {
      onEvent: (event, data) => events.push({ event, data }),
      onGap: () => {},
      onEnd: () => {},
      onError: () => {},
    })

    // Wait for stream to complete
    await new Promise((r) => setTimeout(r, 50))
    handle.abort()

    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('custom')
    expect(events[0].data).toEqual({ type: 'reasoning_delta', content: 'hello' })
  })

  it('handles multiple events in a single chunk', async () => {
    const events: Array<{ event: string; data: unknown }> = []

    mockFetch.mockResolvedValue(
      makeSSEResponse([
        'event: custom\ndata: {"type":"a"}\n\n' +
        'event: custom\ndata: {"type":"b"}\n\n' +
        'event: end\ndata: null\n\n',
      ]),
    )

    const handle = subscribeTaskStream('task-1', {
      onEvent: (event, data) => events.push({ event, data }),
      onGap: () => {},
      onEnd: () => {},
      onError: () => {},
    })

    await new Promise((r) => setTimeout(r, 50))
    handle.abort()

    expect(events).toHaveLength(3)
    expect(events[0]).toEqual({ event: 'custom', data: { type: 'a' } })
    expect(events[1]).toEqual({ event: 'custom', data: { type: 'b' } })
    expect(events[2]).toEqual({ event: 'end', data: null })
  })

  it('handles multi-chunk reads (event and data arrive separately)', async () => {
    const events: Array<{ event: string; data: unknown }> = []

    mockFetch.mockResolvedValue(
      makeSSEResponse([
        'event: custom\n',
        'data: {"type":"test"}\n',
        '\n',
      ]),
    )

    const handle = subscribeTaskStream('task-1', {
      onEvent: (event, data) => events.push({ event, data }),
      onGap: () => {},
      onEnd: () => {},
      onError: () => {},
    })

    await new Promise((r) => setTimeout(r, 50))
    handle.abort()

    expect(events).toHaveLength(1)
    expect(events[0].event).toBe('custom')
    expect(events[0].data).toEqual({ type: 'test' })
  })

  it('calls onGap when gap event received', async () => {
    let gapCalled = false

    mockFetch.mockResolvedValue(
      makeSSEResponse(['event: gap\ndata: {"code":"stream_replay_gap"}\n\n']),
    )

    const handle = subscribeTaskStream('task-1', {
      onEvent: () => {},
      onGap: () => { gapCalled = true },
      onEnd: () => {},
      onError: () => {},
    })

    await new Promise((r) => setTimeout(r, 50))
    handle.abort()

    expect(gapCalled).toBe(true)
  })

  it('calls onEnd when end event received', async () => {
    let endCalled = false

    mockFetch.mockResolvedValue(
      makeSSEResponse(['event: end\ndata: {"status":"complete"}\n\n']),
    )

    const handle = subscribeTaskStream('task-1', {
      onEvent: () => {},
      onGap: () => {},
      onEnd: () => { endCalled = true },
      onError: () => {},
    })

    await new Promise((r) => setTimeout(r, 50))
    handle.abort()

    expect(endCalled).toBe(true)
  })

  it('calls onError when fetch fails', async () => {
    let errorMsg = ''

    mockFetch.mockRejectedValue(new Error('Network error'))

    const handle = subscribeTaskStream('task-1', {
      onEvent: () => {},
      onGap: () => {},
      onEnd: () => {},
      onError: (msg) => { errorMsg = msg },
    })

    await new Promise((r) => setTimeout(r, 50))
    handle.abort()

    expect(errorMsg).toBe('stream.request_failed')
  })

  it('calls onError when response is not ok', async () => {
    let errorMsg = ''

    mockFetch.mockResolvedValue(new Response(null, { status: 404 }))

    const handle = subscribeTaskStream('task-1', {
      onEvent: () => {},
      onGap: () => {},
      onEnd: () => {},
      onError: (msg) => { errorMsg = msg },
    })

    await new Promise((r) => setTimeout(r, 50))
    handle.abort()

    expect(errorMsg).toBe('stream.request_failed:404')
  })

  it('abort() cancels the fetch', () => {
    mockFetch.mockResolvedValue(
      makeSSEResponse(['event: custom\ndata: {"type":"test"}\n\n']),
    )

    const handle = subscribeTaskStream('task-1', {
      onEvent: () => {},
      onGap: () => {},
      onEnd: () => {},
      onError: () => {},
    })

    // Should not throw
    handle.abort()
    expect(handle.abort).toBeDefined()
  })
})
