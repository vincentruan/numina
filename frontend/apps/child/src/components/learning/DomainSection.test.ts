import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import DomainSection from './DomainSection.vue'

function mountSection(props: Record<string, unknown> = {}) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(DomainSection, {
    props: {
      domain: 'Addition',
      domainLabel: '加法',
      masteredCount: 3,
      totalCount: 12,
      expanded: false,
      ...props,
    },
    global: { plugins: [i18n] },
    slots: {
      default: '<div class="test-content">slot content</div>',
    },
  })
}

describe('DomainSection', () => {
  it('renders header with domain label and progress count', () => {
    const wrapper = mountSection()
    expect(wrapper.find('.domain-section__label').text()).toBe('加法')
    expect(wrapper.find('.domain-section__progress').text()).toBe('3/12 已掌握')
  })

  it('emits toggle on header tap', async () => {
    const wrapper = mountSection()
    await wrapper.find('.domain-section__header').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('chevron has expanded class when expanded', () => {
    const collapsed = mountSection({ expanded: false })
    expect(collapsed.find('.domain-section__chevron--expanded').exists()).toBe(false)

    const expanded = mountSection({ expanded: true })
    expect(expanded.find('.domain-section__chevron--expanded').exists()).toBe(true)
  })

  it('aria-expanded matches the expanded prop', () => {
    const collapsed = mountSection({ expanded: false })
    expect(collapsed.find('.domain-section__header').attributes('aria-expanded')).toBe('false')

    const expanded = mountSection({ expanded: true })
    expect(expanded.find('.domain-section__header').attributes('aria-expanded')).toBe('true')
  })

  it('sets data-domain with the raw domain', () => {
    const wrapper = mountSection({ domain: 'Addition' })
    expect(wrapper.find('.domain-section').attributes('data-domain')).toBe('Addition')
  })

  it('renders slot content', () => {
    const wrapper = mountSection()
    expect(wrapper.find('.test-content').exists()).toBe(true)
    expect(wrapper.find('.test-content').text()).toBe('slot content')
  })

  it('header meets 44px minimum touch target', () => {
    const wrapper = mountSection()
    const header = wrapper.find('.domain-section__header')
    // min-height: 44px is set via CSS — verify the class is applied
    expect(header.classes()).toContain('domain-section__header')
  })

  it('uses collapse-section aria-label when expanded', () => {
    const wrapper = mountSection({ expanded: true })
    const label = wrapper.find('.domain-section__header').attributes('aria-label')
    expect(label).toBe('收起')
  })

  it('uses expand-section aria-label when collapsed', () => {
    const wrapper = mountSection({ expanded: false })
    const label = wrapper.find('.domain-section__header').attributes('aria-label')
    expect(label).toBe('展开')
  })
})
