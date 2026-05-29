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

  it('renders sheen and sparkles when motion is allowed', async () => {
    mqMatches = false
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    expect(wrapper.find('[data-test="gold-sheen"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="gold-sparkles"]').exists()).toBe(true)
  })

  it('omits sheen and sparkles when prefers-reduced-motion is set', async () => {
    mqMatches = true
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    expect(wrapper.find('[data-test="gold-sheen"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="gold-sparkles"]').exists()).toBe(false)
  })

  it('always renders the static decoration regardless of motion preference', async () => {
    mqMatches = true
    const { default: GoldenCoin } = await import('./GoldenCoin.vue')
    const wrapper = mount(GoldenCoin)
    const html = wrapper.html()
    expect(html).toContain('class="rim-dots"')
    expect(html).toContain('class="highlight-blob"')
    expect(html).toContain('class="inner-ring"')
  })
})
