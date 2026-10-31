import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

// Stub composables used by LearningSessionPage
vi.mock('@/composables/useLearningChat', () => ({
  useLearningChat: () => ({
    messages: [
      {
        id: 'm1',
        role: 'assistant',
        content: 'Let me help you.',
        toolCall: { name: 'get_hint', arguments: { topic: 'fractions' } },
      },
      {
        id: 'm2',
        role: 'tool',
        content: '',
        toolResult: { name: 'get_hint', output: { hint: 'Think about equal parts' } },
      },
      { id: 'm3', role: 'assistant', content: 'Here is the answer.' },
    ],
    status: 'idle',
    currentStreamText: '',
    error: '',
    isStreaming: false,
    isCompleted: true,
    startAssessment: vi.fn(),
    sendMessage: vi.fn(),
    disconnect: vi.fn(),
  }),
}))

vi.mock('@/composables/usePageLoading', () => ({
  usePageLoading: () => ({ increment: vi.fn(), decrement: vi.fn() }),
}))

vi.mock('@/composables/useLocalizedTopic', () => ({
  useLocalizedTopic: () => ({ topicDisplayName: (t: { name: string }) => t.name }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 's1' } }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

vi.mock('@/api/learning', () => ({
  getSession: vi.fn().mockResolvedValue({
    id: 's1',
    thread_id: 'th1',
    session_type: 'tutorial',
    topic_id: 't1',
  }),
  getTopicDetail: vi.fn().mockResolvedValue({
    id: 't1',
    name: 'Fractions',
    name_zh: '分数',
    subject: 'mathematics',
  }),
  endSession: vi.fn(),
}))

const { default: LearningSessionPage } = await import('./LearningSessionPage.vue')

function mountPage() {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
  return mount(LearningSessionPage, {
    global: {
      plugins: [i18n],
      stubs: {
        RoleShimmer: true,
      },
    },
  })
}

describe('LearningSessionPage — tool-call hiding (R12)', () => {
  it('does not render any <details> elements in the chat area', async () => {
    const wrapper = mountPage()
    // Wait for the component to finish loading
    await vi.waitFor(() => {
      expect(wrapper.find('.chat-area').exists()).toBe(true)
    })
    // Key assertion: no <details> elements anywhere in the rendered output
    expect(wrapper.findAll('details')).toHaveLength(0)
    expect(wrapper.findAll('.tool-details')).toHaveLength(0)
  })

  it('does not render tool-call or tool-result CSS classes', async () => {
    const wrapper = mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('.chat-area').exists()).toBe(true)
    })
    expect(wrapper.find('.tool-details__summary').exists()).toBe(false)
    expect(wrapper.find('.tool-details__content').exists()).toBe(false)
  })

  it('renders assistant text messages normally', async () => {
    const wrapper = mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('.chat-area').exists()).toBe(true)
    })
    const textEls = wrapper.findAll('.chat-msg__text')
    const visibleText = textEls.map((el) => el.text())
    // Text messages render normally
    expect(visibleText).toContain('Let me help you.')
    expect(visibleText).toContain('Here is the answer.')
  })

  it('does not expose tool-call names or JSON arguments in the DOM', async () => {
    const wrapper = mountPage()
    await vi.waitFor(() => {
      expect(wrapper.find('.chat-area').exists()).toBe(true)
    })
    const html = wrapper.html()
    // Tool names and argument JSON should not appear anywhere
    expect(html).not.toContain('get_hint')
    expect(html).not.toContain('toolCall')
    expect(html).not.toContain('toolResult')
  })
})
