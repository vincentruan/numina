import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useSwipeComplete } from './useSwipeComplete'
import { MOTION } from '@/utils/motionTokens'

/** Helper to create a minimal TouchEvent-like object */
function makeTouchEvent(
  type: 'touchstart' | 'touchmove' | 'touchend',
  clientX: number,
  clientY: number,
  currentTarget?: HTMLElement,
): TouchEvent {
  const touch = { clientX, clientY, identifier: 0 } as Touch
  return {
    type,
    touches: type === 'touchend' ? [] : [touch],
    changedTouches: [touch],
    preventDefault: vi.fn(),
    currentTarget: currentTarget ?? null,
  } as unknown as TouchEvent
}

/** Helper to create a mock element with offsetWidth */
function makeElement(width = 300): HTMLElement {
  return { offsetWidth: width } as HTMLElement
}

describe('useSwipeComplete', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('calls onComplete when swipe exceeds 60% threshold', () => {
    const onComplete = vi.fn()
    const { onStart, onMove, onEnd } = useSwipeComplete(onComplete)
    const el = makeElement(300) // 60% = 180px

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    onMove('chore-1', makeTouchEvent('touchmove', 290, 200)) // dx = 190 > 180
    onEnd('chore-1')

    expect(onComplete).toHaveBeenCalledWith('chore-1')
  })

  it('does NOT call onComplete when swipe is below threshold', () => {
    const onComplete = vi.fn()
    const { onStart, onMove, onEnd } = useSwipeComplete(onComplete)
    const el = makeElement(300) // 60% = 180px

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    onMove('chore-1', makeTouchEvent('touchmove', 200, 200)) // dx = 100 < 180
    onEnd('chore-1')

    expect(onComplete).not.toHaveBeenCalled()
  })

  it('springs back (settling = true) when below threshold', () => {
    const onComplete = vi.fn()
    const { onStart, onMove, onEnd, swipeStates } = useSwipeComplete(onComplete)
    const el = makeElement(300)

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    onMove('chore-1', makeTouchEvent('touchmove', 200, 200)) // dx = 100
    onEnd('chore-1')

    // After end, settling should be true
    expect(swipeStates.value['chore-1']?.settling).toBe(true)
    expect(swipeStates.value['chore-1']?.translateX).toBe(0)

    // After motion duration, settling clears
    vi.advanceTimersByTime(MOTION.durations.medium)
    expect(swipeStates.value['chore-1']?.settling).toBe(false)
  })

  it('does not interfere with vertical scroll (direction lock)', () => {
    const onComplete = vi.fn()
    const { onStart, onMove, onEnd } = useSwipeComplete(onComplete)
    const el = makeElement(300)

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    // Primarily vertical movement
    onMove('chore-1', makeTouchEvent('touchmove', 105, 300)) // dx=5, dy=100
    onMove('chore-1', makeTouchEvent('touchmove', 110, 400)) // dx=10, dy=200
    onEnd('chore-1')

    expect(onComplete).not.toHaveBeenCalled()
  })

  it('prevents default on horizontal swipe to avoid page scroll', () => {
    const onComplete = vi.fn()
    const { onStart, onMove } = useSwipeComplete(onComplete)
    const el = makeElement(300)

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    const moveEvent = makeTouchEvent('touchmove', 200, 205) // horizontal
    onMove('chore-1', moveEvent)

    expect(moveEvent.preventDefault).toHaveBeenCalled()
  })

  it('cardStyle returns empty when no swipe active', () => {
    const { cardStyle } = useSwipeComplete(vi.fn())
    expect(cardStyle('unknown-id')).toEqual({})
  })

  it('cardStyle includes transition when settling', () => {
    const { onStart, onMove, onEnd, cardStyle } = useSwipeComplete(vi.fn())
    const el = makeElement(300)

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    onMove('chore-1', makeTouchEvent('touchmove', 150, 200)) // below threshold
    onEnd('chore-1')

    const style = cardStyle('chore-1')
    // After spring-back, translateX is 0 but settling was true
    // cardStyle checks settling flag in the returned style
    expect(style.transition).toContain(MOTION.easings.springPop)
  })

  it('bgStyle reflects progress during swipe', () => {
    const { onStart, onMove, bgStyle } = useSwipeComplete(vi.fn())
    const el = makeElement(300) // threshold = 180px

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    onMove('chore-1', makeTouchEvent('touchmove', 190, 200)) // dx = 90, progress = 90/180 = 0.5

    const style = bgStyle('chore-1')
    expect(parseFloat(style.opacity)).toBeCloseTo(0.5, 1)
  })

  it('bgStyle returns opacity 0 for unknown id', () => {
    const { bgStyle } = useSwipeComplete(vi.fn())
    expect(bgStyle('unknown')).toEqual({ opacity: '0' })
  })

  it('ignores leftward swipe (negative dx)', () => {
    const onComplete = vi.fn()
    const { onStart, onMove, onEnd, swipeStates } = useSwipeComplete(onComplete)
    const el = makeElement(300)

    onStart('chore-1', makeTouchEvent('touchstart', 200, 200, el))
    onMove('chore-1', makeTouchEvent('touchmove', 100, 200)) // dx = -100 (left)
    onEnd('chore-1')

    expect(onComplete).not.toHaveBeenCalled()
    // State should remain at zero
    expect(swipeStates.value['chore-1']?.translateX).toBe(0)
  })

  it('supports custom threshold via opts', () => {
    const onComplete = vi.fn()
    const { onStart, onMove, onEnd } = useSwipeComplete(onComplete, { threshold: 0.3 })
    const el = makeElement(300) // 30% = 90px

    onStart('chore-1', makeTouchEvent('touchstart', 100, 200, el))
    onMove('chore-1', makeTouchEvent('touchmove', 200, 200)) // dx = 100 > 90
    onEnd('chore-1')

    expect(onComplete).toHaveBeenCalledWith('chore-1')
  })

  it('handles multiple independent items', () => {
    const onComplete = vi.fn()
    const { onStart, onMove, onEnd } = useSwipeComplete(onComplete)
    const el = makeElement(300)

    // Swipe item A past threshold
    onStart('a', makeTouchEvent('touchstart', 100, 200, el))
    onMove('a', makeTouchEvent('touchmove', 300, 200)) // dx = 200 > 180

    // Swipe item B below threshold
    onStart('b', makeTouchEvent('touchstart', 100, 200, el))
    onMove('b', makeTouchEvent('touchmove', 200, 200)) // dx = 100 < 180

    onEnd('a')
    onEnd('b')

    expect(onComplete).toHaveBeenCalledTimes(1)
    expect(onComplete).toHaveBeenCalledWith('a')
  })
})
