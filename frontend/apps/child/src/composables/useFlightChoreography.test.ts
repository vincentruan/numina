import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { effectScope } from 'vue'

vi.mock('./useReducedMotion', () => {
  return {
    useReducedMotion: vi.fn(),
  }
})

vi.mock('./useHaptic', () => {
  return {
    tryVibrate: vi.fn(() => true),
  }
})

import { useFlightChoreography } from './useFlightChoreography'
import { useReducedMotion } from './useReducedMotion'
import { tryVibrate } from './useHaptic'
import { ref } from 'vue'

const mockReduced = vi.mocked(useReducedMotion)
const mockVibrate = vi.mocked(tryVibrate)

function makeOpts(overrides: Partial<Parameters<ReturnType<typeof useFlightChoreography>['run']>[0]> = {}) {
  return {
    origins: [{ x: 0, y: 0 }],
    target: { x: 100, y: 100 },
    starsEarned: 5,
    taskCount: 1,
    reducedMotionToast: vi.fn(),
    onBalanceReact: vi.fn(),
    onBalanceReactEnd: vi.fn(),
    onComplete: vi.fn(),
    ...overrides,
  }
}

describe('useFlightChoreography', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockReduced.mockReturnValue(ref(false))
    mockVibrate.mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('reduced-motion: fires toast + invert + completes after 2500ms; never reacts pop', async () => {
    mockReduced.mockReturnValue(ref(true))
    const scope = effectScope()
    const { run, phase } = scope.run(() => useFlightChoreography())!
    const opts = makeOpts()
    run(opts)
    expect(opts.reducedMotionToast).toHaveBeenCalledWith(5)
    expect(opts.onBalanceReact).toHaveBeenCalledWith('invert')
    expect(opts.onBalanceReact).not.toHaveBeenCalledWith('pop')
    expect(phase.value).toBe('reduced-flash')

    await vi.advanceTimersByTimeAsync(2600)
    expect(opts.onComplete).toHaveBeenCalled()
    expect(phase.value).toBe('done')
    scope.stop()
  })

  it('normal path: notifyLanding fires haptic + onBalanceReact("pop") on first landing only', () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const opts = makeOpts()
    choreo.run(opts)
    expect(opts.onBalanceReact).not.toHaveBeenCalled()

    choreo.notifyLanding({ x: 0, y: 0 }, { x: 100, y: 100 })
    expect(mockVibrate).toHaveBeenCalledTimes(1)
    expect(opts.onBalanceReact).toHaveBeenCalledTimes(1)
    expect(opts.onBalanceReact).toHaveBeenCalledWith('pop')
    expect(choreo.phase.value).toBe('glow')

    choreo.notifyLanding({ x: 0, y: 0 }, { x: 100, y: 100 })
    expect(mockVibrate).toHaveBeenCalledTimes(2)
    expect(opts.onBalanceReact).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('notifyAllLanded schedules breathing then complete', async () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const opts = makeOpts()
    choreo.run(opts)
    choreo.notifyLanding({ x: 0, y: 0 }, { x: 100, y: 100 })
    choreo.notifyAllLanded()

    await vi.advanceTimersByTimeAsync(700)
    expect(opts.onBalanceReactEnd).toHaveBeenCalled()
    expect(choreo.phase.value).toBe('breathing')

    await vi.advanceTimersByTimeAsync(3500)
    expect(opts.onComplete).toHaveBeenCalled()
    expect(choreo.phase.value).toBe('done')
    scope.stop()
  })

  it('notifyLanding invokes onLandingTrail with a valid SVG path string', () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const onLandingTrail = vi.fn()
    const opts = makeOpts({ onLandingTrail })
    choreo.run(opts)

    choreo.notifyLanding({ x: 0, y: 0 }, { x: 100, y: 50 })
    expect(onLandingTrail).toHaveBeenCalledTimes(1)
    const path = onLandingTrail.mock.calls[0][0]
    expect(path).toMatch(/^M /)
    expect(path).toContain(' Q ')

    choreo.notifyLanding({ x: 0, y: 0 }, { x: 100, y: 50 })
    expect(onLandingTrail).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('notifyLanding skips onLandingTrail when callback omitted', () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const opts = makeOpts({ onLandingTrail: undefined })
    expect(() => {
      choreo.run(opts)
      choreo.notifyLanding({ x: 0, y: 0 }, { x: 100, y: 50 })
    }).not.toThrow()
    scope.stop()
  })

  it('watchdog timeout completes orchestrator if notifyAllLanded never fires', async () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const opts = makeOpts()
    choreo.run(opts)
    expect(opts.onComplete).not.toHaveBeenCalled()

    // Simulate a stuck FlyToTarget: no landings ever, no allLanded ever.
    await vi.advanceTimersByTimeAsync(10001)
    expect(opts.onComplete).toHaveBeenCalledTimes(1)
    expect(opts.onBalanceReactEnd).toHaveBeenCalled()
    expect(choreo.phase.value).toBe('done')
    scope.stop()
  })

  it('cancel mid-flight clears timers and triggers onComplete once', () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const opts = makeOpts()
    choreo.run(opts)
    choreo.notifyLanding({ x: 0, y: 0 }, { x: 100, y: 100 })
    choreo.cancel()
    expect(opts.onComplete).toHaveBeenCalledTimes(1)
    expect(choreo.phase.value).toBe('idle')
    scope.stop()
  })

  it('cancel() also unhooks the 10s watchdog so it cannot double-complete', async () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const opts = makeOpts()
    choreo.run(opts)
    choreo.cancel()
    expect(opts.onComplete).toHaveBeenCalledTimes(1)
    // Advance past the watchdog horizon; onComplete must not be called a second time.
    await vi.advanceTimersByTimeAsync(11000)
    expect(opts.onComplete).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('null target completes immediately without flight', () => {
    const scope = effectScope()
    const choreo = scope.run(() => useFlightChoreography())!
    const opts = makeOpts({ target: null })
    choreo.run(opts)
    expect(opts.onComplete).toHaveBeenCalled()
    expect(choreo.phase.value).toBe('done')
    scope.stop()
  })
})
