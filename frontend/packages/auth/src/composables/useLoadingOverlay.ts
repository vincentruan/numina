import { ref, computed } from 'vue'

// Module-level singleton — intentional for SPA use.
// This project is Vite SPA-only (no SSR), so cross-request state leakage is not a concern.
// HMR resilience: preserve state across hot reloads so in-flight requests don't orphan the counter.
function createState() {
  return {
    pendingCount: ref(0),
    isVisible: ref(false),
    hideTimer: null as ReturnType<typeof setTimeout> | null,
  }
}

// In dev with HMR, reuse state stored on import.meta.hot.data so that a module
// re-evaluation doesn't reset an in-flight counter to 0.
// In production (no import.meta.hot), create a plain module-level singleton.
const state: ReturnType<typeof createState> = (() => {
  if (import.meta.hot) {
    import.meta.hot.data.loadingState ??= createState()
    return import.meta.hot.data.loadingState as ReturnType<typeof createState>
  }
  return createState()
})()

// Minimum display time (ms) — prevents flash for very fast requests
const MIN_DISPLAY_MS = 400

export function useLoadingOverlay() {
  const isLoading = computed(() => state.isVisible.value)

  function increment() {
    if (state.hideTimer !== null) {
      clearTimeout(state.hideTimer)
      state.hideTimer = null
    }
    state.pendingCount.value++
    state.isVisible.value = true
  }

  function decrement() {
    state.pendingCount.value = Math.max(0, state.pendingCount.value - 1)
    if (state.pendingCount.value === 0) {
      // Delay hide so the exit animation has time to play and fast sequential
      // requests don't cause a flicker (show → hide → show)
      state.hideTimer = setTimeout(() => {
        state.isVisible.value = false
        state.hideTimer = null
      }, MIN_DISPLAY_MS)
    }
  }

  return { isLoading, increment, decrement }
}
