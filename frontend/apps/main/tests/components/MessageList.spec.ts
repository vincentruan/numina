import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MessageList from '@/components/ai/MessageList.vue'
import type { ChatMessage, MessageGroup } from '@/types/ai-chat/message-group'

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

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useI18n: () => ({
      t: (key: string) => key,
      locale: { value: 'zh-CN' },
    }),
  }
})

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

  const createGroup = (id: string, type: 'human' | 'assistant' | 'assistant:processing' | 'assistant:present-files' | 'assistant:clarification' | 'assistant:subagent', messages: ChatMessage[]): MessageGroup => ({
    id,
    type,
    messages,
  })

  describe('visibleMessageGroups - version pagination (stable id keys)', () => {
    it('passes through when no superseded groups', () => {
      const messages = [
        createMessage('h1', 'human'),
        createMessage('a1', 'ai'),
      ]

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups: new Map(),
          supersededVersionIndex: new Map(),
        },
        global: { stubs },
      })

      const groups = wrapper.findAll('.message-group-stub')
      expect(groups).toHaveLength(2)
    })

    it('shows live groups when version=1 (default)', () => {
      const humanMsg = createMessage('h1', 'human')
      const liveAssistant = createMessage('a1', 'ai')
      const supersededAssistant = createMessage('a-old', 'ai')

      const messages = [humanMsg, liveAssistant]

      // Key by human message id (stable identifier)
      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [supersededAssistant])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 1]]), // version 1 = show live
        },
        global: { stubs },
      })

      const groups = wrapper.findAll('.message-group-stub')
      expect(groups).toHaveLength(2)
      // Should show human + live assistant (not superseded)
      expect(groups[0].text()).toBe('human')
      expect(groups[1].text()).toBe('ai')
    })

    it('shows superseded groups when version=0', () => {
      const humanMsg = createMessage('h1', 'human')
      const liveAssistant = createMessage('a1', 'ai')
      const supersededAssistant = createMessage('a-old', 'ai')

      const messages = [humanMsg, liveAssistant]

      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [supersededAssistant])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 0]]), // version 0 = show superseded
        },
        global: { stubs },
      })

      const groups = wrapper.findAll('.message-group-stub')
      expect(groups).toHaveLength(2)
      // Should show human + superseded assistant
      expect(groups[0].text()).toBe('human')
      expect(groups[1].text()).toBe('assistant')
    })

    it('handles multiple turns with different versions', () => {
      const h1 = createMessage('h1', 'human')
      const a1 = createMessage('a1', 'ai')
      const h2 = createMessage('h2', 'human')
      const a2 = createMessage('a2', 'ai')

      const messages = [h1, a1, h2, a2]

      // Turn h1: show superseded (version=0)
      // Turn h2: show live (version=1)
      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [createMessage('a-old-1', 'ai')])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 0], ['h2', 1]]),
        },
        global: { stubs },
      })

      const groups = wrapper.findAll('.message-group-stub')
      expect(groups).toHaveLength(4)
      // Turn h1: human + superseded assistant
      expect(groups[0].text()).toBe('human')
      expect(groups[1].text()).toBe('assistant')
      // Turn h2: human + live assistant
      expect(groups[2].text()).toBe('human')
      expect(groups[3].text()).toBe('ai')
    })
  })

  describe('groupToHumanMessageId - stable identifier consistency', () => {
    it('computes human message ids for visible groups (immune to array shifts)', () => {
      const h1 = createMessage('h1', 'human')
      const a1 = createMessage('a1', 'ai')
      const h2 = createMessage('h2', 'human')
      const a2 = createMessage('a2', 'ai')

      const messages = [h1, a1, h2, a2]

      // When version=0 for turn h1, superseded groups replace live groups.
      // Even if the superseded set has MORE groups (shifting h2's position),
      // the pagination for h2 still works because keys are stable ids.
      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [
          createGroup('sup-1', 'assistant', [createMessage('a-old-1', 'ai')]),
          createGroup('sup-2', 'assistant', [createMessage('a-old-2', 'ai')]),
        ]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 0]]),
        },
        global: { stubs },
      })

      const groups = wrapper.findAll('.message-group-stub')
      // With version=0, turn h1 has 3 groups (human + 2 superseded) instead of 2
      expect(groups).toHaveLength(5)
    })
  })

  describe('pagination controls', () => {
    it('renders pagination control when superseded groups exist', () => {
      const h1 = createMessage('h1', 'human')
      const a1 = createMessage('a1', 'ai')

      const messages = [h1, a1]

      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [createMessage('a-old', 'ai')])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 1]]),
        },
        global: { stubs },
      })

      const pagination = wrapper.find('.version-pagination')
      expect(pagination.exists()).toBe(true)
    })

    it('shows prev button when viewing version=1', () => {
      const h1 = createMessage('h1', 'human')
      const a1 = createMessage('a1', 'ai')

      const messages = [h1, a1]

      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [createMessage('a-old', 'ai')])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 1]]),
        },
        global: { stubs },
      })

      const prevBtn = wrapper.find('.version-nav-btn')
      expect(prevBtn.exists()).toBe(true)
      expect(prevBtn.text()).toContain('aiChat.prevVersion')
    })

    it('shows next button when viewing version=0', () => {
      const h1 = createMessage('h1', 'human')
      const a1 = createMessage('a1', 'ai')

      const messages = [h1, a1]

      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [createMessage('a-old', 'ai')])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 0]]),
        },
        global: { stubs },
      })

      const nextBtn = wrapper.find('.version-nav-btn')
      expect(nextBtn.exists()).toBe(true)
      expect(nextBtn.text()).toContain('aiChat.nextVersion')
    })

    it('emits showPrevVersion with human message id when prev button clicked', async () => {
      const h1 = createMessage('h1', 'human')
      const a1 = createMessage('a1', 'ai')

      const messages = [h1, a1]

      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [createMessage('a-old', 'ai')])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 1]]),
        },
        global: { stubs },
      })

      const prevBtn = wrapper.find('.version-nav-btn')
      await prevBtn.trigger('click')

      expect(wrapper.emitted('showPrevVersion')).toBeTruthy()
      // Now emits the stable human message id, not a positional index
      expect(wrapper.emitted('showPrevVersion')![0]).toEqual(['h1'])
    })

    it('emits showNextVersion with human message id when next button clicked', async () => {
      const h1 = createMessage('h1', 'human')
      const a1 = createMessage('a1', 'ai')

      const messages = [h1, a1]

      const supersededGroups = new Map<string, MessageGroup[]>([
        ['h1', [createGroup('sup-1', 'assistant', [createMessage('a-old', 'ai')])]],
      ])

      const wrapper = mount(MessageList, {
        props: {
          messages,
          isStreaming: false,
          threadId: 'test-thread',
          supersededGroups,
          supersededVersionIndex: new Map([['h1', 0]]),
        },
        global: { stubs },
      })

      const nextBtn = wrapper.find('.version-nav-btn')
      await nextBtn.trigger('click')

      expect(wrapper.emitted('showNextVersion')).toBeTruthy()
      // Now emits the stable human message id, not a positional index
      expect(wrapper.emitted('showNextVersion')![0]).toEqual(['h1'])
    })
  })
})
