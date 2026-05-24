import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import CelebrationAnimation from './CelebrationAnimation.vue'

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
        reducedMotionToast: '✨ 任务通过！获得 {stars} ⭐',
        candleAriaLabel: '等待审批中',
      },
    },
  },
})

describe('CelebrationAnimation orchestration shell', () => {
  function clearBody(): void {
    document.body.innerHTML = ''
  }

  it('does not mount popup when visible=false', async () => {
    mount(CelebrationAnimation, {
      props: { visible: false, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    await nextTick()
    expect(document.body.querySelector('.popup-overlay')).toBeNull()
    clearBody()
  })

  it('mounts treasure popup when visible=true', async () => {
    mount(CelebrationAnimation, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(document.body.querySelector('.popup-overlay')).not.toBeNull()
    expect(document.body.innerHTML).toContain('宝藏解锁')
    clearBody()
  })

  it('does not emit dismiss when the popup backdrop is clicked (avoids skipping flight)', async () => {
    const wrapper = mount(CelebrationAnimation, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    await flushPromises()
    const overlay = document.body.querySelector('.popup-overlay') as HTMLElement | null
    expect(overlay).not.toBeNull()
    overlay!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
    expect(wrapper.emitted('dismiss')).toBeFalsy()
    expect(document.body.querySelector('.popup-overlay')).not.toBeNull()
    clearBody()
  })

  it('renders confirm button with sealed-treasure label', async () => {
    mount(CelebrationAnimation, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    await flushPromises()
    const confirmBtn = document.body.querySelector('.popup-confirm') as HTMLElement | null
    expect(confirmBtn).not.toBeNull()
    expect(confirmBtn!.textContent?.trim()).toBe('太棒了！')
    clearBody()
  })

  it('cleans up the popup when visible toggles to false', async () => {
    const wrapper = mount(CelebrationAnimation, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(document.body.querySelector('.popup-overlay')).not.toBeNull()
    await wrapper.setProps({ visible: false })
    await flushPromises()
    // Vant's leave transition runs sync in jsdom (no real animations) — popup is gone
    expect(document.body.querySelector('.popup-overlay')).toBeNull()
    clearBody()
  })

  it('renders multi-task summary text when taskCount > 1', async () => {
    mount(CelebrationAnimation, {
      props: { visible: true, taskCount: 3, starsEarned: 12 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    await flushPromises()
    expect(document.body.innerHTML).toContain('3个任务通过')
    expect(document.body.innerHTML).toContain('12 ⭐')
    clearBody()
  })

  it('uses reduced-motion namespace when overlay aria-label resolves', async () => {
    mount(CelebrationAnimation, {
      props: { visible: true, taskCount: 1, starsEarned: 5 },
      global: { plugins: [i18n] },
      attachTo: document.body,
    })
    await flushPromises()
    const popup = document.body.querySelector('[role="dialog"]') as HTMLElement | null
    expect(popup).not.toBeNull()
    expect(popup!.getAttribute('aria-label')).toBe('任务通过庆祝')
    clearBody()
  })
})
