import { ref, type Ref } from 'vue'
import { MOTION } from '@/utils/motionTokens'

/**
 * Swipe-to-complete gesture composable for child task cards.
 *
 * Uses native touch events (KTD3 — no gesture library).
 * Tracks horizontal delta; only triggers when horizontal > vertical (avoids scroll interference).
 * When swipe distance exceeds 60% of item width, completion fires on touchend.
 * Below threshold: spring-back animation via motionTokens easing.
 */

const SWIPE_THRESHOLD_RATIO = 0.6
const DIRECTION_LOCK_PX = 6

export interface SwipeState {
  translateX: number
  progress: number
  settling: boolean
}

export function useSwipeComplete(
  onComplete: (instanceId: string) => void,
  opts?: { threshold?: number },
) {
  const threshold = opts?.threshold ?? SWIPE_THRESHOLD_RATIO

  const swipeStates: Ref<Record<string, SwipeState>> = ref({})

  // Non-reactive touch tracking (avoids unnecessary reactivity overhead)
  type Tracking = {
    startX: number
    startY: number
    itemWidth: number
    horizontal: boolean | null // null = undetermined
  }
  const tracking = new Map<string, Tracking>()

  function onStart(id: string, e: TouchEvent) {
    const touch = e.touches[0]
    const el = e.currentTarget as HTMLElement
    tracking.set(id, {
      startX: touch.clientX,
      startY: touch.clientY,
      itemWidth: el.offsetWidth,
      horizontal: null,
    })
    // Reset to zero without animation
    swipeStates.value[id] = { translateX: 0, progress: 0, settling: false }
  }

  function onMove(id: string, e: TouchEvent) {
    const t = tracking.get(id)
    if (!t) return

    const touch = e.touches[0]
    const dx = touch.clientX - t.startX
    const dy = touch.clientY - t.startY

    // Direction lock: determine axis on first significant movement
    if (t.horizontal === null && (Math.abs(dx) > DIRECTION_LOCK_PX || Math.abs(dy) > DIRECTION_LOCK_PX)) {
      t.horizontal = Math.abs(dx) > Math.abs(dy)
    }

    // Vertical scroll — don't interfere
    if (t.horizontal === false) return

    // Only allow rightward swipe
    if (dx <= 0) return

    // Prevent page scroll while swiping horizontally
    e.preventDefault()

    const maxDx = t.itemWidth * threshold
    // Allow slight overshoot for tactile feel, cap at 110% of threshold
    const clampedDx = Math.min(dx, maxDx * 1.1)
    const progress = Math.min(1, clampedDx / maxDx)

    swipeStates.value = {
      ...swipeStates.value,
      [id]: { translateX: clampedDx, progress, settling: false },
    }
  }

  function onEnd(id: string) {
    const t = tracking.get(id)
    tracking.delete(id)

    const state = swipeStates.value[id]
    if (!state) return

    if (state.progress >= 1) {
      // Threshold met — fire completion, snap back instantly
      swipeStates.value = {
        ...swipeStates.value,
        [id]: { translateX: 0, progress: 0, settling: false },
      }
      onComplete(id)
    } else {
      // Below threshold — spring back with animation
      swipeStates.value = {
        ...swipeStates.value,
        [id]: { translateX: 0, progress: 0, settling: true },
      }
      setTimeout(() => {
        const current = swipeStates.value[id]
        if (current?.settling) {
          swipeStates.value = {
            ...swipeStates.value,
            [id]: { ...current, settling: false },
          }
        }
      }, MOTION.durations.medium)
    }
  }

  /** Inline style for the card element — translates during swipe */
  function cardStyle(id: string): Record<string, string> {
    const state = swipeStates.value[id]
    if (!state || (state.translateX === 0 && !state.settling)) return {}
    return {
      transform: `translateX(${state.translateX}px)`,
      transition: state.settling
        ? `transform ${MOTION.durations.medium}ms ${MOTION.easings.springPop}`
        : 'none',
    }
  }

  /** Inline style for the background indicator — opacity tracks progress */
  function bgStyle(id: string): Record<string, string> {
    const state = swipeStates.value[id]
    if (!state) return { opacity: '0' }
    return { opacity: String(state.progress) }
  }

  return {
    swipeStates,
    onStart,
    onMove,
    onEnd,
    cardStyle,
    bgStyle,
  }
}
