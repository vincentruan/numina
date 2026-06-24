import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import StreamingIndicator from '@/components/ai-chat/StreamingIndicator.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': { aiChat: { streaming: 'AI 正在回答' } },
  },
})

function mountComponent(props: { visible: boolean }) {
  return mount(StreamingIndicator, {
    props,
    global: { plugins: [i18n] },
  })
}

describe('StreamingIndicator — U6', () => {
  it('renders three bouncing dots when visible', () => {
    const wrapper = mountComponent({ visible: true })
    expect(wrapper.find('.streaming-indicator').exists()).toBe(true)
    expect(wrapper.findAll('.stream-dot')).toHaveLength(3)
  })

  it('renders nothing when not visible', () => {
    const wrapper = mountComponent({ visible: false })
    expect(wrapper.find('.streaming-indicator').exists()).toBe(false)
  })

  it('has role="status" for accessibility when visible', () => {
    const wrapper = mountComponent({ visible: true })
    expect(wrapper.find('.streaming-indicator').attributes('role')).toBe('status')
  })

  it('renders three dots with nth-child staggered animation (via CSS)', () => {
    const wrapper = mountComponent({ visible: true })
    const dots = wrapper.findAll('.stream-dot')
    expect(dots).toHaveLength(3)
    // Animation delay is applied via CSS :nth-child selectors, not inline styles
    // Verify the dots are present and the component structure is correct
    expect(dots[0].classes()).toContain('stream-dot')
  })
})
