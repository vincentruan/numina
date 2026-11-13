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
})
