import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { MisconceptionFeedback } from '@/api/practice'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import MisconceptionFeedbackCard from './MisconceptionFeedbackCard.vue'

function i18n(locale = 'zh-CN') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en-US',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

const feedback: MisconceptionFeedback = {
  misconception_id: '1001',
  description: 'Many students add numerators and denominators separately.',
  description_zh: '很多同学会把分子和分母分别相加。',
  diagnostic_question_id: '2001',
  diagnostic_question_stem: 'What is 1/2 + 1/5?',
  diagnostic_question_stem_zh: '1/2 + 1/5 等于多少？',
}

describe('MisconceptionFeedbackCard', () => {
  it('renders card with description (zh-CN)', () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback },
      global: { plugins: [i18n('zh-CN')] },
    })
    expect(wrapper.find('[data-test="misconception-card"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="misconception-description"]').text())
      .toContain('分子和分母分别相加')
    expect(wrapper.text()).toContain('这是一个常见的混淆')
  })

  it('falls back to English description when locale is en-US', () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback },
      global: { plugins: [i18n('en-US')] },
    })
    expect(wrapper.find('[data-test="misconception-description"]').text())
      .toContain('add numerators and denominators')
  })

  it('falls back to English description when description_zh is null (zh-CN)', () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback: { ...feedback, description_zh: null } },
      global: { plugins: [i18n('zh-CN')] },
    })
    expect(wrapper.find('[data-test="misconception-description"]').text())
      .toContain('add numerators and denominators')
  })

  it('shows both buttons when diagnostic question is offered', () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback },
      global: { plugins: [i18n()] },
    })
    expect(wrapper.find('[data-test="misconception-try-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="misconception-skip-btn"]').exists()).toBe(true)
  })

  it('hides both buttons when diagnostic_question_id is null', () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: {
        feedback: {
          ...feedback,
          diagnostic_question_id: null,
          diagnostic_question_stem: null,
          diagnostic_question_stem_zh: null,
        },
      },
      global: { plugins: [i18n()] },
    })
    expect(wrapper.find('[data-test="misconception-try-btn"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="misconception-skip-btn"]').exists()).toBe(false)
  })

  it('emits diagnosticRequested when primary button clicked', async () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback },
      global: { plugins: [i18n()] },
    })
    await wrapper.find('[data-test="misconception-try-btn"]').trigger('click')
    expect(wrapper.emitted('diagnosticRequested')).toHaveLength(1)
  })

  it('emits dismissed when skip button clicked', async () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback },
      global: { plugins: [i18n()] },
    })
    await wrapper.find('[data-test="misconception-skip-btn"]').trigger('click')
    expect(wrapper.emitted('dismissed')).toHaveLength(1)
  })

  it('renders nothing when feedback is null', () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback: null },
      global: { plugins: [i18n()] },
    })
    expect(wrapper.find('[data-test="misconception-card"]').exists()).toBe(false)
  })

  it('has every misconception key in both locales', () => {
    const keys = ['commonConfusion', 'tryPractice', 'notNow']
    for (const messages of [zhCN, enUS] as Record<string, unknown>[]) {
      const misconception = (messages.practice as Record<string, unknown>)
        .misconception as Record<string, string> | undefined
      expect(misconception, 'practice.misconception namespace').toBeTruthy()
      for (const key of keys) {
        expect(misconception?.[key], `practice.misconception.${key}`).toBeTruthy()
      }
    }
  })

  it('has an aria-live polite region for screen readers', () => {
    const wrapper = mount(MisconceptionFeedbackCard, {
      props: { feedback },
      global: { plugins: [i18n()] },
    })
    const card = wrapper.find('[data-test="misconception-card"]')
    expect(card.attributes('aria-live')).toBe('polite')
    expect(card.attributes('role')).toBe('status')
  })
})
