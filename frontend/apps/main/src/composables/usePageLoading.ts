import { ref, computed, onUnmounted, type Ref } from 'vue'
import NProgress from 'nprogress'

// Global loading counter (shared across all components in the page)
const loadingCount = ref(0)

// Track if NProgress was started by this system (module-level singleton)
let nprogressStarted: boolean = false

// Track if NProgress was started by the router (beforeEach)
// This allows increment() to take over without restarting the progress bar
let routerNprogressActive: boolean = false

// Track if completeGlobalLoading() already ran for the current navigation.
// When true, increment() knows the router's safety timeout fired first (e.g.
// because a Transition out-in delay pushed mount past the timeout). In that
// case increment must NOT restart NProgress — the bar was already completed.
let routerDone: boolean = false

// Track router's safety timeout ID so increment() can clear it (prevents TOCTOU race)
let routerTimeoutId: ReturnType<typeof setTimeout> | null = null

// Track stuck loading safety timeout ID
let stuckTimeoutId: ReturnType<typeof setTimeout> | null = null

// Track which instances have pending increments with count and active status
// Key: instanceId symbol, Value: { count: number of pending increments, active: boolean }
const pendingInstances = new Map<symbol, { count: number; active: boolean }>()

/**
 * Page-level loading coordinator.
 * Replaces direct NProgress.start()/done() calls.
 *
 * Usage:
 * - onMounted: call increment() before async fetch, decrement() after
 * - For multiple async ops: increment() for each, decrement() when each completes
 * - For simple pages: call complete() in onMounted
 */
