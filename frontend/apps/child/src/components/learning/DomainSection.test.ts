import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
// Vite ?raw import — typed as string by vite/client, works in both vitest and vue-tsc
import domainSectionSource from './DomainSection.vue?raw'
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
    // happy-dom does not cascade the component's scoped stylesheet, so assert
    // the rule itself — a regression that drops min-height fails here.
    expect(domainSectionSource).toMatch(
      /\.domain-section__header\s*\{[^}]*min-height:\s*44px/,
    )
    expect(header.classes()).toContain('domain-section__header')
  })

  it('uses collapse-section aria-label when expanded', () => {
    const wrapper = mountSection({ expanded: true })
    const label = wrapper.find('.domain-section__header').attributes('aria-label')
    expect(label).toBe('加法，收起')
  })

  it('uses expand-section aria-label when collapsed', () => {
    const wrapper = mountSection({ expanded: false })
    const label = wrapper.find('.domain-section__header').attributes('aria-label')
    expect(label).toBe('加法，展开')
  })

  it('names each section by its own domain, so headers are distinguishable', () => {
    const addition = mountSection({ domainLabel: '加法', expanded: false })
    const multiplication = mountSection({ domainLabel: '乘法', expanded: false })
    const a = addition.find('.domain-section__header').attributes('aria-label')
    const m = multiplication.find('.domain-section__header').attributes('aria-label')
    expect(a).not.toBe(m)
    expect(a).toContain('加法')
    expect(m).toContain('乘法')
  })

  it('hides collapsed content from assistive tech and the tab order', () => {
    const collapsed = mountSection({ expanded: false })
    expect(
      collapsed.find('.domain-section__collapse-wrapper').attributes('inert'),
    ).toBeDefined()

    const expanded = mountSection({ expanded: true })
    expect(
      expanded.find('.domain-section__collapse-wrapper').attributes('inert'),
    ).toBeUndefined()
  })

  it('skips the height transition when expanded programmatically', () => {
    const instant = mountSection({ expanded: true, instant: true })
    expect(
      instant.find('.domain-section__header').classes(),
    ).toContain('domain-section__header--instant')
  })
})
