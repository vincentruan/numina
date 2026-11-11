import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { HookQuestionResponse } from '@/api/learning'
import TopicHookQuestion from './TopicHookQuestion.vue'

function makeQuestion(overrides: Partial<HookQuestionResponse> = {}): HookQuestionResponse {
  return {
    id: '1',
    topic_id: '100',
    question_text: 'Why can’t you combine pieces from a cake cut 3 ways with pieces cut 4 ways?',
    question_text_zh: '为什么蛋糕切 3 刀和切 4 刀不能直接合在一起？',
    age_group: 'mid',
    difficulty: 'medium',
    review_status: 'approved',
    ...overrides,
  }
}

function mountHook(
  question: HookQuestionResponse = makeQuestion(),
  locale = 'en-US',
) {
  const i18n = createI18n({
    legacy: false,
    locale,
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(TopicHookQuestion, {
    props: { question },
    global: { plugins: [i18n] },
  })
}

describe('TopicHookQuestion (#200)', () => {
  it('renders the English question text', () => {
    const wrapper = mountHook()
    expect(wrapper.find('.hook-question__text').text()).toContain('cake cut 3 ways')
  })

  it('renders the Chinese question when locale is zh-CN', () => {
    const wrapper = mountHook(makeQuestion(), 'zh-CN')
    expect(wrapper.find('.hook-question__text').text()).toContain('蛋糕切 3 刀')
  })

  it('falls back to English text when zh translation is missing', () => {
    const wrapper = mountHook(makeQuestion({ question_text_zh: null }), 'zh-CN')
    expect(wrapper.find('.hook-question__text').text()).toContain('cake cut 3 ways')
  })

  it('shows the "think about it" prompt', () => {
    const wrapper = mountHook()
    expect(wrapper.find('.hook-question__label').text().length).toBeGreaterThan(0)
  })

  it('emits skip when the skip button is clicked', async () => {
    const wrapper = mountHook()
    await wrapper.find('.hook-question__skip').trigger('click')
    expect(wrapper.emitted('skip')).toHaveLength(1)
  })

  it('skip button is a semantic <button> for keyboard access', () => {
    const wrapper = mountHook()
    const skip = wrapper.find('.hook-question__skip')
    expect(skip.element.tagName).toBe('BUTTON')
  })
})
