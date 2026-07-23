import { describe, it, expect } from 'vitest'
import { ref, nextTick } from 'vue'
import {
  resolveActiveGoal,
  shouldResetLocalGoalOverride,
  goalReconciliationKey,
  getGoalContinuationDisplay,
  useActiveGoal,
} from '@/composables/ai-chat/useActiveGoal'
import type { GoalState } from '@/api/ai-chat'

function makeGoal(overrides: Partial<GoalState> = {}): GoalState {
  return {
    objective: 'ship the landing page',
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    continuation_count: 0,
    max_continuations: 8,
    no_progress_count: 0,
    max_no_progress_continuations: 2,
    ...overrides,
  }
}

describe('resolveActiveGoal', () => {
  it('keeps the optimistic goal when stream values omit the goal field', () => {
    const localGoal = makeGoal()
    expect(resolveActiveGoal(localGoal, undefined)).toBe(localGoal)
  })

  it('falls back to null when neither local nor server state has a goal', () => {
    expect(resolveActiveGoal(undefined, undefined)).toBeNull()
    expect(resolveActiveGoal(undefined, null)).toBeNull()
  })
})

describe('shouldResetLocalGoalOverride', () => {
  it('does not reset an optimistic goal when the same thread omits goal from stream values', () => {
    expect(
      shouldResetLocalGoalOverride({ serverGoalProvided: false, threadChanged: false }),
    ).toBe(false)
  })

  it('resets an optimistic goal when the server explicitly clears the goal', () => {
    expect(
      shouldResetLocalGoalOverride({ serverGoalProvided: true, threadChanged: false }),
    ).toBe(true)
  })

  it('resets an optimistic goal on real thread navigation', () => {
    expect(
      shouldResetLocalGoalOverride({ serverGoalProvided: false, threadChanged: true }),
    ).toBe(true)
  })
})

describe('goalReconciliationKey', () => {
  it('returns "none" for a null goal', () => {
    expect(goalReconciliationKey(null)).toBe('none')
  })

  it('changes when continuation_count bumps (auto-continuation)', () => {
    const before = goalReconciliationKey(makeGoal({ continuation_count: 0 }))
    const after = goalReconciliationKey(makeGoal({ continuation_count: 1, updated_at: '2026-01-02T00:00:00Z' }))
    expect(after).not.toBe(before)
  })
})

describe('getGoalContinuationDisplay', () => {
  it('returns null until continuation_count > 0 (hides 0/8)', () => {
    expect(getGoalContinuationDisplay(makeGoal({ continuation_count: 0 }))).toBeNull()
  })

  it('returns count/max once the agent has auto-continued at least once', () => {
    expect(getGoalContinuationDisplay(makeGoal({ continuation_count: 3 }))).toEqual({
      count: 3,
      max: 8,
    })
  })
})

describe('useActiveGoal (reactive reconciliation)', () => {
  it('optimistic override shows immediately and yields when the server stream arrives', async () => {
    const threadId = ref<string | null | undefined>('thread-1')
    const serverGoal = ref<GoalState | null | undefined>(undefined)
    const { activeGoal, hasGoal, setLocalGoal } = useActiveGoal(threadId, serverGoal)

    const optimistic = makeGoal({ objective: '分析资产' })
    setLocalGoal(optimistic)
    await nextTick()
    // The override is returned by value through a computed; use deep equality.
    expect(activeGoal.value).toStrictEqual(optimistic)
    expect(hasGoal.value).toBe(true)

    // Server stream now carries the authoritative goal → override yields.
    // (activeGoal is a computed over a ref; Vue returns a reactive proxy, so
    // compare by deep equality rather than reference identity.)
    const server = makeGoal({ objective: '分析资产', continuation_count: 2, updated_at: '2026-01-03T00:00:00Z' })
    serverGoal.value = server
    await nextTick()
    expect(activeGoal.value).toStrictEqual(server)
  })

  it('a stream chunk omitting goal does NOT clear the optimistic override', async () => {
    const threadId = ref<string | null | undefined>('thread-1')
    // serverGoal stays undefined (values chunk omitted the goal field entirely).
    const serverGoal = ref<GoalState | null | undefined>(undefined)
    const { activeGoal, setLocalGoal } = useActiveGoal(threadId, serverGoal)

    const optimistic = makeGoal()
    setLocalGoal(optimistic)
    await nextTick()
    // No server state change — override must persist.
    expect(activeGoal.value).toStrictEqual(optimistic)
  })

  it('thread switch clears the optimistic override', async () => {
    const threadId = ref<string | null | undefined>('thread-1')
    const serverGoal = ref<GoalState | null | undefined>(undefined)
    const { activeGoal, setLocalGoal } = useActiveGoal(threadId, serverGoal)

    setLocalGoal(makeGoal({ objective: 'thread-1 goal' }))
    await nextTick()
    expect(activeGoal.value).not.toBeNull()

    // Navigate to thread-2 — override must drop (and no server goal yet → null).
    threadId.value = 'thread-2'
    await nextTick()
    expect(activeGoal.value).toBeNull()
  })
})
