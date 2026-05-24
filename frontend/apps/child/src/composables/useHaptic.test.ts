import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { tryVibrate } from './useHaptic'

describe('tryVibrate', () => {
  let originalVibrate: typeof navigator.vibrate | undefined

  beforeEach(() => {
    originalVibrate = navigator.vibrate
  })

  afterEach(() => {
    if (originalVibrate) {
      Object.defineProperty(navigator, 'vibrate', {
        configurable: true,
        value: originalVibrate,
      })
    }
  })

  it('returns true and forwards pattern when navigator.vibrate exists', () => {
    const spy = vi.fn(() => true)
    Object.defineProperty(navigator, 'vibrate', { configurable: true, value: spy })

    expect(tryVibrate([50])).toBe(true)
    expect(spy).toHaveBeenCalledWith([50])
  })

  it('returns false when navigator.vibrate is absent (iOS Safari)', () => {
    Object.defineProperty(navigator, 'vibrate', { configurable: true, value: undefined })
    expect(tryVibrate([50])).toBe(false)
  })

  it('returns false when navigator.vibrate throws', () => {
    Object.defineProperty(navigator, 'vibrate', {
      configurable: true,
      value: () => {
        throw new Error('blocked')
      },
    })
    expect(() => tryVibrate([50])).not.toThrow()
    expect(tryVibrate([50])).toBe(false)
  })
})
