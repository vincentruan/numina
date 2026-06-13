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

  it('renders specular highlight when motion is allowed', async () => {
    mqMatches = false
    const { default: SilverCoin } = await import('./SilverCoin.vue')
    const wrapper = mount(SilverCoin)
    expect(wrapper.find('[data-test="silver-specular"]').exists()).toBe(true)
  })

  it('omits specular highlight when prefers-reduced-motion is set', async () => {
    mqMatches = true
    const { default: SilverCoin } = await import('./SilverCoin.vue')
    const wrapper = mount(SilverCoin)
    expect(wrapper.find('[data-test="silver-specular"]').exists()).toBe(false)
  })

  it('always renders the static star coin structure regardless of motion preference', async () => {
    mqMatches = true
    const { default: SilverCoin } = await import('./SilverCoin.vue')
    const wrapper = mount(SilverCoin)
    const html = wrapper.html()
    // New xingxing.svg-based structure
    expect(html).toContain('class="coin-ring-shadow"')
    expect(html).toContain('class="coin-face"')
    expect(html).toContain('class="star-main"')
    expect(html).toContain('class="star-highlight"')
  })
})