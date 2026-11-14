import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { PatternChallenge } from '@/types/learning-challenge'
import PatternChallengeComponent from '../PatternChallenge.vue'

const CONFIG_ID = 'pattern-test'

function makeConfig(overrides: Partial<PatternChallenge> = {}): PatternChallenge {
  return {
    id: CONFIG_ID,
    topicId: 't1',
    type: 'pattern',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'What comes next?',
    scenarioZh: '下一个是什么？',
    discoveryMessage: 'You found the pattern!',
    discoveryMessageZh: '你找到规律啦！',
    sequence: [
      { id: 's1', label: '🔵', icon: '🔵' },
      { id: 's2', label: '🔴', icon: '🔴' },
      { id: 's3', label: '🔵', icon: '🔵' },
    ],
    options: [
      { id: 'o1', label: '🔴', icon: '🔴' },
      { id: 'o2', label: '🔵', icon: '🔵' },
      { id: 'o3', label: '🟡', icon: '🟡' },
    ],
    correctAnswer: 'o1',
    ...overrides,
  }
}

function mountPattern(config: PatternChallenge = makeConfig(), locale = 'en-US') {
  const i18n = createI18n({
    legacy: false,
    locale,
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(PatternChallengeComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

async function chooseAndCheck(wrapper: ReturnType<typeof mountPattern>, optionIndex: number) {
  await wrapper.findAll('.pattern-option')[optionIndex].trigger('click')
  await wrapper.find('.challenge-check-btn').trigger('click')
  await nextTick()
}

describe('PatternChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders the sequence with a blank slot for the answer', () => {
    const wrapper = mountPattern()
    expect(wrapper.findAll('.pattern-sequence__item')).toHaveLength(4)
    expect(wrapper.find('.pattern-sequence__item--blank').exists()).toBe(true)
  })

  it('renders every candidate option', () => {
    const wrapper = mountPattern()
    expect(wrapper.findAll('.pattern-option')).toHaveLength(3)
  })

  it('tapping an option selects it, tapping again deselects', async () => {
    const wrapper = mountPattern()
    const first = wrapper.findAll('.pattern-option')[0]
    await first.trigger('click')
    expect(first.classes()).toContain('pattern-option--selected')
    await first.trigger('click')
    expect(first.classes()).not.toContain('pattern-option--selected')
  })

  it('picking the correct answer yields a correct verdict', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 0) // o1 = correctAnswer
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('You found the pattern!')
  })

  it('picking the neighbouring option yields a close verdict, not wrong', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 1) // o2 sits next to o1
    expect(wrapper.find('.challenge-feedback__message--close').exists()).toBe(true)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(false)
  })

  it('picking a distant option yields a wrong verdict', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 2) // o3 is two away from o1
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('renders the judge hint after a close verdict', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 1)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Almost!')
  })

  it('renders the judge hint after a wrong verdict', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 2)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Look at the first few')
  })

  it('keeps the check button after a wrong attempt so the child can retry', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 2)
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(true)
  })

  it('unlocks continue after two attempts without a correct answer', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 2)
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(false)
    // Toggle the selection off and back on so the second check actually runs
    await wrapper.findAll('.pattern-option')[2].trigger('click')
    await chooseAndCheck(wrapper, 2)
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(true)
  })

  it('emits complete when continue is tapped', async () => {
    const wrapper = mountPattern()
    await chooseAndCheck(wrapper, 0)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('restores the selection and verdict after remount', async () => {
    const config = makeConfig()
    const first = mountPattern(config)
    await chooseAndCheck(first, 2)
    await nextTick()

    const second = mountPattern(config)
    expect(second.findAll('.pattern-option')[2].classes()).toContain('pattern-option--selected')
    expect(second.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('clears persisted state on continue', async () => {
    const config = makeConfig()
    const wrapper = mountPattern(config)
    await chooseAndCheck(wrapper, 0)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
