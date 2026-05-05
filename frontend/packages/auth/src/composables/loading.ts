import { ref, computed } from 'vue'

// ── Singleton state (HMR-resilient) ──────────────────────────────────────────

function createState() {
  return {
    pendingCount: ref(0),
    isVisible: ref(false),
    isDismissing: ref(false),
    showTimer: null as ReturnType<typeof setTimeout> | null,
    hideTimer: null as ReturnType<typeof setTimeout> | null,
    shownAt: null as number | null,
    // Safety net: auto-clear after 30s to prevent stuck loading
    watchdogTimer: null as ReturnType<typeof setTimeout> | null,
  }
}

const state: ReturnType<typeof createState> = (() => {
  if (import.meta.hot) {
    import.meta.hot.data.loadingState ??= createState()
    return import.meta.hot.data.loadingState as ReturnType<typeof createState>
  }
  return createState()
})()

// Anti-flicker: don't show if request completes within this window
const DEBOUNCE_MS = 200
// Minimum visible time once shown
const MIN_DISPLAY_MS = 400
// Watchdog timeout
const WATCHDOG_MS = 30_000

function armWatchdog() {
  if (state.watchdogTimer !== null) return
  state.watchdogTimer = setTimeout(() => {
    state.pendingCount.value = 0
    state.isVisible.value = false
    state.isDismissing.value = false
    state.shownAt = null
    state.watchdogTimer = null
  }, WATCHDOG_MS)
}

function disarmWatchdog() {
  if (state.watchdogTimer !== null) {
    clearTimeout(state.watchdogTimer)
    state.watchdogTimer = null
  }
}

// ── Public composable ─────────────────────────────────────────────────────────

export function useLoadingOverlay() {
  const isLoading = computed(() => state.isVisible.value)
  const isDismissing = computed(() => state.isDismissing.value)

  function increment() {
    // Cancel any pending hide
    if (state.hideTimer !== null) {
      clearTimeout(state.hideTimer)
      state.hideTimer = null
    }
    state.isDismissing.value = false
    state.pendingCount.value++

    // Arm watchdog on first request
    if (state.pendingCount.value === 1) {
      armWatchdog()
    }

    // Debounce: only show after DEBOUNCE_MS to avoid flash for fast requests
    if (!state.isVisible.value && state.showTimer === null) {
      state.showTimer = setTimeout(() => {
        state.showTimer = null
        if (state.pendingCount.value > 0) {
          state.isVisible.value = true
          state.shownAt = Date.now()
        }
      }, DEBOUNCE_MS)
    }
  }

  function decrement() {
    state.pendingCount.value = Math.max(0, state.pendingCount.value - 1)

    if (state.pendingCount.value > 0) return

    // Cancel debounce show — request finished before debounce fired
    if (state.showTimer !== null) {
      clearTimeout(state.showTimer)
      state.showTimer = null
      disarmWatchdog()
      return
    }

    if (!state.isVisible.value) {
      disarmWatchdog()
      return
    }

    // Respect minimum display time
    const elapsed = state.shownAt !== null ? Date.now() - state.shownAt : MIN_DISPLAY_MS
    const remaining = Math.max(0, MIN_DISPLAY_MS - elapsed)

    state.isDismissing.value = true // drop z-index so toasts appear above

    state.hideTimer = setTimeout(() => {
      state.isVisible.value = false
      state.isDismissing.value = false
      state.shownAt = null
      state.hideTimer = null
      disarmWatchdog()
    }, remaining)
  }

  return { isLoading, isDismissing, increment, decrement }
}
