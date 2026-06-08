/**
 * Canvas collapse preference persistence utility.
 *
 * Module-level singleton following the darkMode/locale pattern:
 * - ref + watchEffect at module scope for automatic persistence
 * - Namespaced localStorage key to avoid cross-app collision
 */

import { ref, watchEffect } from 'vue'

const STORAGE_KEY = 'canvas:collapse-preference'

function getStoredPreference(): boolean {
  if (typeof window === 'undefined') return false
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'true'
}

// Module-level singleton — shared across all AgentRunCanvas instances
const isCollapsed = ref<boolean>(
  typeof window !== 'undefined' ? getStoredPreference() : false,
)

// Auto-sync to localStorage on change
if (typeof window !== 'undefined') {
  watchEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(isCollapsed.value))
  })
}

/**
 * Get canvas collapse preference state and controls.
 *
 * @returns Reactive collapse state and toggle function
 */
export function useCanvasPreference() {
  function toggleCollapse() {
    isCollapsed.value = !isCollapsed.value
  }

  function setCollapsed(collapsed: boolean) {
    isCollapsed.value = collapsed
  }

  /**
   * Clear preference (optional, for logout scenarios).
   * Preference is non-sensitive UI state, so cleanup is optional.
   */
  function clearPreference() {
    localStorage.removeItem(STORAGE_KEY)
    isCollapsed.value = false
  }

  return {
    isCollapsed,
    toggleCollapse,
    setCollapsed,
    clearPreference,
  }
}