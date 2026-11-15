import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { SpotTheMistakeChallenge } from '@/types/learning-challenge'
import SpotTheMistakeComponent from '../SpotTheMistakeChallenge.vue'
// Raw SFC source, for asserting the tap-target floor declared in its scoped style
import spotTheMistakeSource from '../SpotTheMistakeChallenge.vue?raw'

function makeConfig(overrides: Partial<SpotTheMistakeChallenge> = {}): SpotTheMistakeChallenge {
  return {
    id: 'mistake-test',
    topicId: 't1',
    type: 'spot-the-mistake',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Ada solved this. Which line is wrong?',
    scenarioZh: '小美做的这道题，哪一行错了？',
    discoveryMessage: 'You spotted the mistake!',
    discoveryMessageZh: '你找到错误啦！',
    lines: ['2 + 3 = 5', '5 × 2 = 12', '12 - 2 = 10', '10 + 1 = 11'],
    mistakeLineIndex: 1,
    ...overrides,
  }
}

function mountMistake(config: SpotTheMistakeChallenge = makeConfig()) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(SpotTheMistakeComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

async function tapLine(wrapper: ReturnType<typeof mountMistake>, index: number) {
  await wrapper.findAll('.mistake-line')[index].trigger('click')
  await wrapper.find('.challenge-check-btn').trigger('click')
  await nextTick()
}

describe('SpotTheMistakeChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders every line as its own row control', () => {
    const wrapper = mountMistake()
    expect(wrapper.findAll('.mistake-line')).toHaveLength(4)
    expect(wrapper.findAll('.mistake-line')[1].text()).toContain('5 × 2 = 12')
  })

  it('declares a 48px minimum tap target on each row', () => {
    // R10: the row itself is the tap target, so its height must clear the floor.
    // happy-dom does not cascade scoped styles, so assert against the SFC source.
    const rule = spotTheMistakeSource.match(/\.mistake-line\s*\{[^}]*\}/)?.[0] ?? ''
    expect(rule).toContain('min-height: 48px')
  })

  it('marks the tapped line and unmarks it on a second tap', async () => {
    const wrapper = mountMistake()
    const row = wrapper.findAll('.mistake-line')[0]
    await row.trigger('click')
    expect(row.classes()).toContain('mistake-line--selected')
    await row.trigger('click')
    expect(row.classes()).not.toContain('mistake-line--selected')
  })

  it('tapping the wrong line yields a correct verdict', async () => {
    const wrapper = mountMistake()
    await tapLine(wrapper, 1) // mistakeLineIndex = 1
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('You spotted the mistake!')
  })

  it('tapping an adjacent line yields close, not wrong', async () => {
    const wrapper = mountMistake()
    await tapLine(wrapper, 0) // one away from index 1
    expect(wrapper.find('.challenge-feedback__message--close').exists()).toBe(true)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(false)
  })

  it('tapping a distant line yields wrong', async () => {
    const wrapper = mountMistake()
    await tapLine(wrapper, 3) // three away from index 1
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('renders the close hint', async () => {
    const wrapper = mountMistake()
    await tapLine(wrapper, 0)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Very close!')
  })

  it('renders the wrong hint', async () => {
    const wrapper = mountMistake()
    await tapLine(wrapper, 3)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Work through it again')
  })

  it('emits complete when continue is tapped after a correct answer', async () => {
    const wrapper = mountMistake()
    await tapLine(wrapper, 1)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('clears persisted state on continue', async () => {
    const config = makeConfig()
    const wrapper = mountMistake(config)
    await tapLine(wrapper, 1)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
