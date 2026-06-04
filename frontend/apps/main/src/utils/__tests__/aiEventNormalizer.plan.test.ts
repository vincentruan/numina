import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  createNormalizationState,
  normalizeAgentEvent,
} from '@/utils/aiEventNormalizer'
import type { AgentEvent, NormalizationState } from '@/types/agent-stream'

// Helper to create a plan.update event
function makePlanUpdate(
  todos: Array<{ id: string; content: string; status: string }>,
): AgentEvent {
  return { type: 'plan.update', todos }
}

// Helper to create a tool.call event
function makeToolCall(id: string, name = 'web_search'): AgentEvent {
  return {
    type: 'tool.call',
    tool: {
      id,
      name,
      display_name: name,
      icon: '🔍',
      arguments: {},
    },
  }
}

// Helper to create a tool.progress event
function makeToolProgress(tool_id: string, progress_message: string): AgentEvent {
  return { type: 'tool.progress', tool_id, progress_message }
}

describe('createNormalizationState', () => {
  it('initializes new plan fields to empty/null', () => {
    const state = createNormalizationState()
    expect(state.planSteps).toEqual([])
    expect(state.lastPlanHash).toBe('')
    expect(state.planSource).toBeNull()
    expect(state.inferredSteps).toEqual([])
    expect(state.planWaitTimer).toBeNull()
  })
})

describe('session.start — 3s inference timer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('sets planWaitTimer on session.start', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    expect(state.planWaitTimer).not.toBeNull()
  })

  it('planWaitTimer is cleared (null) after 3s elapses', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    vi.advanceTimersByTime(3000)
    expect(state.planWaitTimer).toBeNull()
  })

  it('replaces previous timer if session.start fires twice', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    const first = state.planWaitTimer
    normalizeAgentEvent({ type: 'session.start' }, state)
    // Timer should be replaced (may or may not be same value, but must be set)
    expect(state.planWaitTimer).not.toBeNull()
    // First timer was cleared — advance 3s, only one fire expected
    const spy = vi.spyOn(globalThis, 'clearTimeout')
    vi.advanceTimersByTime(3000)
    expect(state.planWaitTimer).toBeNull()
    spy.mockRestore()
    void first // suppress unused warning
  })
})

describe('plan.update', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('sets planSource to explicit', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(makePlanUpdate([{ id: 'p0', content: 'Search', status: 'pending' }]), state)
    expect(state.planSource).toBe('explicit')
  })

  it('clears planWaitTimer on receipt', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    expect(state.planWaitTimer).not.toBeNull()

    normalizeAgentEvent(makePlanUpdate([{ id: 'p0', content: 'Search', status: 'pending' }]), state)
    expect(state.planWaitTimer).toBeNull()
  })

  it('emits plan_update event when hash changes', () => {
    const state = createNormalizationState()
    const emitted = normalizeAgentEvent(
      makePlanUpdate([{ id: 'p0', content: 'Search', status: 'pending' }]),
      state,
    )
    const planEvt = emitted.find((e) => e.type === 'plan_update')
    expect(planEvt).toBeDefined()
    expect(planEvt?.type === 'plan_update' && planEvt.steps).toHaveLength(1)
  })

  it('returns no plan_update event when hash is unchanged (duplicate)', () => {
    const state = createNormalizationState()
    const todos = [{ id: 'p0', content: 'Search', status: 'pending' }]
    normalizeAgentEvent(makePlanUpdate(todos), state)
    // Send identical plan again
    const second = normalizeAgentEvent(makePlanUpdate(todos), state)
    expect(second.find((e) => e.type === 'plan_update')).toBeUndefined()
  })

  it('updates planSteps with new steps', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      makePlanUpdate([
        { id: 'p0', content: 'Search', status: 'completed' },
        { id: 'p1', content: 'Analyze', status: 'in_progress' },
      ]),
      state,
    )
    expect(state.planSteps).toHaveLength(2)
    expect(state.planSteps[0]).toEqual({ id: 'p0', label: 'Search', status: 'done' })
    expect(state.planSteps[1]).toEqual({ id: 'p1', label: 'Analyze', status: 'active' })
  })

  it('inserts progress-type ProcessStep entries into steps[]', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      makePlanUpdate([
        { id: 'p0', content: 'Search', status: 'pending' },
        { id: 'p1', content: 'Write', status: 'pending' },
      ]),
      state,
    )
    const progressSteps = state.steps.filter((s) => s.type === 'progress')
    expect(progressSteps).toHaveLength(2)
    expect(progressSteps[0]).toMatchObject({ type: 'progress', id: 'p0', title: 'Search' })
    expect(progressSteps[1]).toMatchObject({ type: 'progress', id: 'p1', title: 'Write' })
  })

  it('updates existing progress steps in-place on re-emit with new hash', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      makePlanUpdate([{ id: 'p0', content: 'Search', status: 'pending' }]),
      state,
    )
    normalizeAgentEvent(
      makePlanUpdate([{ id: 'p0', content: 'Search', status: 'completed' }]),
      state,
    )
    const progressSteps = state.steps.filter((s) => s.type === 'progress')
    // Should still be only 1 step (updated in-place), not 2
    expect(progressSteps).toHaveLength(1)
    expect(progressSteps[0]).toMatchObject({ status: 'done' })
  })

  it('source switch: inference active + plan.update clears inferredSteps', () => {
    const state = createNormalizationState()
    // Activate inference mode manually
    state.planSource = 'inferred'
    state.inferredSteps = [{ id: 'i0', label: 'Inferred step', status: 'active' }]

    normalizeAgentEvent(
      makePlanUpdate([{ id: 'p0', content: 'Explicit step', status: 'pending' }]),
      state,
    )
    expect(state.inferredSteps).toEqual([])
    expect(state.planSource).toBe('explicit')
  })
})

