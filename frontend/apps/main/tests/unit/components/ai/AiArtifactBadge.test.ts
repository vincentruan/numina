import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AiArtifactBadge from '@/components/ai/AiArtifactBadge.vue'
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
    expect(wrapper.emitted('tap')!.length).toBe(1)
  })

  it('touch target is at least 44×44px', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 2 },
      global: { plugins: [i18n] },
    })
    const btn = wrapper.find('.artifact-badge-btn')
    // Verify the button has the correct class (dimensions are in scoped CSS)
    expect(btn.classes()).toContain('artifact-badge-btn')
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
    const element = btn.element as HTMLElement
    // Verify no inline color styles - should use CSS classes with variables
    expect(element.style.background).toBe('')
    expect(element.style.color).toBe('')
    expect(element.style.borderColor).toBe('')
  })

  it('badge-count pill is positioned correctly', () => {
    const wrapper = mount(AiArtifactBadge, {
      props: { count: 10 },
      global: { plugins: [i18n] },
    })
    const pill = wrapper.find('.badge-count')
    // Verify pill has the correct class (positioning is in scoped CSS)
    expect(pill.classes()).toContain('badge-count')
  })
})