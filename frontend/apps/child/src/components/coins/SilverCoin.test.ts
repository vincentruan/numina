import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

describe('SilverCoin reduced-motion gating', () => {
  let mqMatches: boolean

  beforeEach(() => {
    mqMatches = false
    vi.resetModules()
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        get matches() {
          return mqMatches
        },
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
        media: '(prefers-reduced-motion: reduce)',
        onchange: null,
      })),
    })
  })

  it('renders the breathing animate element when motion is allowed', async () => {
    mqMatches = false
    const { default: SilverCoin } = await import('./SilverCoin.vue')
    const wrapper = mount(SilverCoin)
    expect(wrapper.find('[data-test="silver-arc"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="silver-arc-animate"]').exists()).toBe(true)
  })

  it('omits the animate element but keeps the static arc when prefers-reduced-motion is set', async () => {
    mqMatches = true
    const { default: SilverCoin } = await import('./SilverCoin.vue')
    const wrapper = mount(SilverCoin)
    const arc = wrapper.find('[data-test="silver-arc"]')
    expect(arc.exists()).toBe(true)
    expect(arc.attributes('opacity')).toBe('0.55')
    expect(wrapper.find('[data-test="silver-arc-animate"]').exists()).toBe(false)
  })
})
