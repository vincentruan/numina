/**
 * Celebration state tracking via localStorage.
 * Tracks which approved tasks have been celebrated to prevent repeat animations.
 */

import type { ChoreInstance } from '@/api/chores'

const CELEBRATION_STORAGE_KEY = 'numina-child-celebrated-tasks'
const MAX_CACHED_IDS = 50

/**
 * Get the set of task IDs that have already been celebrated.
 * Returns an empty set if localStorage is empty or contains invalid JSON.
 */
export function getCelebratedIds(): Set<string> {
  try {
    const raw = localStorage.getItem(CELEBRATION_STORAGE_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((id) => typeof id === 'string'))
  } catch {
    // Invalid JSON or other error — graceful fallback
    return new Set()
  }
}

/**
 * Mark task IDs as celebrated. Adds them to localStorage.
 * Automatically prunes to MAX_CACHED_IDS to bound growth.
 */
export function markCelebrated(ids: string[]): void {
  const existing = getCelebratedIds()
  for (const id of ids) {
    if (id) existing.add(id)
  }
  // Prune if exceeding max
  const pruned = pruneToMax(existing, MAX_CACHED_IDS)
  try {
    localStorage.setItem(CELEBRATION_STORAGE_KEY, JSON.stringify(pruned))
  } catch {
    // Silently fail on quota exceeded or private browsing mode
  }
}

/**
 * Find tasks that are approved but not yet celebrated.
 * Returns only tasks with status === 'approved' that are not in the celebrated set.
 */
export function findPendingCelebrations(tasks: ChoreInstance[]): ChoreInstance[] {
  const celebrated = getCelebratedIds()
  return tasks.filter(
    (task) => task.status === 'approved' && !celebrated.has(task.id),
  )
}

/**
 * Prune a set to max size, keeping the most recently added IDs.
 * Since Set iteration order is insertion order, we keep the last N items.
 */
function pruneToMax(ids: Set<string>, max: number): string[] {
  if (ids.size <= max) return [...ids]
  // Convert to array and keep last N (most recent)
  const arr = [...ids]
  return arr.slice(-max)
}

/**
 * Clear all celebration state. Useful for testing or reset.
 */
export function clearCelebratedIds(): void {
  localStorage.removeItem(CELEBRATION_STORAGE_KEY)
}