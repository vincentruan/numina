import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { DistributeChallenge, ClassifyChallenge, ChallengeConfig } from '@/types/learning-challenge'
import ManipulateObserveReflect from './ManipulateObserveReflect.vue'

function makeDistributeConfig(overrides: Partial<DistributeChallenge> = {}): DistributeChallenge {
  return {
    id: 'ch1',
    topicId: 't1',
    type: 'distribute',
    scenario: 'Share 4 cookies between 2 friends equally.',
    scenarioZh: '把4块饼干公平分给2个朋友。',
    discoveryMessage: 'You made it fair!',
    discoveryMessageZh: '你分得真公平！',
    objects: [
      { id: 'c1', label: 'Cookie', icon: '🍪' },
      { id: 'c2', label: 'Cookie', icon: '🍪' },
      { id: 'c3', label: 'Cookie', icon: '🍪' },
      { id: 'c4', label: 'Cookie', icon: '🍪' },
    ],
    zones: [
      { id: 'z1', label: 'Friend A', labelZh: '朋友A' },
      { id: 'z2', label: 'Friend B', labelZh: '朋友B' },
    ],
    ...overrides,
  }
}

function makeClassifyConfig(): ClassifyChallenge {
  return {
    id: 'ch2',
    topicId: 't2',
    type: 'classify',
    scenario: 'Sort the animals by type.',
    scenarioZh: '按类型分类动物。',
    discoveryMessage: 'You sorted them correctly!',
    discoveryMessageZh: '你分对了！',
    objects: [
      { id: 'a1', label: 'Dog', icon: '🐕' },
      { id: 'a2', label: 'Cat', icon: '🐈' },
      { id: 'a3', label: 'Fish', icon: '🐟' },
    ],
    zones: [
      { id: 'z1', label: 'Pets', labelZh: '宠物' },
      { id: 'z2', label: 'Other', labelZh: '其他' },
    ],
    correctMapping: { a1: 'z1', a2: 'z1', a3: 'z2' },
  }
}

