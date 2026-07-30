import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
// Vite ?raw import — typed as string by vite/client, works in both vitest and vue-tsc
import roleShimmerSource from './RoleShimmer.vue?raw'

let mqMatches = false

function setupMatchMedia() {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      get matches() { return mqMatches },
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
    })),
  })
}

const VanSkeletonStub = {
  template: '<div class="van-skeleton-stub" />',
  props: ['row', 'rowWidth', 'animate'],
}

describe('RoleShimmer', () => {
  beforeEach(() => {
    mqMatches = false
    setupMatchMedia()
    vi.resetModules()
  })

  it('renders Clay brand-color pulsing rectangles when variant="clay-pulse"', async () => {
    const { default: RoleShimmer } = await import('./RoleShimmer.vue')
    const wrapper = mount(RoleShimmer, {
      props: { variant: 'clay-pulse' },
    })

    expect(wrapper.find('.clay-pulse-root').exists()).toBe(true)
    const bars = wrapper.findAll('.shimmer-bar')
    expect(bars).toHaveLength(3)

    // Each bar uses a distinct Clay brand-color CSS class
    expect(bars[0].classes()).toContain('bar-pink')
    expect(bars[1].classes()).toContain('bar-ochre')
    expect(bars[2].classes()).toContain('bar-teal')
    wrapper.unmount()
  })

  it('renders van-skeleton when variant="skeleton"', async () => {
    const { default: RoleShimmer } = await import('./RoleShimmer.vue')
    const wrapper = mount(RoleShimmer, {
      props: { variant: 'skeleton' },
      global: { stubs: { VanSkeleton: VanSkeletonStub } },
    })

    // Should NOT render clay-pulse bars
    expect(wrapper.find('.clay-pulse-root').exists()).toBe(false)
    // Should render the van-skeleton stub
    expect(wrapper.find('.van-skeleton-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('defaults to skeleton variant when no prop is passed', async () => {
    const { default: RoleShimmer } = await import('./RoleShimmer.vue')
    const wrapper = mount(RoleShimmer, {
      global: { stubs: { VanSkeleton: VanSkeletonStub } },
    })

    expect(wrapper.find('.clay-pulse-root').exists()).toBe(false)
    expect(wrapper.find('.van-skeleton-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('animation duration is <= 2000ms (interaction hard cap)', async () => {
    // CSS animation values are static source-level declarations that happy-dom
    // cannot resolve via getComputedStyle. We verify by reading the .vue source.
    const pulseMatch = roleShimmerSource.match(/animation:\s*clay-pulse\s+(\d+)ms/)
    expect(pulseMatch).not.toBeNull()
    const duration = Number(pulseMatch![1])
    expect(duration).toBeLessThanOrEqual(2000)
    expect(duration).toBeGreaterThan(0)
  })

  it('degrades to fade animation under prefers-reduced-motion: reduce', async () => {
    mqMatches = true
    vi.resetModules()
    const { default: RoleShimmer } = await import('./RoleShimmer.vue')
    const wrapper = mount(RoleShimmer, {
      props: { variant: 'clay-pulse' },
    })

    // The reduced-motion class should be applied to the root element
    const root = wrapper.find('.clay-pulse-root')
    expect(root.classes()).toContain('reduced-motion')

    // Verify the fade animation CSS exists in the source (happy-dom cannot
    // resolve Vue scoped styles, so we verify at the source level).
    expect(roleShimmerSource).toContain('clay-fade')
    const fadeMatch = roleShimmerSource.match(/animation:\s*clay-fade\s+(\d+)ms/)
    expect(fadeMatch).not.toBeNull()
    expect(Number(fadeMatch![1])).toBeLessThanOrEqual(2000)
    wrapper.unmount()
  })

  it('respects dark mode (no inline styles, CSS-class-driven)', async () => {
    const { default: RoleShimmer } = await import('./RoleShimmer.vue')
    const wrapper = mount(RoleShimmer, {
      props: { variant: 'clay-pulse' },
    })

    // All bars use CSS classes for their background — no inline style attributes.
    // This ensures dark mode token overrides via [data-theme="dark"] work correctly
    // (inline styles would beat CSS variable specificity).
    const bars = wrapper.findAll('.shimmer-bar')
    for (const bar of bars) {
      expect(bar.attributes('style')).toBeUndefined()
    }

    // Each bar references a Clay brand token via its CSS class
    expect(bars[0].classes()).toContain('bar-pink')
    expect(bars[1].classes()).toContain('bar-ochre')
    expect(bars[2].classes()).toContain('bar-teal')
    wrapper.unmount()
  })
})
