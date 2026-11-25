import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { ConnectChallenge } from '@/types/learning-challenge'
import ConnectComponent from '../ConnectChallenge.vue'

function makeConfig(overrides: Partial<ConnectChallenge> = {}): ConnectChallenge {
  return {
    id: 'connect-test',
    topicId: 't1',
    type: 'connect',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Match each animal to where it lives.',
    scenarioZh: '把动物和它的家连起来。',
    discoveryMessage: 'All matched!',
    discoveryMessageZh: '全部连对啦！',
    leftItems: [
      { id: 'l1', label: 'Fish' },
      { id: 'l2', label: 'Bird' },
      { id: 'l3', label: 'Bear' },
    ],
    rightItems: [
      { id: 'r1', label: 'Water' },
      { id: 'r2', label: 'Nest' },
      { id: 'r3', label: 'Cave' },
    ],
    correctPairs: { l1: 'r1', l2: 'r2', l3: 'r3' },
    ...overrides,
  }
}

function mountConnect(config: ConnectChallenge = makeConfig()) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(ConnectComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

/**
 * Pair items by simulating the drag interaction.
 * The ConnectChallenge uses pointerdown on left items and pointerup on right items.
 * In jsdom, we mock elementFromPoint to make the drag-drop work.
 */
async function pair(wrapper: ReturnType<typeof mountConnect>, leftId: string, rightId: string) {
  // Mock boardRef for SVG viewBox
  const board = wrapper.find('.connect-board')
  if (board.element.getBoundingClientRect === undefined) {
    board.element.getBoundingClientRect = () => ({
      x: 0, y: 0, width: 400, height: 300, top: 0, left: 0, right: 400, bottom: 300, toJSON: () => {},
    })
  }

  // Find left and right item elements
  const leftEl = wrapper.find(`[data-id="${leftId}"]`)
  const rightEl = wrapper.find(`[data-id="${rightId}"]`)
  expect(leftEl.exists()).toBe(true)
  expect(rightEl.exists()).toBe(true)

  // Mock getBoundingClientRect for both elements
  const leftRect = { x: 0, y: 0, width: 100, height: 50, top: 0, left: 0, right: 100, bottom: 50, toJSON: () => {} }
  const rightRect = { x: 200, y: 0, width: 100, height: 50, top: 0, left: 200, right: 300, bottom: 50, toJSON: () => {} }
  leftEl.element.getBoundingClientRect = () => leftRect as DOMRect
  rightEl.element.getBoundingClientRect = () => rightRect as DOMRect

  // Mock elementFromPoint to return the right item when pointerup happens at right item position
  const origElementFromPoint = document.elementFromPoint
  document.elementFromPoint = vi.fn(() => rightEl.element)

  // Simulate drag: pointerdown on left, pointermove, pointerup on right
  await leftEl.trigger('pointerdown', { clientX: 50, clientY: 25 })
  await nextTick()
  // pointermove and pointerup are on window, so we dispatch on window
  window.dispatchEvent(new PointerEvent('pointermove', { clientX: 250, clientY: 25, bubbles: true }))
  await nextTick()
  window.dispatchEvent(new PointerEvent('pointerup', { clientX: 250, clientY: 25, bubbles: true }))
  await nextTick()

  // Restore
  document.elementFromPoint = origElementFromPoint
}

async function check(wrapper: ReturnType<typeof mountConnect>) {
  await wrapper.find('.challenge-check-btn').trigger('click')
  await nextTick()
}

describe('ConnectChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders both columns', () => {
    const wrapper = mountConnect()
    expect(wrapper.findAll('.connect-column')).toHaveLength(2)
    expect(wrapper.findAll('.connect-item')).toHaveLength(6)
  })

  it('pairing a left item with a right item records the pair', async () => {
    const wrapper = mountConnect()
    await pair(wrapper, 'l1', 'r1')
    // After pairing, left item should show paired class
    const pairedItems = wrapper.findAll('.connect-item--paired')
    expect(pairedItems.length).toBeGreaterThanOrEqual(1)
  })

  it('all correct pairs yield correct', async () => {
    const config = makeConfig()
    // Pre-set all pairs via sessionStorage (useChallengeState format)
    sessionStorage.setItem(
      `numina:challenge:${config.id}`,
      JSON.stringify({
        state: { pairs: { l1: 'r1', l2: 'r2', l3: 'r3' } },
        completed: false,
        feedbackMessage: '',
        feedbackVerdict: null,
        attemptCount: 0,
      }),
    )
    const wrapper = mountConnect(config)
    await nextTick()
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('All matched!')
  })

  it('renders the close hint for one wrong pair', async () => {
    const config = makeConfig({
      leftItems: [
        { id: 'l1', label: 'Fish' },
        { id: 'l2', label: 'Bird' },
      ],
      rightItems: [
        { id: 'r1', label: 'Water' },
        { id: 'r2', label: 'Nest' },
        { id: 'r3', label: 'Sky' },
      ],
      correctPairs: { l1: 'r1', l2: 'r2' },
    })
    // One wrong, one right
    sessionStorage.setItem(
      `numina:challenge:${config.id}`,
      JSON.stringify({
        state: { pairs: { l1: 'r3', l2: 'r2' } },
        completed: false,
        feedbackMessage: '',
        feedbackVerdict: null,
        attemptCount: 0,
      }),
    )
    const wrapper = mountConnect(config)
    await nextTick()
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--close').exists()).toBe(true)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Only one pair left')
  })

  it('emits complete on continue', async () => {
    const config = makeConfig()
    sessionStorage.setItem(
      `numina:challenge:${config.id}`,
      JSON.stringify({
        state: { pairs: { l1: 'r1', l2: 'r2', l3: 'r3' } },
        completed: true,
        feedbackMessage: 'All matched!',
        feedbackVerdict: 'correct',
        attemptCount: 1,
      }),
    )
    const wrapper = mountConnect(config)
    await nextTick()
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('clears persisted state on continue', async () => {
    const config = makeConfig()
    sessionStorage.setItem(
      `numina:challenge:${config.id}`,
      JSON.stringify({
        state: { pairs: { l1: 'r1', l2: 'r2', l3: 'r3' } },
        completed: true,
        feedbackMessage: 'All matched!',
        feedbackVerdict: 'correct',
        attemptCount: 1,
      }),
    )
    const wrapper = mountConnect(config)
    await nextTick()
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
