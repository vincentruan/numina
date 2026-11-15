/**
 * Pure helpers for deriving practice-session intent from the route.
 *
 * Kept separate from PracticeSessionPage so the castle's review-window
 * contract (KTD7) and the first-mastery CTA gate (U9) are testable without
 * mounting the full page.
 */
import type { PracticeResultResponse } from '@/api/practice'

export type PracticeSessionMode = 'practice' | 'review'

/**
 * The castle's "复习到期" windows navigate with `?mode=review`; everything
 * else (including a missing or unrecognised value) is an ordinary practice.
 */
export function resolveSessionMode(modeQuery: unknown): PracticeSessionMode {
  return modeQuery === 'review' ? 'review' : 'practice'
}

/**
 * True only when this session pushed the topic to 'mastered' for the first
 * time — the sole trigger for the castle CTA and the brick-drop (R5, F1).
 */
export function isFirstMasteryResult(
  result: Pick<PracticeResultResponse, 'mastery_changed' | 'new_mastery_level'> | null,
): boolean {
  return Boolean(result?.mastery_changed) && result?.new_mastery_level === 'mastered'
}
