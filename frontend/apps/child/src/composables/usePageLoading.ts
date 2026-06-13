// frontend/apps/child/src/composables/usePageLoading.ts
import { ref, computed, onUnmounted, type Ref } from 'vue'
import NProgress from 'nprogress'

// Global loading counter (shared across all components in the page)
const loadingCount = ref(0)

// Track if NProgress was started by this system (module-level singleton)
let nprogressStarted: boolean = false

// Track which instances have pending increments
const pendingInstances = new Set<symbol>()

/**
 * Page-level loading coordinator for child app.
 * Replaces direct NProgress.start()/done() calls.
 *
 * Usage:
 * - onMounted: call increment() before async fetch, decrement() after
 * - For multiple async ops: increment() for each, decrement() when each completes
 * - For simple pages with skeleton: call complete() immediately in onMounted
 */
export function usePageLoading() {
  // Create unique ID for this instance
  const instanceId = Symbol('pageLoading')

  function increment() {
    loadingCount.value++
    pendingInstances.add(instanceId)
    if (loadingCount.value === 1 && !nprogressStarted) {
      NProgress.start()
      nprogressStarted = true
    }
  }

  function decrement() {
    if (loadingCount.value > 0) {
      loadingCount.value--
      pendingInstances.delete(instanceId)
    } else {
      if (import.meta.env.DEV) {
        console.warn('[usePageLoading] decrement() called without matching increment()')
      }
    }
    if (loadingCount.value === 0 && nprogressStarted) {
      NProgress.done()
      nprogressStarted = false
    }
  }

  /**
   * Force complete all loading tracking.
   * Use only when you want to abort tracking (e.g., page with skeleton
   * that takes over visual feedback, or error scenarios).
   * WARNING: This clears ALL pending operations, not just this instance's.
   */
  function complete() {
    loadingCount.value = 0
    pendingInstances.clear()
    if (nprogressStarted) {
      NProgress.done()
      nprogressStarted = false
    }
  }

  // Safety net: only clear this instance's contributions on unmount
  onUnmounted(() => {
    if (pendingInstances.has(instanceId)) {
      // This instance had pending increments - clean them up
      pendingInstances.delete(instanceId)
      if (loadingCount.value > 0) {
        loadingCount.value--
      }
      if (loadingCount.value === 0 && nprogressStarted) {
        NProgress.done()
        nprogressStarted = false
      }
    }
  })

  const isGlobalLoading = computed(() => loadingCount.value > 0)

  return {
    increment,
    decrement,
    complete,
    isGlobalLoading,
  }
}

// Export global state for router guard access (without lifecycle hooks)
export const globalLoadingCount: Ref<number> = loadingCount
export function completeGlobalLoading(): void {
  loadingCount.value = 0
  pendingInstances.clear()
  if (nprogressStarted) {
    NProgress.done()
    nprogressStarted = false
  }
}
