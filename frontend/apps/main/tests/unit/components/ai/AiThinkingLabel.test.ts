import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import AiThinkingLabel from '@/components/ai/AiThinkingLabel.vue'

// Mock i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => {
      const translations: Record<string, string> = {
        'aiChat.thinkingLabel': '思考中...',
        'aiChat.thoughtSeconds': `思考了 ${params?.seconds || 'X'}s`,
      }
      return translations[key] || key
    },
  }),
}))

describe('AiThinkingLabel', () => {
  it('renders shimmer text during streaming', () => {
    const wrapper = mount(AiThinkingLabel, {
      props: { isStreaming: true, duration: 0 },
    })
    expect(wrapper.find('.shimmer-text').exists()).toBe(true)
    expect(wrapper.text()).toContain('思考中...')
  })

  it('renders static text when streaming ends', async () => {
    const isStreaming = ref(true)
    const wrapper = mount(AiThinkingLabel, {
      props: {
        isStreaming: isStreaming.value,
        duration: 8,
      },
    })

    // Initially streaming
    expect(wrapper.find('.shimmer-text').exists()).toBe(true)

    // Stop streaming
    isStreaming.value = false
    await wrapper.setProps({ isStreaming: false, duration: 8 })
    await nextTick()

    // Should show static text with duration
    expect(wrapper.text()).toContain('思考了 8s')
    expect(wrapper.find('.ai-thinking-label--done').exists()).toBe(true)
  })

  it('shows less than 1 second for short durations', async () => {
    const wrapper = mount(AiThinkingLabel, {
      props: { isStreaming: false, duration: 0.5 },
    })
    expect(wrapper.text()).toContain('<1')
  })

  it('emits auto-collapse event after 1 second', async () => {
    vi.useFakeTimers()
    const wrapper = mount(AiThinkingLabel, {
      props: { isStreaming: true, duration: 5 },
    })

    // Stop streaming
    await wrapper.setProps({ isStreaming: false, duration: 5 })

    // No event yet
    expect(wrapper.emitted('auto-collapse')).toBeFalsy()

    // Advance 1 second
    vi.advanceTimersByTime(1000)
    await nextTick()

    // Event should be emitted
    expect(wrapper.emitted('auto-collapse')).toBeTruthy()
    expect(wrapper.emitted('auto-collapse')?.length).toBe(1)

    vi.useRealTimers()
  })

  it('does not auto-collapse again after first collapse', async () => {
    vi.useFakeTimers()
    const wrapper = mount(AiThinkingLabel, {
      props: { isStreaming: true, duration: 5 },
    })

    // Stop streaming → collapse
    await wrapper.setProps({ isStreaming: false, duration: 5 })
    vi.advanceTimersByTime(1000)
    await nextTick()

    // Restart streaming
    await wrapper.setProps({ isStreaming: true, duration: 5 })

    // Stop again
    await wrapper.setProps({ isStreaming: false, duration: 5 })
    vi.advanceTimersByTime(1000)
    await nextTick()

    // Should not emit again (only once)
    expect(wrapper.emitted('auto-collapse')?.length).toBe(1)

    vi.useRealTimers()
  })

  it('applies static class for prefers-reduced-motion', () => {
    // Mock matchMedia
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
    }))

    const wrapper = mount(AiThinkingLabel, {
      props: { isStreaming: true, duration: 0 },
    })

    expect(wrapper.find('.ai-thinking-label--static').exists()).toBe(true)

    vi.unstubAllGlobals()
  })
})