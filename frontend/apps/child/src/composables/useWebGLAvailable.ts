/**
 * useWebGLAvailable — check WebGL support without creating context.
 * Reusable composable for 3D components.
 */
import { ref, onMounted } from 'vue'

/**
 * Check if WebGL is available without creating a context.
 */
export function isWebGLAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl2') || canvas.getContext('webgl'))
    )
  } catch {
    return false
  }
}

/**
 * Reactive WebGL availability check.
 * Useful for components that need to update on mount.
 */
export function useWebGLAvailable() {
  const available = ref(false)

  onMounted(() => {
    available.value = isWebGLAvailable()
  })

  return { available }
}

/**
 * Check prefers-reduced-motion media query.
 */
export function useReducedMotionCheck() {
  const reduced = ref(false)

  onMounted(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    reduced.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })

  return { reduced }
}
