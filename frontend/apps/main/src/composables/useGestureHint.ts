import { ref, type Ref } from 'vue'
import { isGuideDone, markGuideDone } from '@/utils/storage'

export interface UseGestureHintOptions {
  target: string
  type: 'swipe-left' | 'long-press-pulse'
  autoPlay?: number
}

export function useGestureHint(key: string, _options: UseGestureHintOptions): {
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