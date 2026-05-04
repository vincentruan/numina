import { ref, computed } from 'vue'

// Global singleton — shared across all axios interceptors in the same app
const pendingCount = ref(0)
const isVisible = ref(false)
let hideTimer: ReturnType<typeof setTimeout> | null = null

// Minimum display time (ms) — prevents flash for very fast requests
const MIN_DISPLAY_MS = 400

export function useLoadingOverlay() {
  const isLoading = computed(() => isVisible.value)

  function increment() {
    if (hideTimer !== null) {
      clearTimeout(hideTimer)
      hideTimer = null
    }
    pendingCount.value++
    isVisible.value = true
  }

  function decrement() {
    pendingCount.value = Math.max(0, pendingCount.value - 1)
    if (pendingCount.value === 0) {
      // Delay hide so the exit animation has time to play and fast sequential
      // requests don't cause a flicker (show → hide → show)
      hideTimer = setTimeout(() => {
        isVisible.value = false
        hideTimer = null
      }, MIN_DISPLAY_MS)
    }
  }

  return { isLoading, increment, decrement }
}
