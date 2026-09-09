import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, ref, h, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { useScrollReveal } from '../useScrollReveal'

// Mock IntersectionObserver — must be a class (not arrow fn) for `new` to work
const mockObserve = vi.fn()
const mockUnobserve = vi.fn()
const mockDisconnect = vi.fn()
let observerCallback: (entries: Array<{ target: Element; isIntersecting: boolean }>) => void

class MockIntersectionObserver {
  constructor(cb: typeof observerCallback) {
    observerCallback = cb
  }
  observe = mockObserve
  unobserve = mockUnobserve
  disconnect = mockDisconnect
}

vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)

// Mock matchMedia
function setupMatchMedia(reducedMotion = false) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? reducedMotion : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  )
}

// Helper: create a test component that uses the composable
function createTestComponent(children: string) {
  return defineComponent({
    setup() {
      const container = ref<HTMLElement | null>(null)
      useScrollReveal(container)
      return { container }
    },
    template: `<div ref="container">${children}</div>`,
  })
}

describe('useScrollReveal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupMatchMedia(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('creates observer and observes [data-reveal] elements on mount', async () => {
    const wrapper = mount(createTestComponent('<p data-reveal></p><p data-reveal></p>'))
    await nextTick()

    expect(mockObserve).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })

  it('adds revealed class and unobserves on intersection', async () => {
    const wrapper = mount(createTestComponent('<p data-reveal></p>'))
    await nextTick()

    const p = wrapper.find('p').element
    observerCallback([{ target: p, isIntersecting: true }])

    expect(p.classList.contains('revealed')).toBe(true)
    expect(mockUnobserve).toHaveBeenCalledWith(p)
    wrapper.unmount()
  })

  it('does NOT create observer when prefers-reduced-motion is reduce', async () => {
    setupMatchMedia(true)

    const wrapper = mount(createTestComponent('<p data-reveal></p>'))
    await nextTick()

    expect(mockObserve).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('does nothing when container has no [data-reveal] elements', async () => {
    const wrapper = mount(createTestComponent('<p>no reveal</p>'))
    await nextTick()

    expect(mockObserve).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('disconnects observer on unmount', async () => {
    const wrapper = mount(createTestComponent('<p data-reveal></p>'))
    await nextTick()

    expect(mockObserve).toHaveBeenCalled()
    wrapper.unmount()

    expect(mockDisconnect).toHaveBeenCalled()
  })

  it('does nothing when container ref is null', async () => {
    const Component = defineComponent({
      setup() {
        const container = ref<HTMLElement | null>(null)
        useScrollReveal(container)
        return { container }
      },
      // No template — container ref stays null
      render: () => h('div'),
    })

    const wrapper = mount(Component)
    await nextTick()

    expect(mockObserve).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
