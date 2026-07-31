import { ref, type Ref } from 'vue'
import { isGuideDone, markGuideDone } from '@/utils/storage'

/**
 * One-shot gesture hint trigger.
 * Tracks playback state via localStorage to ensure the hint fires only once per key.
 *
 * The actual animation is applied via CSS classes on the target element by the caller.
 * This composable only manages the "should I play?" decision and persistence.
 *
 * @param key - Unique identifier for this gesture hint (stored as gesture_<key>)
 */
export function useGestureHint(key: string): {
  played: Ref<boolean>
  trigger: () => void
} {
  const storageKey = `gesture_${key}`
  const played = ref(false)

  function trigger() {
    if (isGuideDone(storageKey)) return
    played.value = true
    markGuideDone(storageKey)
  }

  return { played, trigger }
}
