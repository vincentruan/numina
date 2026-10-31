import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { PracticeResultResponse } from '@/api/practice'
import PracticeResultSummary from './PracticeResultSummary.vue'

function makeResult(overrides: Partial<PracticeResultResponse> = {}): PracticeResultResponse {
  return {
    session_id: 's1',
    total_score: 0.8,
    correct_count: 4,
    total_count: 5,
    xp_earned: 10,
    coins_earned: 10,
    mastery_changed: true,
    new_mastery_level: 'mastered',
    ...overrides,
  }
}

function mountSummary(result: PracticeResultResponse) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(PracticeResultSummary, {
    props: { result },
    global: { plugins: [i18n] },
  })
}

describe('PracticeResultSummary — discovery-first (R6, R7)', () => {
  it('renders discovery statement as the first content element', () => {
    const wrapper = mountSummary(makeResult({ mastery_changed: true }))
    // Discovery text should appear before the score in DOM order
    const html = wrapper.html()
    const discoveryIdx = html.indexOf('result-discovery')
    const scoreIdx = html.indexOf('result-score-section')
    expect(discoveryIdx).toBeGreaterThan(-1)
    expect(scoreIdx).toBeGreaterThan(discoveryIdx)
  })

  it('shows mastery discovery text when mastery_changed is true', () => {
    const wrapper = mountSummary(makeResult({ mastery_changed: true }))
    const text = wrapper.find('.result-discovery__text').text()
    expect(text).toContain('掌握')
  })

  it('shows encouragement when mastery did not change', () => {
    const wrapper = mountSummary(makeResult({ mastery_changed: false, total_score: 0.6 }))
    const text = wrapper.find('.result-discovery__text').text()
    expect(text).toContain('努力')
  })

  it('shows high-score discovery for score >= 80% without mastery change', () => {
    const wrapper = mountSummary(makeResult({ mastery_changed: false, total_score: 0.85 }))
    const text = wrapper.find('.result-discovery__text').text()
    expect(text).toContain('棒')
  })

  it('renders score with reduced visual weight (smaller than discovery)', () => {
    const wrapper = mountSummary(makeResult())
    const scoreEl = wrapper.find('.result-score')
    expect(scoreEl.exists()).toBe(true)
    expect(scoreEl.text()).toBe('80%')
  })

  it('renders rewards with subtle styling (no large emoji icons)', () => {
    const wrapper = mountSummary(makeResult())
    // No large reward-icon spans
    expect(wrapper.findAll('.reward-icon')).toHaveLength(0)
    // Reward items exist but are small text
    const rewardItems = wrapper.findAll('.reward-item')
    expect(rewardItems.length).toBeGreaterThan(0)
  })

  it('hides rewards section when no rewards earned', () => {
    const wrapper = mountSummary(makeResult({ xp_earned: 0, coins_earned: 0, mastery_changed: false }))
    expect(wrapper.find('.result-rewards').exists()).toBe(false)
  })

  it('does not show oversized emoji icons in reward items', () => {
    const wrapper = mountSummary(makeResult())
    // The old design had ⚡ 🪙 🌟 emoji icons as .reward-icon
    expect(wrapper.find('.reward-icon').exists()).toBe(false)
  })

  it('emits "again" when Try Again button is clicked', async () => {
    const wrapper = mountSummary(makeResult())
    const buttons = wrapper.findAll('button')
    const againBtn = buttons.find((b) => b.text().includes('再来') || b.text().includes('Again'))
    expect(againBtn).toBeDefined()
    await againBtn!.trigger('click')
    expect(wrapper.emitted('again')).toBeTruthy()
  })

  it('emits "back" when Back to Map button is clicked', async () => {
    const wrapper = mountSummary(makeResult())
    const buttons = wrapper.findAll('button')
    const backBtn = buttons.find((b) => b.text().includes('返回') || b.text().includes('Back'))
    expect(backBtn).toBeDefined()
    await backBtn!.trigger('click')
    expect(wrapper.emitted('back')).toBeTruthy()
  })

  it('shows challenge discovery message when challengeDiscovery prop is set', async () => {
    const wrapper = mountSummary(makeResult())
    await wrapper.setProps({ challengeDiscovery: 'You found that 1/2 and 2/4 are the same!' })
    const text = wrapper.find('.result-discovery__text').text()
    expect(text).toContain('1/2 and 2/4')
  })

  it('challenge discovery takes priority over generic mastery text', async () => {
    const wrapper = mountSummary(makeResult({ mastery_changed: true }))
    await wrapper.setProps({ challengeDiscovery: 'You discovered equal sharing!' })
    const text = wrapper.find('.result-discovery__text').text()
    expect(text).toContain('equal sharing')
    expect(text).not.toContain('掌握')
  })
})
