import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import ErrorMessage from '@/components/ai-chat/ErrorMessage.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': { aiChat: { retry: '重试' } },
  },
})

function mountComponent(props: Record<string, unknown>) {
  return mount(ErrorMessage, {
    props,
    global: { plugins: [i18n] },
  })
}

describe('ErrorMessage — U7', () => {
  it('renders error bar when message is provided', () => {
    const wrapper = mountComponent({ message: '连接中断，点击重试' })
    expect(wrapper.find('.error-message-bar').exists()).toBe(true)
    expect(wrapper.find('.error-text').text()).toBe('连接中断，点击重试')
  })

  it('renders nothing when message is empty', () => {
    const wrapper = mountComponent({ message: '' })
    expect(wrapper.find('.error-message-bar').exists()).toBe(false)
  })

  it('shows retry button when showRetry is true', () => {
    const wrapper = mountComponent({ message: 'error', showRetry: true })
    expect(wrapper.find('.error-retry-btn').exists()).toBe(true)
  })

  it('hides retry button when showRetry is false', () => {
    const wrapper = mountComponent({ message: 'error', showRetry: false })
    expect(wrapper.find('.error-retry-btn').exists()).toBe(false)
  })

  it('emits retry event when retry button clicked', async () => {
    const wrapper = mountComponent({ message: 'error', showRetry: true })
    await wrapper.find('.error-retry-btn').trigger('click')
    expect(wrapper.emitted('retry')).toBeTruthy()
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('has role="alert" for accessibility', () => {
    const wrapper = mountComponent({ message: 'error' })
    expect(wrapper.find('.error-message-bar').attributes('role')).toBe('alert')
  })
})
