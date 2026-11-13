/**
 * Shared state for a hands-on challenge component.
 *
 * Every challenge type evaluates locally and remembers its progress in
 * sessionStorage so leaving the page and coming back does not lose the child's
 * work. This composable holds that state plus the three-state verdict
 * progression, so each type only implements its own evaluation.
 */
import { computed, reactive, ref, watch, type Ref } from 'vue'
import type { ChallengeJudgement, ChallengeVerdict } from '@/types/learning-challenge'

export interface PersistedChallengeState<S> {
  state: S
  attemptCount: number
  completed: boolean
  feedbackMessage: string
  feedbackVerdict: ChallengeVerdict | null
}

export interface ChallengeStateOptions<S extends object> {
  /** Config id — namespaces the sessionStorage key. */
  id: string
  /** Initial (empty) interaction state. */
  initial: S
  /** Rehydrate saved interaction state; return the initial state if unusable. */
  restore?: (saved: S) => S
}

export function useChallengeState<S extends object>(opts: ChallengeStateOptions<S>) {
  const STORAGE_KEY = `numina:challenge:${opts.id}`

  const state = reactive(opts.initial) as S
  const attemptCount = ref(0)
  const completed = ref(false)
  const feedbackMessage = ref('')
  const feedbackVerdict = ref<ChallengeVerdict | null>(null)

  // ── Persistence ──

  function restoreState() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const saved = JSON.parse(raw) as PersistedChallengeState<S>
      if (saved.state) {
        const next = opts.restore ? opts.restore(saved.state) : saved.state
        Object.assign(state, next)
      }
      attemptCount.value = saved.attemptCount ?? 0
      completed.value = saved.completed ?? false
      feedbackMessage.value = saved.feedbackMessage ?? ''
      feedbackVerdict.value = saved.feedbackVerdict ?? null
    } catch {
      // Storage unavailable — the challenge still works, it just won't resume.
    }
  }

  function clearState() {
    try {
      sessionStorage.removeItem(STORAGE_KEY)
    } catch {
      // Storage unavailable
    }
  }

  restoreState()

  watch(
    [() => state as unknown as Ref<S>, attemptCount, completed, feedbackMessage, feedbackVerdict],
    () => {
      try {
        const persisted: PersistedChallengeState<S> = {
          state: JSON.parse(JSON.stringify(state)) as S,
          attemptCount: attemptCount.value,
          completed: completed.value,
          feedbackMessage: feedbackMessage.value,
          feedbackVerdict: feedbackVerdict.value,
        }
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(persisted))
      } catch {
        // Storage unavailable
      }
    },
    { deep: true },
  )

  // ── Verdict progression ──

  /**
   * Apply an evaluation. `correct` completes the challenge; `close` and
   * `wrong` leave it open for another attempt.
   */
  function applyJudgement(judgement: ChallengeJudgement, successMessage: string) {
    attemptCount.value++
    feedbackVerdict.value = judgement.verdict
    if (judgement.verdict === 'correct') {
      completed.value = true
      feedbackMessage.value = successMessage
    } else {
      feedbackMessage.value = judgement.hint
    }
  }

  const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)

  /**
   * After two retries the child may continue without a correct verdict, so a
   * child who keeps landing `close` is never stuck in the challenge.
   */
  const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)

  return {
    state,
    attemptCount,
    completed,
    feedbackMessage,
    feedbackVerdict,
    showTutorSuggestion,
    allowEarlyContinue,
    applyJudgement,
    clearState,
  }
}
