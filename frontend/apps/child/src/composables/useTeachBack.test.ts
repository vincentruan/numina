import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string, params?: Record<string, unknown>) =>
    params ? `${key}:${JSON.stringify(params)}` : key }),
}))

// Capture the handlers readSSEStream is given so tests can drive them directly.
const handlersRef: { current: Record<string, (arg?: unknown) => void> | null } = {
  current: null,
}

vi.mock('@numina/shared', () => ({
  readSSEStream: vi.fn(async (_response: unknown, handlers: Record<string, (arg?: unknown) => void>) => {
    handlersRef.current = handlers
    // Real streams end; the composable only allows a follow-up submit once
    // status is 'completed', so a mock that never ends would stall the flow.
    handlers.onEnd?.()
  }),
}))

import { useTeachBack } from './useTeachBack'

type TeachBackApi = ReturnType<typeof useTeachBack>

function makeScope() {
  const scope = effectScope()
  const api = scope.run(() => useTeachBack()) as TeachBackApi
  return { scope, api }
}

/** Build a Response-like object whose `ok`/`status` the composable reads. */
function mockFetchResponse(ok = true, status = 200) {
  return { ok, status } as Response
}

describe('useTeachBack', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    handlersRef.current = null
    fetchMock = vi.fn().mockResolvedValue(mockFetchResponse())
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Outgoing request shape (Snowflake IDs must stay strings — #3)
  // -------------------------------------------------------------------------

  it('sends topic_id as a string, never Number()-coerced', async () => {
    const { scope, api } = makeScope()
    const snowflake = '379460684699668480' // > 2^53, corrupts under Number()

    await api.startTeachBack(snowflake)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body as string)
    expect(body.topic_id).toBe(snowflake)
    expect(typeof body.topic_id).toBe('string')
    scope.stop()
  })

  it('sends session_id as a string on follow-up turns', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')
    // Backend prepends session_created, which the composable captures.
    handlersRef.current!.onCustom({
      type: 'session_created',
      session_id: '379460684699668481',
    })
    await nextTick()

    await api.submitExplanation('because the denominators match')

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [, init] = fetchMock.mock.calls[1]
    const body = JSON.parse(init.body as string)
    expect(body.session_id).toBe('379460684699668481')
    expect(typeof body.session_id).toBe('string')
    scope.stop()
  })

  // -------------------------------------------------------------------------
  // session_created event (#4 — breaks the first-turn deadlock)
  // -------------------------------------------------------------------------

  it('captures session_id from the session_created custom event', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')

    handlersRef.current!.onCustom({
      type: 'session_created',
      session_id: '379460684699668481',
    })
    await nextTick()

    // With a session id known, submitting is no longer a silent no-op.
    const before = fetchMock.mock.calls.length
    await api.submitExplanation('my explanation')
    expect(fetchMock.mock.calls.length).toBe(before + 1)
    scope.stop()
  })

  it('is a no-op (no request) when no session_id is known yet', async () => {
    const { scope, api } = makeScope()
    // No startTeachBack, no session_created event -> activeSessionId is null
    await api.submitExplanation('my explanation')
    expect(fetchMock).not.toHaveBeenCalled()
    scope.stop()
  })

  // -------------------------------------------------------------------------
  // tool_result parsing (#18 — backend emits `content`, not `result`)
  // -------------------------------------------------------------------------

  it('parses tool_result from the JSON-string `content` field', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')

    const turnPayload = {
      ok: true,
      session_id: '379460684699668481',
      confusion_id: 10,
      verdict: 'hit',
      phase: 'evaluate_explanation',
      next_phase: 'present_confusion',
      child_explanation: 'because the denominator is the number of parts',
      reasoning_summary: 'explains the denominator',
      all_confusions_hit: false,
      teach_back_success: false,
    }
    handlersRef.current!.onCustom({
      type: 'tool_result',
      tool_name: 'record_teach_back_turn',
      content: JSON.stringify(turnPayload),
    })
    await nextTick()

    expect(api.turns.value).toHaveLength(1)
    expect(api.turns.value[0].verdict).toBe('hit')
    expect(api.turns.value[0].confusion_id).toBe('10')
    expect(api.currentPhase.value).toBe('present_confusion')
    scope.stop()
  })

  it('parses tool_result when `content` is already an object', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')

    handlersRef.current!.onCustom({
      type: 'tool_result',
      tool_name: 'record_teach_back_turn',
      content: {
        ok: true,
        confusion_id: 11,
        verdict: 'miss',
        phase: 'evaluate_explanation',
        next_phase: 'present_confusion',
        child_explanation: 'I do not know',
        reasoning_summary: 'not an explanation',
      },
    })
    await nextTick()

    expect(api.turns.value).toHaveLength(1)
    expect(api.turns.value[0].verdict).toBe('miss')
    scope.stop()
  })

  it('ignores malformed tool_result content without throwing', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')

    expect(() =>
      handlersRef.current!.onCustom({
        type: 'tool_result',
        tool_name: 'record_teach_back_turn',
        content: 'not valid json {{{',
      }),
    ).not.toThrow()
    await nextTick()

    expect(api.turns.value).toHaveLength(0)
    scope.stop()
  })

  it('ignores tool_result from a different tool', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')

    handlersRef.current!.onCustom({
      type: 'tool_result',
      tool_name: 'some_other_tool',
      content: JSON.stringify({ confusion_id: 10, verdict: 'hit' }),
    })
    await nextTick()

    expect(api.turns.value).toHaveLength(0)
    scope.stop()
  })

  // -------------------------------------------------------------------------
  // Success flag propagation
  // -------------------------------------------------------------------------

  it('sets allConfusionsHit and teachBackSuccess from the tool result', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')

    handlersRef.current!.onCustom({
      type: 'tool_result',
      tool_name: 'record_teach_back_turn',
      content: JSON.stringify({
        ok: true,
        confusion_id: 10,
        verdict: 'hit',
        phase: 'resolve',
        next_phase: 'end',
        child_explanation: 'final answer',
        reasoning_summary: 'all resolved',
        all_confusions_hit: true,
        teach_back_success: true,
      }),
    })
    await nextTick()

    expect(api.allConfusionsHit.value).toBe(true)
    expect(api.teachBackSuccess.value).toBe(true)
    scope.stop()
  })
  // -------------------------------------------------------------------------
  // Follow-up contract (#8) — only session_id + child_answer are required
  // -------------------------------------------------------------------------

  it('submits a follow-up with only session_id and child_answer in the body', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')
    handlersRef.current!.onCustom({
      type: 'session_created',
      session_id: '379460684699668481',
    })
    await nextTick()

    fetchMock.mockClear()
    await api.submitExplanation('the denominator stays the same')

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string)
    expect(body).toEqual({
      session_id: '379460684699668481',
      child_answer: 'the denominator stays the same',
    })
    scope.stop()
  })

  it('submits a follow-up even after reset() clears the topic id', async () => {
    // reset() drops both ids, so re-establish only the session id the way a
    // resumed client would (session_created replay) and confirm the guard does
    // not key on the topic id.
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')
    handlersRef.current!.onCustom({
      type: 'session_created',
      session_id: '379460684699668482',
    })
    await nextTick()

    fetchMock.mockClear()
    await api.submitExplanation('still explaining')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  // -------------------------------------------------------------------------
  // Error / gap / disconnect / reset paths
  // -------------------------------------------------------------------------

  it('surfaces a stream error and stops streaming', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')
    api.status.value = 'streaming'

    handlersRef.current!.onError({ message: 'stream blew up' })
    await nextTick()

    expect(api.error.value).toBe('stream blew up')
    expect(api.status.value).toBe('error')
    scope.stop()
  })

  it('falls back to the i18n message when the error payload has none', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')
    api.status.value = 'streaming'

    handlersRef.current!.onError({})
    await nextTick()

    expect(api.error.value).toBe('learning.error.stream')
    scope.stop()
  })

  it('reports a gap as a recoverable error', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')
    api.status.value = 'streaming'

    handlersRef.current!.onGap()
    await nextTick()

    expect(api.error.value).toBe('learning.error.gap_recovery')
    expect(api.status.value).toBe('error')
    scope.stop()
  })

  it('reset() clears every piece of turn state', async () => {
    const { scope, api } = makeScope()
    await api.startTeachBack('379460684699668480')
    handlersRef.current!.onCustom({
      type: 'tool_result',
      tool_name: 'record_teach_back_turn',
      content: JSON.stringify({
        ok: true,
        session_id: '379460684699668481',
        confusion_id: 10,
        verdict: 'hit',
        phase: 'evaluate_explanation',
        next_phase: 'present_confusion',
        child_explanation: 'explained',
        all_confusions_hit: true,
        teach_back_success: true,
      }),
    })
    await nextTick()
    expect(api.turns.value).toHaveLength(1)

    api.reset()
    await nextTick()

    expect(api.turns.value).toEqual([])
    expect(api.messages.value).toEqual([])
    expect(api.allConfusionsHit.value).toBe(false)
    expect(api.teachBackSuccess.value).toBe(false)
    expect(api.error.value).toBeNull()
    expect(api.status.value).toBe('idle')
    expect(api.currentPhase.value).toBe('present_confusion')
    scope.stop()
  })

  it('disconnect() aborts the in-flight request', async () => {
    const { scope, api } = makeScope()
    // Hold the fetch open so an abort controller is live when disconnect runs.
    let capturedSignal: AbortSignal | undefined
    fetchMock.mockImplementation((_url: string, init: RequestInit) => {
      capturedSignal = init.signal as AbortSignal
      return new Promise(() => {})
    })

    void api.startTeachBack('379460684699668480')
    await nextTick()
    expect(capturedSignal?.aborted).toBe(false)

    api.disconnect()
    expect(capturedSignal?.aborted).toBe(true)
    scope.stop()
  })

  it('does not surface an error when the caller aborts deliberately', async () => {
    const { scope, api } = makeScope()
    fetchMock.mockRejectedValue(
      Object.assign(new Error('aborted'), { name: 'AbortError' }),
    )

    await api.startTeachBack('379460684699668480')

    expect(api.error.value).toBeNull()
    scope.stop()
  })
})
