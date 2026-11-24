import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import SubjectTabs from './SubjectTabs.vue'

function mountTabs(tabs: Array<{ subject: string; count: number }>, selected = tabs[0]?.subject ?? '') {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(SubjectTabs, {
    props: { modelValue: selected, tabs },
    global: { plugins: [i18n] },
  })
}

describe('SubjectTabs — badge (#246 A)', () => {
  it.each([0, 9, 99, 358, 1234])('renders the badge for count %i on exactly one line', (count) => {
    const wrapper = mountTabs([{ subject: 'biology', count }])
    const badges = wrapper.findAll('.subject-tab__badge')
    // R1/R3: zero is a real count — the badge must render, not be suppressed.
    expect(badges).toHaveLength(1)
    expect(badges[0].text()).toBe(String(count))
  })

  it('renders a badge for every tab, including a zero-progress subject', () => {
    const wrapper = mountTabs([
      { subject: 'mathematics', count: 0 },
      { subject: 'biology', count: 358 },
    ])
    const texts = wrapper.findAll('.subject-tab__badge').map((b) => b.text())
    expect(texts).toEqual(['0', '358'])
  })

  it('carries no inline sizing or transform on the badge', () => {
    // R1: sizing must come from the stylesheet (content-sized), never from an
    // inline height/transform that would re-pin the capsule. happy-dom has no
    // layout engine, so this asserts the rendered contract, not pixels.
    const wrapper = mountTabs([{ subject: 'biology', count: 358 }])
    const badge = wrapper.find('.subject-tab__badge')
    expect(badge.attributes('style')).toBeUndefined()
  })
})