export function usePageLoading() {
  // Create unique ID for this instance
  const instanceId = Symbol('pageLoading')

  // Mark instance as active on creation
  pendingInstances.set(instanceId, { count: 0, active: true })

  function increment() {
    // Clear router's safety timeout to prevent TOCTOU race
    if (routerTimeoutId !== null) {
      clearTimeout(routerTimeoutId)
      routerTimeoutId = null
    }

    const instance = pendingInstances.get(instanceId)
    if (!instance || !instance.active) {
      // KeepAlive may have evicted and re-activated the component, causing
      // onUnmounted to mark this instance inactive and remove it from the map.
      // When onActivated fires again, re-register the instance so the
      // increment/decrement pair stays balanced.
      pendingInstances.set(instanceId, { count: 0, active: true })
    }

    const active = pendingInstances.get(instanceId)!
    loadingCount.value++
    active.count++

    if (loadingCount.value === 1 && !nprogressStarted) {
      // If router already started NProgress, take over without restarting
      // This prevents the flicker: start→done→start pattern
      if (!routerNprogressActive) {
        // If completeGlobalLoading() already fired (e.g. Transition out-in
        // delay pushed mount past the afterEach timeout), the bar was already
        // hidden. Don't restart it — just mark started so decrement() can
        // call done() (harmless no-op) for bookkeeping.
        if (routerDone) {
          nprogressStarted = true
          routerDone = false
        } else {
          NProgress.start()
          nprogressStarted = true
        }
      } else {
        routerNprogressActive = false
        nprogressStarted = true
      }

      // Start stuck safety timeout
      if (stuckTimeoutId !== null) {
        clearTimeout(stuckTimeoutId)
      }
      stuckTimeoutId = setTimeout(() => {
        if (import.meta.env.DEV) {
          console.warn('[usePageLoading] Loading operation stuck, forcing complete')
        }
        completeGlobalLoading()
      }, 5000)
    }
  }

  function decrement() {
    const instance = pendingInstances.get(instanceId)

    // Guard: instance must exist, be active, and have pending increments
    if (!instance || !instance.active || instance.count === 0) {
      if (import.meta.env.DEV) {
        if (!instance) {
          console.warn('[usePageLoading] decrement() called on unknown instance')
        } else if (!instance.active) {
          console.warn('[usePageLoading] decrement() called on inactive (unmounted) instance')
        } else {
          console.warn('[usePageLoading] decrement() called without matching increment()')
        }
      }
      return
    }

    loadingCount.value--
    instance.count--

    // Remove from map when count reaches zero (no pending ops)
    if (instance.count === 0) {
      pendingInstances.delete(instanceId)
    }

    // Complete NProgress when all loading is done
    if (loadingCount.value === 0 && nprogressStarted) {
      NProgress.done()
      nprogressStarted = false

      if (stuckTimeoutId !== null) {
        clearTimeout(stuckTimeoutId)
        stuckTimeoutId = null
      }
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
    if (stuckTimeoutId !== null) {
      clearTimeout(stuckTimeoutId)
      stuckTimeoutId = null
    }
    // Always call NProgress.done() - this is a cleanup function
    // Router beforeEach may have called NProgress.start() directly,
    // so we must complete NProgress unconditionally
    NProgress.done()
    nprogressStarted = false
  }

  // Safety net: mark instance inactive and clear its pending contributions on unmount
  onUnmounted(() => {
    const instance = pendingInstances.get(instanceId)
    if (instance && instance.active) {
      // Mark inactive to prevent stale decrement() calls
      instance.active = false

      // Subtract this instance's remaining count from global counter
      if (instance.count > 0 && loadingCount.value >= instance.count) {
        loadingCount.value -= instance.count
        instance.count = 0
      }

      // Remove from map
      pendingInstances.delete(instanceId)

      // Complete NProgress if all loading is now done
      // Always call done() when loadingCount reaches 0 - router may have started NProgress directly
      if (loadingCount.value === 0) {
        NProgress.done()
        nprogressStarted = false

        if (stuckTimeoutId !== null) {
          clearTimeout(stuckTimeoutId)
          stuckTimeoutId = null
        }
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

// --- Router-facing exports (no lifecycle hooks) ---

export const globalLoadingCount: Ref<number> = loadingCount

export function completeGlobalLoading(): void {
  loadingCount.value = 0
  pendingInstances.clear()
  if (stuckTimeoutId !== null) {
    clearTimeout(stuckTimeoutId)
    stuckTimeoutId = null
  }
  // Always call NProgress.done() - this is the emergency cleanup function
  // Router beforeEach may have called NProgress.start() directly without setting nprogressStarted,
  // so we must complete NProgress unconditionally to prevent stuck progress bar
  NProgress.done()
  nprogressStarted = false
  routerNprogressActive = false
  // Signal to increment() that the router timeout already fired. If a page
  // mounts later (e.g. Transition out-in delay pushed it past the timeout),
  // increment() will NOT restart NProgress — the bar was already completed.
  routerDone = true
}

/**
 * Register router's safety timeout ID so increment() can clear it.
 * Call this from router afterEach when scheduling the timeout.
 */
export function registerRouterTimeout(timeoutId: ReturnType<typeof setTimeout>): void {
  routerTimeoutId = timeoutId
}

/**
 * Clear router's safety timeout manually (e.g., for hasSkeleton pages).
 */
export function clearRouterTimeout(): void {
  if (routerTimeoutId !== null) {
    clearTimeout(routerTimeoutId)
    routerTimeoutId = null
  }
}

/**
 * Mark that router has started NProgress (called from beforeEach).
 * This allows increment() to take over without restarting the progress bar.
 */
export function markRouterNprogressActive(): void {
  routerNprogressActive = true
  routerDone = false
}

/**
 * Reset all module-level state. Test only — not part of the public API.
 */
export function _resetForTesting(): void {
  loadingCount.value = 0
  pendingInstances.clear()
  nprogressStarted = false
  routerNprogressActive = false
  routerDone = false
  if (stuckTimeoutId !== null) {
    clearTimeout(stuckTimeoutId)
    stuckTimeoutId = null
  }
  if (routerTimeoutId !== null) {
    clearTimeout(routerTimeoutId)
    routerTimeoutId = null
  }
}