describe('tool.progress', () => {
  it('updates progressMessage on matching tool_call step', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(makeToolCall('tool-1'), state)
    normalizeAgentEvent(makeToolProgress('tool-1', 'Fetching results...'), state)

    const toolStep = state.steps.find((s) => s.type === 'tool_call' && s.id === 'tool-1')
    expect(toolStep?.type === 'tool_call' && toolStep.progressMessage).toBe('Fetching results...')
  })

  it('emits tool_progress NormalizedAiEvent', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(makeToolCall('tool-1'), state)
    const emitted = normalizeAgentEvent(makeToolProgress('tool-1', 'Fetching...'), state)
    const evt = emitted.find((e) => e.type === 'tool_progress')
    expect(evt).toBeDefined()
    expect(evt?.type === 'tool_progress' && evt.toolCallId).toBe('tool-1')
    expect(evt?.type === 'tool_progress' && evt.progressMessage).toBe('Fetching...')
  })

  it('does not crash when tool_id is unknown, and still emits event', () => {
    const state = createNormalizationState()
    // No matching tool_call step — should not throw
    const emitted = normalizeAgentEvent(makeToolProgress('unknown-id', 'Working...'), state)
    const evt = emitted.find((e) => e.type === 'tool_progress')
    expect(evt).toBeDefined()
  })
})

describe('tool.call — inference mode activation', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('does NOT activate inference mode while timer is still running', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    // Timer still active (< 3s)
    vi.advanceTimersByTime(1000)
    normalizeAgentEvent(makeToolCall('t1'), state)
    expect(state.planSource).toBeNull()
  })

  it('activates inference mode after timer expires and tool.call arrives', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    vi.advanceTimersByTime(3000) // timer fires, planWaitTimer → null
    normalizeAgentEvent(makeToolCall('t1'), state)
    expect(state.planSource).toBe('inferred')
  })

  it('does not change planSource if explicit plan arrived first', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    // Explicit plan arrives before timer
    normalizeAgentEvent(
      makePlanUpdate([{ id: 'p0', content: 'Step', status: 'pending' }]),
      state,
    )
    expect(state.planSource).toBe('explicit')
    vi.advanceTimersByTime(3000)
    normalizeAgentEvent(makeToolCall('t1'), state)
    // planSource should remain 'explicit' — not overwritten to 'inferred'
    expect(state.planSource).toBe('explicit')
  })
})

describe('capability.end — clears planWaitTimer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('clears timer on capability.end', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    expect(state.planWaitTimer).not.toBeNull()
    normalizeAgentEvent({ type: 'capability.end' }, state)
    expect(state.planWaitTimer).toBeNull()
  })

  it('clears timer on capability.error', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    expect(state.planWaitTimer).not.toBeNull()
    normalizeAgentEvent({
      type: 'capability.error',
      error: { message: 'Oops', code: 'E1' },
    }, state)
    expect(state.planWaitTimer).toBeNull()
  })

  it('does not crash if no timer was set when capability.end fires', () => {
    const state = createNormalizationState()
    // planWaitTimer is null by default — should not throw
    expect(() => normalizeAgentEvent({ type: 'capability.end' }, state)).not.toThrow()
  })
})

describe('plan.update with empty todos', () => {
  it('does not update planSteps or emit plan_update when todos is empty', () => {
    const state = createNormalizationState()
    const emitted = normalizeAgentEvent({ type: 'plan.update', todos: [] }, state)
    expect(state.planSteps).toEqual([])
    expect(emitted.find((e) => e.type === 'plan_update')).toBeUndefined()
  })

  it('still sets planSource to explicit and clears timer even with empty todos', () => {
    vi.useFakeTimers()
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'session.start' }, state)
    normalizeAgentEvent({ type: 'plan.update', todos: [] }, state)
    expect(state.planSource).toBe('explicit')
    expect(state.planWaitTimer).toBeNull()
    vi.useRealTimers()
  })
})
