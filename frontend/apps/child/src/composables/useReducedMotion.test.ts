import { describe, it, expect, beforeEach, vi } from 'vitest'
import { effectScope } from 'vue'

describe('useReducedMotion', () => {
  let listeners: Array<(e: { matches: boolean }) => void>
  let mqMatches: boolean

  beforeEach(() => {
    listeners = []
    mqMatches = false
    vi.resetModules()
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        get matches() {
          return mqMatches
        },
        addEventListener: (_evt: string, cb: (e: { matches: boolean }) => void) => {
          listeners.push(cb)
        },
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        media: '(prefers-reduced-motion: reduce)',
        onchange: null,
      })),
    })
  })

  it('initial value reflects matchMedia.matches', async () => {
    mqMatches = true
    const { useReducedMotion } = await import('./useReducedMotion')
    const scope = effectScope()
    scope.run(() => {
      const isReduced = useReducedMotion()
      expect(isReduced.value).toBe(true)
    })
    scope.stop()
  })

  it('updates reactively when matchMedia change event fires', async () => {
    mqMatches = false
    const { useReducedMotion } = await import('./useReducedMotion')
    const scope = effectScope()
    scope.run(() => {
      const isReduced = useReducedMotion()
      expect(isReduced.value).toBe(false)

      // Fire change event
      mqMatches = true
      listeners.forEach((cb) => cb({ matches: true }))
      expect(isReduced.value).toBe(true)
    })
    scope.stop()
  })
})
