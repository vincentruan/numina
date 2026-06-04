import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AiArtifactBadge from './AiArtifactBadge.vue'
import { createI18n } from 'vue-i18n'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiArtifact: {
        badgeLabel: '查看 {count} 个附件',
      },
    },
  },
})

describe('AiArtifactBadge', () => {
  it('R1: badge visible when count > 0', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 1 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.artifact-badge-btn').exists()).toBe(true)
    expect(wrapper.isVisible()).toBe(true)
  })

  it('R3: badge hidden when count = 0', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 0 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.artifact-badge-btn').exists()).toBe(false)
  })

  it('R2: count = 5 shows "5" in pill', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 5 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.badge-count').text()).toBe('5')
  })

  it('click triggers tap emit', async () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 3 },
      global: { plugins: [i18n] },
    })
    await wrapper.find('.artifact-badge-btn').trigger('click')
    expect(wrapper.emitted('tap')).toBeTruthy()
    expect(wrapper.emitted('tap').length).toBe(1)
  })

  it('touch target is at least 44×44px', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 2 },
      global: { plugins: [i18n] },
    })
    const btn = wrapper.find('.artifact-badge-btn')
    // Check inline styles for dimensions
    expect(btn.element.style.width).toBe('44px')
    expect(btn.element.style.height).toBe('44px')
  })

  it('aria-label includes count', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 7 },
      global: { plugins: [i18n] },
    })
    const ariaLabel = wrapper.find('.artifact-badge-btn').attributes('aria-label')
    expect(ariaLabel).toContain('7')
    expect(ariaLabel).toContain('附件')
  })

  it('has correct role attribute', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 1 },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.artifact-badge-btn').attributes('role')).toBe('button')
  })

  it('uses CSS variables for styling', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 1 },
      global: { plugins: [i18n] },
    })
    const btn = wrapper.find('.artifact-badge-btn')
    // Verify no inline color styles - should use CSS classes with variables
    expect(btn.element.style.background).toBe('')
    expect(btn.element.style.color).toBe('')
    expect(btn.element.style.borderColor).toBe('')
  })

  it('badge-count pill is positioned correctly', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 10 },
      global: { plugins: [i18n] },
    })
    const pill = wrapper.find('.badge-count')
    // Check pill has absolute positioning
    expect(pill.element.style.position).toBe('absolute')
    expect(pill.element.style.top).toBe('-4px')
    expect(pill.element.style.right).toBe('-4px')
  })
})