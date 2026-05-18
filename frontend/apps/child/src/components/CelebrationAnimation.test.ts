import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import CelebrationAnimation from '@/components/CelebrationAnimation.vue'

// Create i18n instance for tests
const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      celebration: {
        phrases: ['太棒了！', '厉害！', '真行！'],
        singleTask: '获得 {stars} ⭐！',
        multipleTasks: '{count}个任务通过！获得 {stars} ⭐',
        overlayLabel: '任务通过庆祝',
      },
    },
  },
})

describe('CelebrationAnimation', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function mountComponent(props = {}) {
    return mount(CelebrationAnimation, {
      global: {
        plugins: [i18n],
      },
      props: {
        visible: false,
        taskCount: 1,
        starsEarned: 5,
        ...props,
      },
    })
  }

  describe('rendering', () => {
    it('does not render when visible is false', () => {
      const wrapper = mountComponent({ visible: false })
      expect(wrapper.find('.celebration-overlay').exists()).toBe(false)
    })

    it('renders overlay when visible is true', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      expect(wrapper.find('.celebration-overlay').exists()).toBe(true)
    })

    it('renders correct star count for single task', async () => {
      const wrapper = mountComponent({ visible: true, taskCount: 1 })
      await flushPromises()
      // Star count = Math.min(taskCount + 2, 8) = 3 for taskCount=1
      const stars = wrapper.findAll('.star')
      expect(stars.length).toBe(3)
    })

    it('caps star count at 8 for large task count', async () => {
      const wrapper = mountComponent({ visible: true, taskCount: 10 })
      await flushPromises()
      const stars = wrapper.findAll('.star')
      expect(stars.length).toBe(8)
    })

    it('shows single task message when taskCount is 1', async () => {
      const wrapper = mountComponent({ visible: true, taskCount: 1, starsEarned: 5 })
      await flushPromises()
      vi.advanceTimersByTime(1800) // Wait for summary card
      await flushPromises()
      expect(wrapper.find('.summary-text').text()).toContain('5 ⭐')
    })

    it('shows multiple task message when taskCount > 1', async () => {
      const wrapper = mountComponent({ visible: true, taskCount: 3, starsEarned: 15 })
      await flushPromises()
      vi.advanceTimersByTime(1800)
      await flushPromises()
      expect(wrapper.find('.summary-text').text()).toContain('3')
      expect(wrapper.find('.summary-text').text()).toContain('15 ⭐')
    })
  })

  describe('animation phases', () => {
    it('shows phrase after 200ms', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      expect(wrapper.find('.phrase-container').exists()).toBe(false)
      vi.advanceTimersByTime(200)
      await flushPromises()
      expect(wrapper.find('.phrase-container').exists()).toBe(true)
    })

    it('shows summary card after 1800ms', async () => {
      const wrapper = mountComponent({ visible: true, taskCount: 1 })
      await flushPromises()
      expect(wrapper.find('.summary-card').exists()).toBe(false)
      vi.advanceTimersByTime(1800)
      await flushPromises()
      expect(wrapper.find('.summary-card').exists()).toBe(true)
    })

    it('emits dismiss after 2800ms', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      vi.advanceTimersByTime(2800)
      await flushPromises()
      expect(wrapper.emitted('dismiss')).toBeTruthy()
    })
  })

  describe('timer cleanup', () => {
    it('clears all timers on dismiss', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      // Trigger dismiss early
      wrapper.find('.celebration-overlay').trigger('click')
      await flushPromises()
      // Advance timers — should not emit dismiss again
      vi.advanceTimersByTime(5000)
      await flushPromises()
      // Only one dismiss emission (from click)
      expect(wrapper.emitted('dismiss').length).toBe(1)
    })

    it('clears timers when visibility changes to false', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      // Change visibility mid-animation
      await wrapper.setProps({ visible: false })
      await flushPromises()
      // Advance timers — should not emit dismiss
      vi.advanceTimersByTime(5000)
      await flushPromises()
      // No dismiss emitted (animation was cancelled)
      expect(wrapper.emitted('dismiss')).toBeFalsy()
    })
  })

  describe('accessibility', () => {
    it('has correct aria attributes', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      const overlay = wrapper.find('.celebration-overlay')
      expect(overlay.attributes('role')).toBe('dialog')
      expect(overlay.attributes('aria-modal')).toBe('true')
      expect(overlay.attributes('aria-label')).toBe('任务通过庆祝')
    })

    it('marks stars container as aria-hidden', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      const starsContainer = wrapper.find('.stars-container')
      expect(starsContainer.attributes('aria-hidden')).toBe('true')
    })
  })

  describe('random phrase selection', () => {
    it('displays a phrase from the i18n pool', async () => {
      const wrapper = mountComponent({ visible: true })
      await flushPromises()
      vi.advanceTimersByTime(200)
      await flushPromises()
      const phrase = wrapper.find('.phrase').text()
      // Should be one of the defined phrases
      expect(['太棒了！', '厉害！', '真行！']).toContain(phrase)
    })
  })
})