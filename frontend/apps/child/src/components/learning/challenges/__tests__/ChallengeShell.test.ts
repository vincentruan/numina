import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { DistributeChallenge } from '@/types/learning-challenge'
import ChallengeShell from '../ChallengeShell.vue'

function makeConfig(overrides: Partial<DistributeChallenge> = {}): DistributeChallenge {
  return {
    id: 'shell-test',
    topicId: 't1',
    type: 'distribute',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Share 4 cookies between 2 friends.',
    scenarioZh: '把4块饼干分给2个朋友。',
    discoveryMessage: 'You made it fair!',
    discoveryMessageZh: '你分得真公平！',
    objects: [
      { id: 'c1', label: 'Cookie', icon: '🍪' },
      { id: 'c2', label: 'Cookie', icon: '🍪' },
    ],
    zones: [
      { id: 'z1', label: 'A', labelZh: '甲' },
      { id: 'z2', label: 'B', labelZh: '乙' },
    ],
    ...overrides,
  }
}

function mountShell(props: Record<string, unknown> = {}) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(ChallengeShell, {
    props: {
      config: makeConfig(),
      feedbackMessage: '',
      feedbackIsCorrect: false,
      hasAnyPlacement: false,
      completed: false,
      showTutorSuggestion: false,
      statusText: 'Placed 0 / 2',
      ...props,
    },
    slots: {
      default: '<div class="test-interaction">interaction area</div>',
    },
    global: { plugins: [i18n] },
  })
}

describe('ChallengeShell', () => {
  it('renders scenario text from config', () => {
    const wrapper = mountShell()
    expect(wrapper.find('.challenge-scenario__text').text()).toContain('Share 4 cookies')
  })

  it('renders Chinese scenario when locale is zh-CN', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'en-US': enUS, 'zh-CN': zhCN },
    })
    const wrapper = mount(ChallengeShell, {
      props: {
        config: makeConfig(),
        feedbackMessage: '',
        feedbackIsCorrect: false,
        hasAnyPlacement: false,
        completed: false,
        showTutorSuggestion: false,
        statusText: '',
      },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.challenge-scenario__text').text()).toContain('分给2个朋友')
  })

  it('renders slot content in the interaction area', () => {
    const wrapper = mountShell()
    expect(wrapper.find('.test-interaction').exists()).toBe(true)
    expect(wrapper.find('.test-interaction').text()).toBe('interaction area')
  })

  it('shows status text when no feedback message', () => {
    const wrapper = mountShell({ statusText: 'Placed 1 / 4' })
    expect(wrapper.find('.challenge-feedback__status').text()).toBe('Placed 1 / 4')
  })

  it('shows feedback message when present', () => {
    const wrapper = mountShell({ feedbackMessage: 'Almost there!', feedbackIsCorrect: false })
    expect(wrapper.find('.challenge-feedback__message').text()).toBe('Almost there!')
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('shows correct feedback styling when isCorrect is true', () => {
    const wrapper = mountShell({ feedbackMessage: 'Great job!', feedbackIsCorrect: true })
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
  })

  it('renders check button when not completed', () => {
    const wrapper = mountShell({ completed: false })
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(true)
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(false)
  })

  it('renders continue button when completed', () => {
    const wrapper = mountShell({ completed: true })
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(true)
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(false)
  })

  it('check button is disabled when hasAnyPlacement is false', () => {
    const wrapper = mountShell({ hasAnyPlacement: false })
    expect(wrapper.find('.challenge-check-btn').attributes('disabled')).toBeDefined()
  })

  it('check button is enabled when hasAnyPlacement is true', () => {
    const wrapper = mountShell({ hasAnyPlacement: true })
    expect(wrapper.find('.challenge-check-btn').attributes('disabled')).toBeUndefined()
  })

  it('emits check when check button is clicked', async () => {
    const wrapper = mountShell({ hasAnyPlacement: true })
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.emitted('check')).toBeTruthy()
  })

  it('emits continue when continue button is clicked', async () => {
    const wrapper = mountShell({ completed: true })
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('continue')).toBeTruthy()
  })

  it('shows tutor button when showTutorSuggestion is true', () => {
    const wrapper = mountShell({ showTutorSuggestion: true })
    expect(wrapper.find('.challenge-tutor-btn').exists()).toBe(true)
  })

  it('hides tutor button when showTutorSuggestion is false', () => {
    const wrapper = mountShell({ showTutorSuggestion: false })
    expect(wrapper.find('.challenge-tutor-btn').exists()).toBe(false)
  })

  it('emits requestTutor when tutor button is clicked', async () => {
    const wrapper = mountShell({ showTutorSuggestion: true })
    await wrapper.find('.challenge-tutor-btn').trigger('click')
    expect(wrapper.emitted('requestTutor')).toBeTruthy()
  })
})
