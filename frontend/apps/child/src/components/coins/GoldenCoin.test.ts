import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

describe('GoldenCoin reduced-motion gating', () => {
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

  it('renders specular highlight and sparkles when motion is allowed', async () => {
    mqMatches = false
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    expect(wrapper.find('[data-test="gold-specular"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="gold-sparkles"]').exists()).toBe(true)
  })

  it('omits specular highlight and sparkles when prefers-reduced-motion is set', async () => {
    mqMatches = true
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    expect(wrapper.find('[data-test="gold-specular"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="gold-sparkles"]').exists()).toBe(false)
  })

  it('always renders the static star coin structure regardless of motion preference', async () => {
    mqMatches = true
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    const html = wrapper.html()
    // New xingxing.svg-based structure
    expect(html).toContain('class="coin-ring-shadow"')
    expect(html).toContain('class="coin-face"')
    expect(html).toContain('class="star-main"')
    expect(html).toContain('class="star-highlight"')
  })
})