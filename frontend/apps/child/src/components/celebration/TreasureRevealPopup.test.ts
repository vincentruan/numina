import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import TreasureRevealPopup from './TreasureRevealPopup.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      celebration: {
        phrases: ['加油'],
        singleTask: '获得 {stars} ⭐！',
        multipleTasks: '{count}个任务通过！获得 {stars} ⭐',
        overlayLabel: '任务通过庆祝',
        treasureUnlocked: '宝藏解锁！',
        confirmButton: '太棒了！',
      },
    },
  },
})

describe('TreasureRevealPopup', () => {
  it('renders title, phrase, and confirm button when visible', () => {
    const wrapper = mount(TreasureRevealPopup, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    expect(document.body.innerHTML).toContain('宝藏解锁')
    expect(document.body.innerHTML).toContain('太棒了')
    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('emits confirm when button clicked', async () => {
    const wrapper = mount(TreasureRevealPopup, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    const btn = document.querySelector('.popup-confirm') as HTMLElement
    btn.click()
    await flushPromises()
    expect(wrapper.emitted().confirm).toBeTruthy()
    wrapper.unmount()
    document.body.innerHTML = ''
  })

  it('emits auto-dismiss after 6 seconds with no interaction', async () => {
    vi.useFakeTimers()
    const wrapper = mount(TreasureRevealPopup, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    vi.advanceTimersByTime(6100)
    expect(wrapper.emitted()['auto-dismiss']).toBeTruthy()
    wrapper.unmount()
    document.body.innerHTML = ''
    vi.useRealTimers()
  })

  it('does not render when not visible', () => {
    mount(TreasureRevealPopup, {
      props: { visible: false, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    expect(document.body.querySelector('.popup-overlay')).toBeNull()
    document.body.innerHTML = ''
  })
})
