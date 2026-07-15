import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import LiveTimer from '../LiveTimer.vue'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (key === 'aiChat.reasoning.thinking') return '思考中'
      if (key === 'aiChat.reasoning.thought') return '已思考'
      return key
    },
  }),
}))

// Stub ShimmerText to avoid CSS animation in tests
const ShimmerTextStub = {
  name: 'ShimmerText',
  props: ['text'],
  template: '<span class="shimmer-text-stub">{{ text }}</span>',
}

function createWrapper(props: { startTime: number; endTime?: number }) {
  return mount(LiveTimer, {
    props,
    global: {
      stubs: {
        ShimmerText: ShimmerTextStub,
      },
    },
  })
}

describe('LiveTimer', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders thinking label with elapsed time when running', () => {
    const now = Date.now()
    const wrapper = createWrapper({ startTime: now - 5000 })

    expect(wrapper.text()).toContain('思考中')
    expect(wrapper.text()).toContain('5s')
  })

  it('updates elapsed time every second', async () => {
    const now = Date.now()
    const wrapper = createWrapper({ startTime: now - 10000 })

    expect(wrapper.text()).toContain('10s')

    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.text()).toContain('11s')

    await vi.advanceTimersByTimeAsync(1000)
    expect(wrapper.text()).toContain('12s')
  })

  it('shows final duration when endTime is set', () => {
    const start = 1000000
    const end = 1030000 // 30 seconds later
    const wrapper = createWrapper({ startTime: start, endTime: end })

    expect(wrapper.text()).toContain('已思考')
    expect(wrapper.text()).toContain('30s')
    // Should NOT show the thinking label
    expect(wrapper.text()).not.toContain('思考中')
  })

  describe('time formatting', () => {
    it('formats seconds (< 60s)', () => {
      const wrapper = createWrapper({ startTime: 0, endTime: 23000 })
      expect(wrapper.text()).toContain('23s')
    })

    it('formats minutes and seconds (60s - 5min)', () => {
      const wrapper = createWrapper({ startTime: 0, endTime: 83000 }) // 1m 23s
      expect(wrapper.text()).toContain('1m 23s')
    })

    it('caps at 5m+ for durations >= 5 minutes', () => {
      const wrapper = createWrapper({ startTime: 0, endTime: 300000 }) // exactly 5min
      expect(wrapper.text()).toContain('5m+')
    })

    it('caps at 5m+ for durations > 5 minutes', () => {
      const wrapper = createWrapper({ startTime: 0, endTime: 600000 }) // 10min
      expect(wrapper.text()).toContain('5m+')
    })
  })

  it('clears interval on unmount', async () => {
    const now = Date.now()
    const wrapper = createWrapper({ startTime: now - 5000 })

    const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
    wrapper.unmount()
    expect(clearIntervalSpy).toHaveBeenCalled()
  })

  it('clears interval when endTime changes from undefined to defined', async () => {
    const now = Date.now()
    const wrapper = createWrapper({ startTime: now - 5000 })

    expect(wrapper.text()).toContain('思考中')

    // Set endTime — should stop the timer
    await wrapper.setProps({ endTime: now })

    expect(wrapper.text()).toContain('已思考')

    const clearIntervalSpy = vi.spyOn(global, 'clearInterval')

    // Advance time — no further updates should happen
    await vi.advanceTimersByTimeAsync(3000)
    expect(wrapper.text()).not.toContain('思考中')
  })
})
