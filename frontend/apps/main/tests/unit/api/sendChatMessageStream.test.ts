/**
 * ADV-001 regression test (post-fix).
 *
 * Pins the contract that `sendChatMessageStream` actually puts `agent_id` in
 * the POST body when given an `agentId` argument. Before this fix the
 * function signature didn't even accept `agentId` — every chat dispatch hit
 * the legacy /chat/ask path with no skill resolution, regardless of which
 * agent the recipient chip selected. The agent-dispatch path (which runs
 * _resolve_skills) is only reached via this wire-format.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { sendChatMessageStream } from '@/api/ai'

describe('sendChatMessageStream — ADV-001 contract', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    // Stub fetch with a minimal streamable response.
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream({
        start(controller) {
          controller.close()
        },
      }),
    })
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('includes agent_id in the POST body when agentId is provided', async () => {
    await sendChatMessageStream(
      'hello',
      false,
      false,
      undefined,
      'session-123',
      'numina-agent-id',
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body as string)
    expect(body.question).toBe('hello')
    expect(body.agent_id).toBe('numina-agent-id')
    expect(body.deep_think).toBe(false)
    // U2: web_search removed from payload (smart mode agents decide search behavior)
    expect(body.web_search).toBeUndefined()
  })

  it('omits agent_id from the POST body when agentId is not provided', async () => {
    await sendChatMessageStream('hello', false, false)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body as string)
    expect(body.question).toBe('hello')
    expect('agent_id' in body).toBe(false)
  })

  it('sends deep_think and reasoning_effort alongside agent_id for smart mode', async () => {
    await sendChatMessageStream(
      'analyze allocation',
      true,
      false,
      undefined,
      undefined,
      'custom-agent-id',
      'high',
    )
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body as string)
    expect(body.agent_id).toBe('custom-agent-id')
    expect(body.deep_think).toBe(true)
    expect(body.reasoning_effort).toBe('high')
    // U2: web_search removed from payload
    expect(body.web_search).toBeUndefined()
  })

  it('passes sessionId via X-Thread-Id header regardless of agentId', async () => {
    await sendChatMessageStream(
      'hello',
      false,
      false,
      undefined,
      'thread-456',
      'agent-789',
    )
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['X-Thread-Id']).toBe('thread-456')
  })
})
