import { describe, expect, it, vi, beforeEach } from 'vitest'
import NProgress from 'nprogress'

describe('usePageLoading fix verification', () => {
  beforeEach(async () => {
    const source = await vi.importActual<any>('../../src/composables/usePageLoading')
    source._resetForTesting()
    vi.clearAllMocks()
  })

  it('completeGlobalLoading should unconditionally call NProgress.done()', async () => {
    const source = await vi.importActual<any>('../../src/composables/usePageLoading')
    expect(source.completeGlobalLoading).toBeDefined()
    expect(typeof source.completeGlobalLoading).toBe('function')
    source.completeGlobalLoading()
    expect(NProgress.done).toHaveBeenCalled()
  })

  it('usePageLoading complete should unconditionally call NProgress.done()', async () => {
    const source = await vi.importActual<any>('../../src/composables/usePageLoading')
    const { complete } = source.usePageLoading()
    complete()
    expect(NProgress.done).toHaveBeenCalled()
  })

  it('globalLoadingCount should reset to 0 after completeGlobalLoading', async () => {
    const source = await vi.importActual<any>('../../src/composables/usePageLoading')
    source.completeGlobalLoading()
    expect(source.globalLoadingCount.value).toBe(0)
  })

  it('should trigger stuck loading safety timeout after 5s', async () => {
    vi.useFakeTimers()
    const source = await vi.importActual<any>('../../src/composables/usePageLoading')
    const { increment } = source.usePageLoading()

    increment()
    expect(source.globalLoadingCount.value).toBe(1)
    expect(NProgress.start).toHaveBeenCalled()

    // Fast-forward time to 5000ms
    vi.advanceTimersByTime(5000)

    // globalLoadingCount should be reset to 0 and NProgress.done should have been called
    expect(source.globalLoadingCount.value).toBe(0)
    expect(NProgress.done).toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('should clear stuck loading safety timeout when loading finishes within 5s', async () => {
    vi.useFakeTimers()
    const source = await vi.importActual<any>('../../src/composables/usePageLoading')
    const { increment, decrement } = source.usePageLoading()

    increment()
    expect(source.globalLoadingCount.value).toBe(1)

    // Fast-forward 2 seconds
    vi.advanceTimersByTime(2000)
    expect(source.globalLoadingCount.value).toBe(1)

    // Finish loading
    decrement()
    expect(source.globalLoadingCount.value).toBe(0)
    expect(NProgress.done).toHaveBeenCalled()

    // Clear done mock calls to see if the timeout calls done again
    vi.clearAllMocks()

    // Fast-forward remaining time (another 3 seconds)
    vi.advanceTimersByTime(3000)

    // NProgress.done should NOT have been called again because timeout was cleared
    expect(NProgress.done).not.toHaveBeenCalled()
    vi.useRealTimers()
  })
})