import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import UserBubble from '@/components/chat/UserBubble.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiChat: {
        sendingMessage: '发送中',
        sendFailed: '发送失败',
        resend: '重发',
        retry: '重发',
        copyAria: '复制',
      },
    },
  },
})

// Stub MarkdownContent to render its content prop as plain text
const MarkdownContentStub = {
  template: '<div class="markdown-stub"><slot />{{ content }}</div>',
  props: ['content'],
}

function mountWith(props: Partial<InstanceType<typeof UserBubble>['$props']> = {}) {
  return mount(UserBubble, {
    props: { content: 'hello', displayTime: '14:28', ...props },
    global: {
      plugins: [i18n],
      stubs: { MarkdownContent: MarkdownContentStub },
    },
  })
}

describe('UserBubble — DeerFlow layout', () => {
  it('bubble-content contains the text via MarkdownContent, not the copy button or time', () => {
    const w = mountWith({ content: '你应该接了mcp才对' })
    const bubble = w.find('.bubble-content')
    expect(bubble.exists()).toBe(true)
    expect(bubble.text()).toContain('你应该接了mcp才对')
    // Footer (copy + time) must NOT be inside the bubble
    expect(bubble.find('.bubble-footer').exists()).toBe(false)
    expect(bubble.find('.bubble-time').exists()).toBe(false)
    expect(bubble.find('.action-btn').exists()).toBe(false)
  })

  it('copy button and time are a sibling footer below the bubble', () => {
    const w = mountWith({ content: 'hi', displayTime: '14:28' })
    // Both bubble-content and bubble-footer are direct children of .user-bubble
    const userBubble = w.find('.user-bubble').element
    const bubble = w.find('.bubble-content')
    const footer = w.find('.bubble-footer')
    expect(bubble.element.parentElement).toBe(userBubble)
    expect(footer.element.parentElement).toBe(userBubble)
    // Footer comes after the bubble in DOM order (below it visually)
    const children = Array.from(userBubble.children)
    const bubbleIdx = children.findIndex(el => el.classList.contains('bubble-content'))
    const footerIdx = children.findIndex(el => el.classList.contains('bubble-footer'))
    expect(footerIdx).toBeGreaterThan(bubbleIdx)
    // Footer contains the copy button and the time
    expect(footer.find('.action-btn').exists()).toBe(true)
    expect(footer.find('.bubble-time').text()).toBe('14:28')
  })

  it('send status renders below the bubble, not inside it', () => {
    const w = mountWith({ sendStatus: 'sending' })
    // Status is a direct child of .user-bubble, not inside .bubble-content
    const status = w.find('.send-status.sending')
    expect(status.exists()).toBe(true)
    expect(status.element.parentElement).toBe(w.find('.user-bubble').element)
    expect(w.find('.bubble-content .send-status').exists()).toBe(false)
    expect(status.text()).toContain('发送中')
  })

  it('copy button click emits copy and writes to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })
    const w = mountWith({ content: 'copy me' })
    await w.find('.action-btn').trigger('click')
    expect(writeText).toHaveBeenCalledWith('copy me')
    expect(w.emitted('copy')).toBeTruthy()
  })

  it('failed status shows resend button below the bubble', async () => {
    const w = mountWith({ sendStatus: 'failed' })
    const failed = w.find('.send-status.failed')
    expect(failed.exists()).toBe(true)
    expect(failed.element.parentElement).toBe(w.find('.user-bubble').element)
    const retryBtn = failed.find('.retry-btn')
    expect(retryBtn.exists()).toBe(true)
    await retryBtn.trigger('click')
    expect(w.emitted('retry')).toBeTruthy()
  })
})
