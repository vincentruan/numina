import type { ProgressWithTopic } from '@/api/learning'

/**
 * Mastery-status mapping shared across every learning-map view.
 *
 * #18 fix: ClusterMap, GraphMap, TopicGrid, TopicNode and TopicConstellation
 * each carried their own copy of this logic; a new state added to one view
 * was silently missing from the others. A single source of truth here keeps
 * the five callers in lock-step.
 *
 * The review-due branch requires `next_review_at` to be present; callers with
 * only a level (e.g. TopicConstellation's `OceanTopic`) pass the level in an
 * item shape with no `next_review_at` and get the four-state mapping.
 */
export type MasteryStatus = 'mastered' | 'learning' | 'available' | 'locked' | 'review'

export function masteryStatus(
  item: Pick<ProgressWithTopic, 'mastery_level'> & { next_review_at?: string | null },
): MasteryStatus {
  const level = item.mastery_level
  if (level === 'mastered') {
    if (item.next_review_at) {
      const reviewDate = new Date(item.next_review_at)
      if (reviewDate <= new Date()) return 'review'
    }
    return 'mastered'
  }
  if (level === 'learning' || level === 'assessing') return 'learning'
  if (level === 'locked') return 'locked'
  return 'available'
}
