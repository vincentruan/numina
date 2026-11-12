import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import type { RecommendResponse } from '@/api/practice'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import DiagnosisCard from './DiagnosisCard.vue'

function i18n(locale = 'zh-CN') {
  return createI18n({
    legacy: false,
    locale,
    fallbackLocale: 'en-US',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

const candidate: RecommendResponse = {
  topic_id: '1001',
  topic_name: 'Common Denominator',
  topic_name_zh: '通分',
  mastery_level: 'learning',
  accuracy: 0.3,
  is_prerequisite: true,
  prerequisite_of_topic_id: '2001',
  is_diagnosis: true,
  depth: 2,
  bkt_mastery: 0.35,
  sample_size: 5,
}

describe('DiagnosisCard', () => {
  it('renders card with prerequisite and target names (zh-CN)', () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate,
        targetTopicName: 'Fractions Addition',
        targetTopicNameZh: '分数加法',
      },
      global: { plugins: [i18n('zh-CN')] },
    })
    expect(wrapper.find('[data-test="diagnosis-card"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('通分')
    expect(wrapper.text()).toContain('分数加法')
    expect(wrapper.text()).toContain('5')
  })

  it('falls back to English name when locale is en-US', () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate,
        targetTopicName: 'Fractions Addition',
        targetTopicNameZh: '分数加法',
      },
      global: { plugins: [i18n('en-US')] },
    })
    expect(wrapper.text()).toContain('Common Denominator')
    expect(wrapper.text()).toContain('Fractions Addition')
  })

  it('emits practiceFirst event when primary button clicked', async () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate,
        targetTopicName: 'T',
        targetTopicNameZh: '中',
      },
      global: { plugins: [i18n()] },
    })
    await wrapper.find('[data-test="practice-first-btn"]').trigger('click')
    expect(wrapper.emitted('practiceFirst')).toHaveLength(1)
  })

  it('emits continue event when ghost button clicked', async () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate,
        targetTopicName: 'T',
        targetTopicNameZh: '中',
      },
      global: { plugins: [i18n()] },
    })
    await wrapper.find('[data-test="continue-btn"]').trigger('click')
    expect(wrapper.emitted('continue')).toHaveLength(1)
  })

  it('renders nothing when candidate is null', () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate: null,
        targetTopicName: 'T',
        targetTopicNameZh: '中',
      },
      global: { plugins: [i18n()] },
    })
    expect(wrapper.find('[data-test="diagnosis-card"]').exists()).toBe(false)
  })

  it('renders nothing when target name is not resolved', () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate,
        targetTopicName: null,
        targetTopicNameZh: null,
      },
      global: { plugins: [i18n()] },
    })
    expect(wrapper.find('[data-test="diagnosis-card"]').exists()).toBe(false)
  })

  it('has every diagnosis key in both locales', () => {
    const keys = ['title', 'evidence', 'practiceFirst', 'continue']
    for (const messages of [zhCN, enUS] as Record<string, unknown>[]) {
      const diagnosis = (messages.practice as Record<string, unknown>).diagnosis as
        | Record<string, string>
        | undefined
      expect(diagnosis, 'practice.diagnosis namespace').toBeTruthy()
      for (const key of keys) {
        expect(diagnosis?.[key], `practice.diagnosis.${key}`).toBeTruthy()
      }
    }
  })

  it('never shows the mastery number or depth to the child', () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate: { ...candidate, bkt_mastery: 0.35, depth: 2 },
        targetTopicName: 'T',
        targetTopicNameZh: '中',
      },
      global: { plugins: [i18n()] },
    })
    const text = wrapper.text()
    expect(text).not.toContain('0.35')
    expect(text).not.toContain('35%')
    expect(text).not.toContain('2 层')
  })

  it('has an aria-live polite region for screen readers', () => {
    const wrapper = mount(DiagnosisCard, {
      props: {
        candidate,
        targetTopicName: 'T',
        targetTopicNameZh: '中',
      },
      global: { plugins: [i18n()] },
    })
    const card = wrapper.find('[data-test="diagnosis-card"]')
    expect(card.attributes('aria-live')).toBe('polite')
    expect(card.attributes('role')).toBe('status')
  })
})
