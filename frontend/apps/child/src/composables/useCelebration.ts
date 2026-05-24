/**
 * Celebration orchestration composable.
 * Centralizes celebration trigger logic, state management, and lifecycle coordination.
 * Use in pages that need to trigger celebration on approved tasks.
 */

import { ref } from 'vue'
import type { ChoreInstance } from '@/api/chores'
import { findPendingCelebrations, markCelebrated } from '@/utils/celebrationState'

export type StreakTier = 0 | 7 | 14 | 30

function resolveStreakTier(tasks: ChoreInstance[]): StreakTier {
  let max = 0
  for (const t of tasks) {
    const s = t.streak_count ?? 0
    if (s > max) max = s
  }
  if (max >= 30) return 30
  if (max >= 14) return 14
  if (max >= 7) return 7
  return 0
}

export function useCelebration() {
  const celebrationVisible = ref(false)
  const celebrationTaskCount = ref(0)
  const celebrationStarsEarned = ref(0)
  const celebrationTaskIds = ref<string[]>([])
  const celebrationStreakTier = ref<StreakTier>(0)

  /**
   * Trigger celebration for approved tasks not yet celebrated.
   * Computes total stars earned and shows animation.
   */
  function triggerCelebration(tasks: ChoreInstance[]): void {
    if (tasks.length === 0) return
    celebrationTaskCount.value = tasks.length
    celebrationStarsEarned.value = tasks.reduce(
      (sum, t) => sum + (t.coin_reward ?? 0) + (t.streak_bonus ?? 0),
      0,
    )
    celebrationTaskIds.value = tasks.map((t) => t.id)
    celebrationStreakTier.value = resolveStreakTier(tasks)
    celebrationVisible.value = true
  }

  /**
   * Handle celebration dismiss — mark tasks as celebrated.
   */
  function onCelebrationDismiss(): void {
    celebrationVisible.value = false
    if (celebrationTaskIds.value.length > 0) {
      markCelebrated(celebrationTaskIds.value)
    }
  }

  /**
   * Check for pending celebrations and trigger if found.
   * Call this after data loads complete.
   */
  function checkAndTriggerCelebration(chores: ChoreInstance[]): void {
    const pending = findPendingCelebrations(chores)
    if (pending.length > 0) {
      triggerCelebration(pending)
    }
  }

  return {
    celebrationVisible,
    celebrationTaskCount,
    celebrationStarsEarned,
    celebrationTaskIds,
    celebrationStreakTier,
    triggerCelebration,
    onCelebrationDismiss,
    checkAndTriggerCelebration,
  }
}
