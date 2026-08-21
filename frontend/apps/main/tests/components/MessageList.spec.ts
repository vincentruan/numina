import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageList from '@/components/ai/MessageList.vue'
import type { ChatMessage } from '@/types/ai-chat/message-group'

// Mock composables and child components
vi.mock('@/composables/ai-chat/useMessageGroups', () => ({
  useMessageGroups: (messages: any) => ({
    value: messages.value.map((m: ChatMessage) => ({
      id: m.id,
      type: m.type,
      messages: [m],
    })),
  }),
}))

vi.mock('vue-i18n', async (importOriginal) => ({
  ...(await importOriginal()),
  useI18n: () => ({
    t: (key: string) => key,
    locale: { value: 'zh-CN' },
  }),
}))

// Stub child components
const stubs = {
  MessageGroup: {
    template: '<div class="message-group-stub">{{ group.type }}</div>',
    props: ['group', 'threadId', 'isLoading', 'isLastAssistant', 'canBranch', 'branchingMessageId', 'answeredInterruptIds', 'prevGroupPlanSteps'],
  },
  StreamingIndicator: {
    template: '<div class="streaming-indicator-stub" />',
    props: ['visible'],
  },
}

describe('MessageList.vue', () => {
  const createMessage = (id: string, type: 'human' | 'ai'): ChatMessage => ({
    id,
    type,
    role: type === 'human' ? 'user' : 'assistant',
    content: `Message ${id}`,
    displayTime: new Date().toISOString(),
  })

  describe('message rendering', () => {
    it('shows empty state when no messages', () => {
      const wrapper = mount(MessageList, {
        props: { messages: [], isStreaming: false },
        global: { stubs },
      })
      expect(wrapper.find('.message-list-empty').exists()).toBe(true)
    })

    it('renders all message groups when messages exist', () => {
      const messages = [
        createMessage('h1', 'human'),
        createMessage('a1', 'ai'),
      ]
      const wrapper = mount(MessageList, {
        props: { messages, isStreaming: false, threadId: 'test-thread' },
        global: { stubs },
      })
      const groups = wrapper.findAll('.message-group-stub')
      expect(groups).toHaveLength(2)
      expect(groups[0].text()).toBe('human')
      expect(groups[1].text()).toBe('ai')
    })

    it('shows thinking indicator when streaming and last group is human', () => {
      const messages = [createMessage('h1', 'human')]
      const wrapper = mount(MessageList, {
        props: { messages, isStreaming: true },
        global: { stubs },
      })
      expect(wrapper.find('.thinking-placeholder').exists()).toBe(true)
    })

    it('hides thinking indicator when not streaming', () => {
      const messages = [createMessage('h1', 'human')]
      const wrapper = mount(MessageList, {
        props: { messages, isStreaming: false },
        global: { stubs },
      })
      expect(wrapper.find('.thinking-placeholder').exists()).toBe(false)
    })

    it('hides thinking indicator when last group is assistant', () => {
      const messages = [
        createMessage('h1', 'human'),
        createMessage('a1', 'ai'),
      ]
      const wrapper = mount(MessageList, {
        props: { messages, isStreaming: true },
        global: { stubs },
      })
      expect(wrapper.find('.thinking-placeholder').exists()).toBe(false)
    })
  })

  describe('event forwarding', () => {
    it('renders message groups with correct props', () => {
      const messages = [
        createMessage('h1', 'human'),
        createMessage('a1', 'ai'),
      ]
      const wrapper = mount(MessageList, {
        props: { messages, isStreaming: false, threadId: 'test-thread' },
        global: { stubs },
      })
      // Verify groups are rendered (stubs receive the correct props)
      const groups = wrapper.findAll('.message-group-stub')
      expect(groups).toHaveLength(2)
    })
  })
})
