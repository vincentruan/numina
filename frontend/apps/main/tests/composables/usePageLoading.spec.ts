import { describe, expect, it, vi, beforeEach } from 'vitest'
import { defineComponent, h, KeepAlive, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'

// Mock NProgress at the top level to ensure it's mocked even when the real
// usePageLoading module is loaded via vi.importActual (which bypasses setup.ts mocks)
vi.mock('nprogress', () => ({
  default: {
    start: vi.fn(),
    done: vi.fn(),
    configure: vi.fn(),
    isStarted: vi.fn(() => false),
    status: vi.fn(),
  },
}))
vi.mock('nprogress/nprogress.css', () => ({ default: {} }))

// Import the mocked NProgress for assertions
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

  it('should reset loadingCount when KeepAlive deactivates a component with pending work', async () => {
    const source = await vi.importActual<any>('../../src/composables/usePageLoading')

    // CompA: calls increment() in onMounted (simulates async fetch still in-flight)
    const CompA = defineComponent({
      name: 'CompA',
      setup() {
        const { increment } = source.usePageLoading()
        increment() // Pending async work — no matching decrement yet
      },
      render: () => h('div', 'A'),
    })

    // CompB: no loading work
    const CompB = defineComponent({
      name: 'CompB',
      render: () => h('div', 'B'),
    })

    // Wrapper: KeepAlive with dynamic component switch
    const Wrapper = defineComponent({
      setup() {
        const current = ref('A')
        return { current }
      },
      render() {
        return h(KeepAlive, { include: ['CompA', 'CompB'] }, [
          this.current === 'A' ? h(CompA) : h(CompB),
        ])
      },
    })

    const wrapper = mount(Wrapper)
    expect(source.globalLoadingCount.value).toBe(1)

    // Switch component: CompA gets deactivated (KeepAlive caches it, no unmount)
    wrapper.vm.current = 'B'
    await nextTick()

    // onDeactivated in usePageLoading should have cleaned up CompA's pending count
    expect(source.globalLoadingCount.value).toBe(0)
    expect(NProgress.done).toHaveBeenCalled()

    wrapper.unmount()
  })
})