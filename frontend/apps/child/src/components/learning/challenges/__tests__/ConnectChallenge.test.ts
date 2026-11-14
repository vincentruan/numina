import { describe, it, expect, beforeEach } from 'vitest'
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

/** Tap a left item then a right item to pair them. */
async function pair(wrapper: ReturnType<typeof mountConnect>, leftLabel: string, rightLabel: string) {
  const items = wrapper.findAll('.connect-item')
  const left = items.find((i) => i.text().includes(leftLabel) && !i.text().includes('→'))
  const right = items.find((i) => i.text().includes(rightLabel) && !i.text().includes('→') && !i.text().includes('↩'))
  expect(left).toBeTruthy()
  expect(right).toBeTruthy()
  await left!.trigger('click')
  await right!.trigger('click')
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
    await pair(wrapper, 'Fish', 'Water')
    expect(wrapper.findAll('.connect-item--paired').length).toBe(2)
  })

  it('all correct pairs yield correct', async () => {
    const wrapper = mountConnect()
    await pair(wrapper, 'Fish', 'Water')
    await pair(wrapper, 'Bird', 'Nest')
    await pair(wrapper, 'Bear', 'Cave')
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('All matched!')
  })

  it('exactly one wrong pair among three yields wrong, not close', async () => {
    const wrapper = mountConnect({
      ...makeConfig(),
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
    await pair(wrapper, 'Fish', 'Nest') // wrong
    await pair(wrapper, 'Bird', 'Sky') // wrong
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('renders the close hint for one wrong pair', async () => {
    const wrapper = mountConnect({
      ...makeConfig(),
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
    await pair(wrapper, 'Fish', 'Sky') // wrong, one of two
    await pair(wrapper, 'Bird', 'Nest') // right
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--close').exists()).toBe(true)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Only one pair left')
  })

  it('tapping a paired item unpairs it', async () => {
    const wrapper = mountConnect()
    await pair(wrapper, 'Fish', 'Water')
    expect(wrapper.findAll('.connect-item--paired').length).toBe(2)
    const paired = wrapper.findAll('.connect-item--paired')[0]
    await paired.trigger('click')
    expect(wrapper.findAll('.connect-item--paired').length).toBe(0)
  })

  it('emits complete on continue', async () => {
    const wrapper = mountConnect()
    await pair(wrapper, 'Fish', 'Water')
    await pair(wrapper, 'Bird', 'Nest')
    await pair(wrapper, 'Bear', 'Cave')
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('clears persisted state on continue', async () => {
    const config = makeConfig()
    const wrapper = mountConnect(config)
    await pair(wrapper, 'Fish', 'Water')
    await pair(wrapper, 'Bird', 'Nest')
    await pair(wrapper, 'Bear', 'Cave')
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
