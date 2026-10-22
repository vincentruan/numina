import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import DomainSection from '../DomainSection.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      learning: {
        cluster: { progress: '{mastered}/{total} 已掌握' },
        domainSection: { expandSection: '展开', collapseSection: '收起' },
        recommendPath: { hiddenTopics: '{count}' },
      },
    },
  },
})

const defaultProps = {
  domain: 'Addition',
  domainLabel: '加法',
  masteredCount: 2,
  totalCount: 5,
  expanded: false,
}

describe('DomainSection — path count badge', () => {
  it('renders badge when pathCount > 0 and collapsed', () => {
    const wrapper = mount(DomainSection, {
      props: { ...defaultProps, pathCount: 2 },
      slots: { default: '<div>content</div>' },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.domain-section__path-badge').exists()).toBe(true)
    expect(wrapper.find('.domain-section__path-badge').text()).toBe('2')
  })

  it('hides badge when section is expanded', () => {
    const wrapper = mount(DomainSection, {
      props: { ...defaultProps, expanded: true, pathCount: 2 },
      slots: { default: '<div>content</div>' },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.domain-section__path-badge').exists()).toBe(false)
  })

  it('hides badge when pathCount is 0', () => {
    const wrapper = mount(DomainSection, {
      props: { ...defaultProps, pathCount: 0 },
      slots: { default: '<div>content</div>' },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.domain-section__path-badge').exists()).toBe(false)
  })

  it('hides badge when pathCount is undefined', () => {
    const wrapper = mount(DomainSection, {
      props: defaultProps,
      slots: { default: '<div>content</div>' },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.domain-section__path-badge').exists()).toBe(false)
  })

  it('tap on badge area triggers section expand (existing toggle behavior)', async () => {
    const wrapper = mount(DomainSection, {
      props: { ...defaultProps, pathCount: 2 },
      slots: { default: '<div>content</div>' },
      global: { plugins: [i18n] },
    })
    // The badge is inside the header button, so clicking the header triggers toggle
    await wrapper.find('.domain-section__header').trigger('click')
    expect(wrapper.emitted('toggle')).toBeTruthy()
  })
})
