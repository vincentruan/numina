import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { GoalState } from '@/api/ai-chat'

/**
 * U5 (D1 /goal) — optimistic-UI reconciliation for the active thread goal.
 *
 * Ported from DeerFlow `frontend/src/components/workspace/use-active-goal.ts`
 * + `goal-status-helpers.ts` (React hooks → Vue refs + watch).
 *
 * A `/goal <condition>` command updates the UI immediately via `setLocalGoal`
 * (optimistic override), then `submitThreadMessage` starts the run. The
 * override is dropped as soon as the server explicitly reports goal state in a
 * `values` stream chunk — which carries the authoritative `continuation_count`
 * / `updated_at` bumps from U4's auto-continuation loop, or `null` once the
 * goal is cleared/satisfied. A stream chunk that OMITS the goal field is NOT
 * treated as a clear, because clarification interrupts publish partial values
 * while the active goal is still present in the checkpoint
 * (use-active-goal.ts:40-44).
 *
 * Thread navigation resets the optimistic override so a stale local goal from
 * thread A never shadows thread B.
 */

export type UseActiveGoalResult = {
  /** The goal to render — the optimistic override while set, else server state. */
  activeGoal: Ref<GoalState | null>
  /** True when there is an active goal (optimistic or server) to render. */
  hasGoal: Ref<boolean>
  /** Apply an optimistic goal after a `/goal` command (or `null` to hide it). */
  setLocalGoal: (goal: GoalState | null | undefined) => void
  /** The current optimistic override (undefined when none). Test/inspect only. */
  localGoal: Ref<GoalState | null | undefined>
}

/**
 * Resolve the goal to render: the optimistic override wins while set; a stream
 * chunk that omits goal (`serverGoal === undefined`) does NOT clear the
 * override. When no override is present and the server has not provided a goal,
 * returns `null`. Ported from DeerFlow `resolveActiveGoal`.
 */
export function resolveActiveGoal(
  localGoal: GoalState | null | undefined,
  serverGoal: GoalState | null | undefined,
): GoalState | null {
  return localGoal !== undefined ? localGoal : (serverGoal ?? null)
}

/**
 * Decide when an optimistic override should yield back to server state. Ported
 * from DeerFlow `shouldResetLocalGoalOverride`.
 *
 * - Thread navigation always resets (local goal from thread A must not leak).
 * - A stream chunk that explicitly carries the goal field (`serverGoalProvided`
 *   = true) resets: the server has now reported authoritative state — a new
 *   `continuation_count`, a satisfied/cleared goal, etc.
 * - A stream chunk that OMITS the goal field does NOT reset: the override must
 *   persist until the server speaks.
 */
export function shouldResetLocalGoalOverride(input: {
  serverGoalProvided: boolean
  threadChanged: boolean
}): boolean {
  if (input.threadChanged) {
    return true
  }
  return input.serverGoalProvided
}

/**
 * Stable signature of the *server* goal, used to decide when an optimistic
 * client override should yield back to server state. Ported from DeerFlow
 * `goalReconciliationKey` (goal-status-helpers.ts:36-47).
 *
 * It changes whenever a new goal is set (`created_at`), the agent
 * auto-continues (`continuation_count`/`updated_at`), or the backend
 * clears/satisfies the goal (`null`). The watch in `useActiveGoal` resets the
 * optimistic copy when this key changes, so the streamed continuation counter is
 * never permanently shadowed.
 */
export function goalReconciliationKey(goal: GoalState | null): string {
  if (!goal) {
    return 'none'
  }
  return [
    goal.objective,
    goal.status,
    goal.created_at ?? '',
    goal.updated_at ?? '',
    goal.continuation_count ?? 0,
  ].join('|')
}

export type GoalContinuationDisplay = {
  count: number
  max: number
}

/**
 * Decide the continuation counter to render for an active goal. Ported from
 * DeerFlow `getGoalContinuationDisplay` (goal-status-helpers.ts:16-25).
 *
 * Returns `null` until the agent has actually auto-continued at least once
 * (`continuation_count > 0`). Before that, the raw "0/8" reads as a mysterious
 * score, so the counter is hidden; once continuation starts it surfaces as
 * "{count}/{max}".
 */
export function getGoalContinuationDisplay(
  goal: Pick<GoalState, 'continuation_count' | 'max_continuations'>,
): GoalContinuationDisplay | null {
  const count = goal.continuation_count ?? 0
  const max = goal.max_continuations ?? 0
  if (!Number.isFinite(count) || count <= 0) {
    return null
  }
  return { count, max }
}

/**
 * Reconcile the optimistic `/goal`-command result with the server's goal state.
 *
 * @param threadId The currently active thread id (changes reset the override).
 * @param serverGoal The server goal — `undefined` when a `values` stream chunk
 *   OMITS the goal field (do not treat as clear); `null` when the server
 *   explicitly reports no goal; a `GoalState` otherwise. Pass a `Ref` sourced
 *   from `useThreadChat` (which captures `goal` from the `values` SSE channel
 *   + hydrates from checkpoint history).
 */
export function useActiveGoal(
  threadId: Ref<string | null | undefined>,
  serverGoal: Ref<GoalState | null | undefined>,
): UseActiveGoalResult {
  const localGoal = ref<GoalState | null | undefined>(undefined)
  const previousThreadId = ref<string | null | undefined>(threadId.value)
  const serverGoalProvided = computed(() => serverGoal.value !== undefined)
  const serverGoalKey = computed(() =>
    serverGoalProvided.value
      ? goalReconciliationKey(serverGoal.value ?? null)
      : 'missing',
  )

  // Reset the optimistic override when the server explicitly reports goal
  // state (key change) OR on real thread navigation. A `values` chunk omitting
  // the goal field leaves `serverGoal` undefined → key stays "missing" → no
  // reset → override persists (use-active-goal.ts:58-64).
  watch(
    [serverGoalKey, serverGoalProvided, threadId],
    ([, provided, tid]) => {
      const threadChanged = previousThreadId.value !== tid
      previousThreadId.value = tid
      if (shouldResetLocalGoalOverride({ serverGoalProvided: provided, threadChanged })) {
        localGoal.value = undefined
      }
    },
  )

  const activeGoal = computed(() => resolveActiveGoal(localGoal.value, serverGoal.value))
  const hasGoal = computed(() => activeGoal.value !== null)

  function setLocalGoal(goal: GoalState | null | undefined): void {
    localGoal.value = goal
  }

  return { activeGoal, hasGoal, setLocalGoal, localGoal }
}
