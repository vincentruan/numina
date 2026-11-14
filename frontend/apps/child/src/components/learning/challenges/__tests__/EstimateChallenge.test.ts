import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { EstimateChallenge } from '@/types/learning-challenge'
import EstimateComponent from '../EstimateChallenge.vue'

function makeConfig(overrides: Partial<EstimateChallenge> = {}): EstimateChallenge {
  return {
    id: 'estimate-test',
    topicId: 't1',
    type: 'estimate',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'About how many beans are in the jar?',
    scenarioZh: '这个罐子里大概有多少颗豆子？',
    discoveryMessage: 'Great estimate!',
    discoveryMessageZh: '估得真准！',
    startValue: 0,
    step: 10,
    targetValue: 100,
    narrowTolerance: 10,
    wideTolerance: 30,
    unitLabel: 'beans',
    unitLabelZh: '颗',
    ...overrides,
  }
}

function mountEstimate(overrides: Partial<EstimateChallenge> = {}) {
  const config = makeConfig(overrides)
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(EstimateComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

async function stepTo(wrapper: ReturnType<typeof mountEstimate>, target: number) {
  const stepButtons = wrapper.findAll('.estimate-step')
  const plus = stepButtons[1]
  const current = Number(wrapper.find('.estimate-value__number').text())
  const steps = (target - current) / 10
  for (let i = 0; i < Math.abs(steps); i++) {
    await (steps > 0 ? plus : stepButtons[0]).trigger('click')
  }
}

async function check(wrapper: ReturnType<typeof mountEstimate>) {
  await wrapper.find('.challenge-check-btn').trigger('click')
  await nextTick()
}

describe('EstimateChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('starts at the configured start value', () => {
    const wrapper = mountEstimate()
    expect(wrapper.find('.estimate-value__number').text()).toBe('0')
  })

  it('tapping + increases the value by the step', async () => {
    const wrapper = mountEstimate()
    await wrapper.findAll('.estimate-step')[1].trigger('click')
    expect(wrapper.find('.estimate-value__number').text()).toBe('10')
  })

  it('tapping − decreases the value', async () => {
    // Distinct id: a shared id would restore another test's persisted value
    const wrapper = mountEstimate({ id: 'estimate-minus-test', startValue: 50 })
    expect(wrapper.find('.estimate-value__number').text()).toBe('50')
    await wrapper.findAll('.estimate-step')[0].trigger('click')
    expect(wrapper.find('.estimate-value__number').text()).toBe('40')
  })

  it('a value inside the narrow tolerance yields correct', async () => {
    const wrapper = mountEstimate()
    await stepTo(wrapper, 100)
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('Great estimate!')
  })

  it('a value inside the wide tolerance but outside narrow yields close', async () => {
    const wrapper = mountEstimate()
    await stepTo(wrapper, 120) // 20 away: > 10 narrow, <= 30 wide
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--close').exists()).toBe(true)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(false)
  })

  it('renders the close hint', async () => {
    const wrapper = mountEstimate()
    await stepTo(wrapper, 120)
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Very close!')
  })

  it('a value outside the wide tolerance yields wrong', async () => {
    const wrapper = mountEstimate()
    await stepTo(wrapper, 160) // 60 away
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('renders the wrong hint', async () => {
    const wrapper = mountEstimate()
    await stepTo(wrapper, 160)
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('quite far off')
  })

  it('reaches the target from the start value in whole steps', () => {
    // Configuration invariant: targetValue === startValue + k * step
    const config = makeConfig()
    const k = (config.targetValue - config.startValue) / config.step
    expect(Number.isInteger(k)).toBe(true)
  })

  it('emits complete on continue', async () => {
    const wrapper = mountEstimate()
    await stepTo(wrapper, 100)
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('clears persisted state on continue', async () => {
    const config = makeConfig()
    const wrapper = mountEstimate(config)
    await stepTo(wrapper, 100)
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
