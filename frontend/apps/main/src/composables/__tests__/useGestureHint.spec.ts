import { describe, it, expect, beforeEach } from 'vitest'
import { useGestureHint } from '../useGestureHint'

describe('useGestureHint', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns played=false initially', () => {
    const { played } = useGestureHint('test-gesture')
    expect(played.value).toBe(false)
  })

  it('trigger() sets played=true and marks done when not already done', () => {
    const { played, trigger } = useGestureHint('test-gesture')
    trigger()
    expect(played.value).toBe(true)
    expect(localStorage.getItem('gesture_test-gesture')).toBe('done')
  })

  it('trigger() does NOT play when already done', () => {
    localStorage.setItem('gesture_test-gesture', 'done')
    const { played, trigger } = useGestureHint('test-gesture')
    trigger()
    expect(played.value).toBe(false)
  })
})