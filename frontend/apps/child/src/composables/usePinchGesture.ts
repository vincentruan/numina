import { ref, readonly, type Ref } from 'vue'

/** Minimal shared two-finger pinch gesture detector. */
const PINCH_THRESHOLD = 1.15

export interface PinchGestureHandlers {
  onPinchOut?: () => void
  onPinchIn?: (touch: { clientX: number; clientY: number }) => void
}

export interface PinchGesture {
  onTouchStart(event: TouchEvent): void
  onTouchMove(event: TouchEvent): void
  onTouchEnd(): void
  isPinching: Readonly<Ref<boolean>>
  reset(): void
}

function touchDistance(event: TouchEvent): number {
  const first = event.touches[0]
  const second = event.touches[1]
  if (!first || !second) return 0
  return Math.hypot(
    first.clientX - second.clientX,
    first.clientY - second.clientY,
  )
}

/**
 * Report each pinch direction once per gesture. The reset timer survives the
 * synthetic pointerup/click that follows a touch gesture, so callers can use
 * `isPinching.value` to suppress that follow-up event.
 */
export function usePinchGesture(handlers: PinchGestureHandlers = {}): PinchGesture {
  let startDistance = 0
  let pinchedOut = false
  let pinchedIn = false
  let resetTimer: ReturnType<typeof setTimeout> | null = null
  let active = false
  const pinching = ref(false)

  function cancelResetTimer(): void {
    if (resetTimer !== null) clearTimeout(resetTimer)
    resetTimer = null
  }

  function reset(): void {
    cancelResetTimer()
    startDistance = 0
    pinchedOut = false
    pinchedIn = false
    active = false
    pinching.value = false
  }

  function onTouchStart(event: TouchEvent): void {
    if (event.touches.length !== 2) return
    cancelResetTimer()
    startDistance = touchDistance(event)
    pinchedOut = false
    pinchedIn = false
    active = true
    pinching.value = false
  }

  function onTouchMove(event: TouchEvent): void {
    if (event.touches.length !== 2) return
    const distance = touchDistance(event)
    if (startDistance <= 0) {
      startDistance = distance
      return
    }
    const ratio = distance / startDistance
    if (ratio > PINCH_THRESHOLD && !pinchedOut) {
      pinchedOut = true
      pinching.value = true
      startDistance = distance
      handlers.onPinchOut?.()
    } else if (ratio < 1 / PINCH_THRESHOLD && !pinchedIn) {
      pinchedIn = true
      pinching.value = true
      startDistance = distance
      handlers.onPinchIn?.(event.touches[0])
    }
  }

  function onTouchEnd(): void {
    if (!active) return
    active = false
    startDistance = 0
    cancelResetTimer()
    if (pinchedOut || pinchedIn) {
      resetTimer = setTimeout(() => {
        resetTimer = null
        pinchedOut = false
        pinchedIn = false
        pinching.value = false
      }, 0)
    }
  }

  return {
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    isPinching: readonly(pinching),
    reset,
  }
}
