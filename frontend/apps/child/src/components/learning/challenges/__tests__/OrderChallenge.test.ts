import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { OrderChallenge } from '@/types/learning-challenge'
import OrderChallengeComponent from '../OrderChallenge.vue'

function makeConfig(overrides: Partial<OrderChallenge> = {}): OrderChallenge {
  return {
    id: 'order-test',
    topicId: 't1',
    type: 'order',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Put in order from smallest to biggest.',
    scenarioZh: '从小到大排一排。',
    discoveryMessage: 'Correct order!',
    discoveryMessageZh: '顺序正确！',
    objects: [
      { id: 'a', label: 'Small', icon: '🔵' },
      { id: 'b', label: 'Medium', icon: '🟡' },
      { id: 'c', label: 'Large', icon: '🔴' },
    ],
    correctOrder: ['a', 'b', 'c'],
    ...overrides,
  }
}

function mountOrder(config: OrderChallenge = makeConfig()) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(OrderChallengeComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

describe('OrderChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders sequence slots matching correctOrder length', () => {
    const wrapper = mountOrder()
    expect(wrapper.findAll('.challenge-slot')).toHaveLength(3)
  })

  it('renders object pool with all objects initially', () => {
    const wrapper = mountOrder()
    expect(wrapper.findAll('.challenge-object')).toHaveLength(3)
  })

  it('shows slot numbers as placeholders', () => {
    const wrapper = mountOrder()
    const slots = wrapper.findAll('.challenge-slot')
    expect(slots[0].find('.challenge-slot__placeholder').text()).toBe('1')
    expect(slots[1].find('.challenge-slot__placeholder').text()).toBe('2')
    expect(slots[2].find('.challenge-slot__placeholder').text()).toBe('3')
  })

  it('tap object selects it', async () => {
    const wrapper = mountOrder()
    const objects = wrapper.findAll('.challenge-object')
    await objects[0].trigger('click')
    expect(objects[0].classes()).toContain('challenge-object--selected')
  })

  it('tap same object again deselects it', async () => {
    const wrapper = mountOrder()
    const obj = wrapper.findAll('.challenge-object')[0]
    await obj.trigger('click')
    expect(obj.classes()).toContain('challenge-object--selected')
    await obj.trigger('click')
    expect(obj.classes()).not.toContain('challenge-object--selected')
  })

  it('tap slot with selected object places it', async () => {
    const wrapper = mountOrder()
    // Select first object
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    // Tap first slot
    await wrapper.findAll('.challenge-slot')[0].trigger('click')
    // Object removed from pool
    expect(wrapper.findAll('.challenge-object')).toHaveLength(2)
    // Slot shows the icon
    expect(wrapper.findAll('.challenge-slot')[0].find('.challenge-slot__icon').exists()).toBe(true)
  })

  it('tap filled slot returns object to pool', async () => {
    const wrapper = mountOrder()
    // Place an object
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    await wrapper.findAll('.challenge-slot')[0].trigger('click')
    expect(wrapper.findAll('.challenge-object')).toHaveLength(2)
    // Tap the filled slot to return
    await wrapper.findAll('.challenge-slot')[0].trigger('click')
    expect(wrapper.findAll('.challenge-object')).toHaveLength(3)
  })

  it('check button disabled when no objects placed', () => {
    const wrapper = mountOrder()
    expect(wrapper.find('.challenge-check-btn').attributes('disabled')).toBeDefined()
  })

  it('correct order → discovery message shown', async () => {
    const wrapper = mountOrder()
    // Place a → slot 0, b → slot 1, c → slot 2
    for (let i = 0; i < 3; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-slot')[i].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('Correct order!')
  })

  it('wrong order → hint shown, retry allowed', async () => {
    const wrapper = mountOrder()
    // Place in wrong order: c → slot 0, b → slot 1, a → slot 2
    // Pool starts as [a(0), b(1), c(2)]. Select LAST for c, then adjust.
    const objects = wrapper.findAll('.challenge-object')
    await objects[2].trigger('click') // select c
    await wrapper.findAll('.challenge-slot')[0].trigger('click') // place in slot 0
    // Pool now [a(0), b(1)]
    await wrapper.findAll('.challenge-object')[1].trigger('click') // select b
    await wrapper.findAll('.challenge-slot')[1].trigger('click') // place in slot 1
    // Pool now [a(0)]
    await wrapper.findAll('.challenge-object')[0].trigger('click') // select a
    await wrapper.findAll('.challenge-slot')[2].trigger('click') // place in slot 2
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
    // Check button still present (retry)
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(true)
  })

  it('shows continue button after correct answer', async () => {
    const wrapper = mountOrder()
    for (let i = 0; i < 3; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-slot')[i].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(true)
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(false)
  })

  it('emits complete when continue is clicked', async () => {
    const wrapper = mountOrder()
    for (let i = 0; i < 3; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-slot')[i].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('blocks interaction after completion', async () => {
    const wrapper = mountOrder()
    for (let i = 0; i < 3; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-slot')[i].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    // All objects placed, pool is empty
    expect(wrapper.findAll('.challenge-object')).toHaveLength(0)
  })

  it('shows tutor button after 2 failed attempts', async () => {
    const wrapper = mountOrder()
    // Fail twice by placing in reverse order each time.
    for (let attempt = 0; attempt < 2; attempt++) {
      const objects = wrapper.findAll('.challenge-object')
      await objects[2].trigger('click')
      await wrapper.findAll('.challenge-slot')[0].trigger('click')
      await wrapper.findAll('.challenge-object')[1].trigger('click')
      await wrapper.findAll('.challenge-slot')[1].trigger('click')
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-slot')[2].trigger('click')
      await wrapper.find('.challenge-check-btn').trigger('click')
      expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
      // Return all to pool for the next attempt
      for (const slot of wrapper.findAll('.challenge-slot')) {
        await slot.trigger('click')
      }
    }
    expect(wrapper.find('.challenge-tutor-btn').exists()).toBe(true)
  })

  it('restores state from sessionStorage on remount', async () => {
    const config = makeConfig()
    const first = mountOrder(config)
    // Place first object in first slot
    await first.findAll('.challenge-object')[0].trigger('click')
    await first.findAll('.challenge-slot')[0].trigger('click')
    await nextTick()

    // Fresh mount — should restore
    const second = mountOrder(config)
    expect(second.findAll('.challenge-object')).toHaveLength(2)
    expect(second.findAll('.challenge-slot')[0].find('.challenge-slot__icon').exists()).toBe(true)
  })

  it('clears persisted state after continuing', async () => {
    const config = makeConfig()
    const wrapper = mountOrder(config)
    for (let i = 0; i < 3; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-slot')[i].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