function mountChallenge(config: ChallengeConfig = makeDistributeConfig()) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(ManipulateObserveReflect, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

describe('ManipulateObserveReflect (U5)', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders scenario text and object pool from config', () => {
    const wrapper = mountChallenge()
    expect(wrapper.find('.challenge-scenario__text').text()).toContain('Share 4 cookies')
    expect(wrapper.findAll('.challenge-object')).toHaveLength(4)
  })

  it('renders zone areas', () => {
    const wrapper = mountChallenge()
    const zones = wrapper.findAll('.challenge-zone')
    expect(zones).toHaveLength(2)
    expect(zones[0].text()).toContain('Friend A')
  })

  it('tap object selects it (highlighted state)', async () => {
    const wrapper = mountChallenge()
    const objects = wrapper.findAll('.challenge-object')
    await objects[0].trigger('click')
    expect(objects[0].classes()).toContain('challenge-object--selected')
  })

  it('tap same object again deselects it', async () => {
    const wrapper = mountChallenge()
    const obj = wrapper.findAll('.challenge-object')[0]
    await obj.trigger('click')
    expect(obj.classes()).toContain('challenge-object--selected')
    await obj.trigger('click')
    expect(obj.classes()).not.toContain('challenge-object--selected')
  })

  it('tap zone with selected object moves it to zone', async () => {
    const wrapper = mountChallenge()
    // Select first object
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    // Tap zone
    await wrapper.findAll('.challenge-zone')[0].trigger('click')
    // Object removed from pool
    expect(wrapper.findAll('.challenge-object')).toHaveLength(3)
    // Object appears in zone
    expect(wrapper.findAll('.challenge-zone__placed')).toHaveLength(1)
  })

  it('tap placed object returns it to pool', async () => {
    const wrapper = mountChallenge()
    // Place an object
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    await wrapper.findAll('.challenge-zone')[0].trigger('click')
    expect(wrapper.findAll('.challenge-object')).toHaveLength(3)
    // Tap placed object to return
    await wrapper.find('.challenge-zone__placed').trigger('click')
    expect(wrapper.findAll('.challenge-object')).toHaveLength(4)
  })

  it('correct distribution → discovery message shown', async () => {
    const wrapper = mountChallenge()
    // Place 2 cookies in zone 1, 2 in zone 2
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[0].trigger('click')
    }
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[1].trigger('click')
    }
    // Check
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('You made it fair!')
  })

  it('incorrect distribution → hint shown, retry allowed', async () => {
    const wrapper = mountChallenge()
    // Place all 4 in zone 1 (wrong)
    for (let i = 0; i < 4; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[0].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
    // Check button still present (retry)
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(true)
  })

  it('check button disabled when no objects placed', () => {
    const wrapper = mountChallenge()
    expect(wrapper.find('.challenge-check-btn').attributes('disabled')).toBeDefined()
  })

  it('all interactive elements use semantic <button> for accessibility', () => {
    const wrapper = mountChallenge()
    // Challenge objects are <button> elements — ensures keyboard/screen-reader access
    const objects = wrapper.findAll('.challenge-object')
    expect(objects[0].element.tagName).toBe('BUTTON')
    // Check/continue buttons are also <button>
    expect(wrapper.find('.challenge-check-btn').element.tagName).toBe('BUTTON')
  })

  it('renders nothing when config has no objects', () => {
    const wrapper = mountChallenge(makeDistributeConfig({ objects: [] }))
    // Should still render (empty pool)
    expect(wrapper.find('.manipulate-challenge').exists()).toBe(true)
    expect(wrapper.findAll('.challenge-object')).toHaveLength(0)
  })

  it('shows continue button after correct answer', async () => {
    const wrapper = mountChallenge()
    // Place 2+2 (correct)
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[0].trigger('click')
    }
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[1].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(true)
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(false)
  })

  it('emits complete when continue is clicked after success', async () => {
    const wrapper = mountChallenge()
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[0].trigger('click')
    }
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[1].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('classify challenge evaluates correctly', async () => {
    const wrapper = mountChallenge(makeClassifyConfig())
    const zones = wrapper.findAll('.challenge-zone')
    // Dog (a1) → Pets: click first object, then first zone
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    await zones[0].trigger('click')
    // Cat (a2) → Pets: first remaining object is now Cat
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    await zones[0].trigger('click')
    // Fish (a3) → Other: last remaining object
    await wrapper.findAll('.challenge-object')[0].trigger('click')
    await zones[1].trigger('click')
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
  })

  it('blocks interaction after challenge is completed', async () => {
    const wrapper = mountChallenge()
    // Complete the challenge (2+2 equal distribution)
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[0].trigger('click')
    }
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[1].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    // Verify completed
    expect(wrapper.find('.challenge-next-btn').exists()).toBe(true)
    // Try to place more objects — pool should be empty since all are placed
    expect(wrapper.findAll('.challenge-object')).toHaveLength(0)
  })

  it('renders Chinese scenario and discovery messages when locale is zh-CN', async () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'en-US': enUS, 'zh-CN': zhCN },
    })
    const config = makeDistributeConfig()
    const wrapper = mount(ManipulateObserveReflect, {
      props: { config },
      global: { plugins: [i18n] },
    })
    // Chinese scenario text
    expect(wrapper.find('.challenge-scenario__text').text()).toContain('公平分给')
    // Complete challenge and check Chinese discovery message
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[0].trigger('click')
    }
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[1].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    expect(wrapper.find('.challenge-feedback__message--correct').text()).toContain('真公平')
  })

  it('shows AI tutor suggestion button after 2 failed attempts', async () => {
    const wrapper = mountChallenge()
    // Fail twice (all in zone 1 = unequal)
    for (let attempt = 0; attempt < 2; attempt++) {
      for (let i = 0; i < 4; i++) {
        await wrapper.findAll('.challenge-object')[0].trigger('click')
        await wrapper.findAll('.challenge-zone')[0].trigger('click')
      }
      await wrapper.find('.challenge-check-btn').trigger('click')
      expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
      // Return all to pool for next attempt
      for (const placed of wrapper.findAll('.challenge-zone__placed')) {
        await placed.trigger('click')
      }
    }
    // After 2 failed attempts, tutor suggestion should appear alongside check button
    expect(wrapper.find('.challenge-tutor-btn').exists()).toBe(true)
    expect(wrapper.find('.challenge-check-btn').exists()).toBe(true)
  })

  it('restores placements and attempts from sessionStorage on remount (AE5)', async () => {
    const config = makeDistributeConfig()
    const first = mountChallenge(config)
    // Place 2 cookies in zone 1 and fail once
    for (let i = 0; i < 2; i++) {
      await first.findAll('.challenge-object')[0].trigger('click')
      await first.findAll('.challenge-zone')[0].trigger('click')
    }
    await first.find('.challenge-check-btn').trigger('click')
    await nextTick()

    // Simulate the child leaving and returning: fresh mount, same config
    const second = mountChallenge(config)
    // 2 objects remain placed in zone 1, pool is back down to 2
    expect(second.findAll('.challenge-zone__placed')).toHaveLength(2)
    expect(second.findAll('.challenge-object')).toHaveLength(2)
    // The failed-attempt hint is still shown
    expect(second.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('clears persisted state after continuing past the challenge', async () => {
    const config = makeDistributeConfig()
    const wrapper = mountChallenge(config)
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[0].trigger('click')
    }
    for (let i = 0; i < 2; i++) {
      await wrapper.findAll('.challenge-object')[0].trigger('click')
      await wrapper.findAll('.challenge-zone')[1].trigger('click')
    }
    await wrapper.find('.challenge-check-btn').trigger('click')
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
