import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { BalanceChallenge } from '@/types/learning-challenge'
import BalanceChallengeComponent from '../BalanceChallenge.vue'

function makeConfig(overrides: Partial<BalanceChallenge> = {}): BalanceChallenge {
  return {
    id: 'balance-test',
    topicId: 't1',
    type: 'balance',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Balance the scale.',
    scenarioZh: '让天平平衡。',
    discoveryMessage: 'Both sides are equal!',
    discoveryMessageZh: '两边相等！',
    leftFixed: [
      { id: 'l1', label: '3', icon: '🔵' },
      { id: 'l2', label: '2', icon: '🔵' },
    ],
    rightSlots: 2,
    objects: [
      { id: 'r1', label: '1', icon: '🔴' },
      { id: 'r3', label: '3', icon: '🔴' },
      { id: 'r5', label: '5', icon: '🔴' },
    ],
    objectValues: { l1: 3, l2: 2, r1: 1, r3: 3, r5: 5 },
    ...overrides,
  }
}

function mountBalance(config: BalanceChallenge = makeConfig()) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(BalanceChallengeComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

describe('BalanceChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders left pan with fixed items', () => {
    const wrapper = mountBalance()
    const leftPan = wrapper.find('.challenge-pan--left')
    expect(leftPan.exists()).toBe(true)
    expect(leftPan.findAll('.challenge-pan__item')).toHaveLength(2)
  })

  it('renders right pan with correct number of slots', () => {
    const wrapper = mountBalance()
    const rightPan = wrapper.find('.challenge-pan--right')
    expect(rightPan.exists()).toBe(true)
    expect(rightPan.findAll('.challenge-pan__slot')).toHaveLength(2)
  })

  it('shows left total (sum of fixed items)', () => {
    const wrapper = mountBalance()
    // l1=3 + l2=2 = 5
    expect(wrapper.find('.challenge-pan--left .challenge-pan__total').text()).toContain('5')
  })

  it('shows right total as 0 initially', () => {
    const wrapper = mountBalance()
    expect(wrapper.find('.challenge-pan--right .challenge-pan__total').text()).toContain('0')
  })

  it('renders object pool with available objects', () => {
    const wrapper = mountBalance()
    expect(wrapper.findAll('.challenge-object')).toHaveLength(3)
  })

  it('tap object selects it', async () => {
    const wrapper = mountBalance()
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    expect(wrapper.findAll('.challenge-object')[0].classes()).toContain('challenge-object--selected')
  })

  it('tap slot with selected object places it', async () => {
    const wrapper = mountBalance()
    // Select r5 (value 5)
    await wrapper.findAll('.challenge-object')[2].trigger('click')
    // Place in first slot
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    // Object removed from pool
    expect(wrapper.findAll('.challenge-object')).toHaveLength(2)
    // Right total updated
    expect(wrapper.find('.challenge-pan--right .challenge-pan__total').text()).toContain('5')
  })

  it('tap filled slot returns object to pool', async () => {
    const wrapper = mountBalance()
    // Place an object
    await wrapper.findAll('.challenge-object')[2].trigger('click')
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    expect(wrapper.findAll('.challenge-object')).toHaveLength(2)
    // Return to pool
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    expect(wrapper.findAll('.challenge-object')).toHaveLength(3)
  })

  it('correct balance → discovery message', async () => {
    const wrapper = mountBalance()
    // Left = 3+2 = 5. Place r5 (value 5) in slot 0, r1 (value 0 → won't balance)
    // Actually we need right = 5. r5=5 alone. But we have 2 slots and need to fill both?
    // No — evaluateBalance checks left === right. Place r5=5 in slot 0, r1=1 won't work.
    // Let's use a simpler config: place r5 (5) + nothing = 5.
    // Wait, evaluateBalance: rightTotal must equal leftTotal. Let me place r3 (3) in slot 0
    // and... hmm. Actually the config has r1=1, r3=3, r5=5 and left=5.
    // Only r5 alone = 5 matches. But we have 2 slots. Let me check evaluateBalance:
    // it checks rightTotal === leftTotal. So r5 in slot 0, empty slot 1 → rightTotal = 5. Balanced!
    await wrapper.findAll('.challenge-object')[2].trigger('click') // r5
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('Both sides are equal!')
  })

  it('right too light → hint', async () => {
    const wrapper = mountBalance()
    // Place r1 (value 1) — right = 1, left = 5 → too light
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('right too heavy → hint', async () => {
    const wrapper = mountBalance()
    // Place r5 (5) + r3 (3) = 8 > 5 → too heavy
    await wrapper.findAll('.challenge-object')[2].trigger('click') // r5
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    await wrapper.findAll('.challenge-object')[1].trigger('click') // r3
    await wrapper.findAll('.challenge-pan__slot')[1].trigger('click')
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('check button disabled when nothing placed', () => {
    const wrapper = mountBalance()
    expect(wrapper.find('.challenge-check-btn').attributes('disabled')).toBeDefined()
  })

  it('shows continue button after correct balance', async () => {
    const wrapper = mountBalance()
    await wrapper.findAll('.challenge-object')[2].trigger('click')
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(true)
  })

  it('emits complete on continue', async () => {
    const wrapper = mountBalance()
    await wrapper.findAll('.challenge-object')[2].trigger('click')
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    await wrapper.find('.challenge-check-btn').trigger('click')
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('fulcrum tilts based on weight difference', async () => {
    const wrapper = mountBalance()
    // Initially balanced (no placements, fulcrum has no tilt class)
    expect(wrapper.find('.challenge-fulcrum--left-heavy').exists()).toBe(false)
    expect(wrapper.find('.challenge-fulcrum--right-heavy').exists()).toBe(false)
    // Place r1 (1) — left heavy
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    expect(wrapper.find('.challenge-fulcrum--left-heavy').exists()).toBe(true)
  })

  it('restores state from sessionStorage on remount', async () => {
    const config = makeConfig()
    const first = mountBalance(config)
    // Place r5 in slot 0
    await first.findAll('.challenge-object')[2].trigger('click')
    await first.findAll('.challenge-pan__slot')[0].trigger('click')
    await nextTick()

    const second = mountBalance(config)
    expect(second.findAll('.challenge-object')).toHaveLength(2)
    expect(second.find('.challenge-pan--right .challenge-pan__total').text()).toContain('5')
  })

  it('clears persisted state after continuing', async () => {
    const config = makeConfig()
    const wrapper = mountBalance(config)
    await wrapper.findAll('.challenge-object')[2].trigger('click')
    await wrapper.findAll('.challenge-pan__slot')[0].trigger('click')
    await wrapper.find('.challenge-check-btn').trigger('click')
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
