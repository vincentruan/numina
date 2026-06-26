import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import ChatHeader from '../../src/components/ai/ChatHeader.vue'
import { useAgentStore } from '../../src/stores/agent'

// Mock composables
vi.mock('@/composables/ai-chat/useThreadChat', () => ({
  useThreadChat: () => ({
    messages: { value: [] },
    isLoading: { value: false },
    isStreaming: { value: false },
    error: { value: null },
    tokenUsage: { value: null },
    planningSteps: { value: [] },
    suggestions: { value: [] },
    runId: { value: null },
    sendMessage: vi.fn(),
    cancelStream: vi.fn(),
    loadHistory: vi.fn(),
    retry: vi.fn(),
  }),
}))

vi.mock('@/composables/ai-chat/useArtifacts', () => ({
  useArtifacts: () => ({
    selectedArtifact: { value: null },
    open: { value: false },
    select: vi.fn(),
    deselect: vi.fn(),
  }),
}))

// Mock API
vi.mock('@/api/ai-chat', () => ({
  getThread: vi.fn(() => Promise.resolve({ thread_id: 'test-thread', title: 'Test Thread' })),
  createThread: vi.fn(() => Promise.resolve({ thread_id: 'new-thread' })),
  updateThread: vi.fn(() => Promise.resolve({ thread_id: 'test-thread', title: 'Updated Title' })),
}))

// Mock router
const mockPush = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useRouter: () => ({ push: mockPush }),
  }
})

// Mock Vant functional APIs
vi.mock('vant', () => ({
  showFailToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showDialog: vi.fn(() => Promise.resolve()),
}))

// Mock vue-i18n
vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useI18n: () => ({ t: (key: string) => key }),
  }
})

// Mock history.replaceState used by chatSession store
vi.spyOn(globalThis.history, 'replaceState').mockImplementation(() => {})

// Stub Vant components
const vantStubs = {
  VanDialog: { template: '<div class="van-dialog"><slot /></div>', props: ['show', 'title', 'showCancelButton', 'loading'] },
  VanField: { template: '<input class="van-field" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />', props: ['modelValue', 'placeholder', 'autofocus', 'clearable', 'maxlength', 'showWordLimit'] },
  VanLoading: { template: '<div class="van-loading"></div>', props: ['size'] },
}

describe('ChatHeader', () => {
  let wrapper: VueWrapper<any>
  let agentStore: ReturnType<typeof useAgentStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    agentStore = useAgentStore()
    mockPush.mockClear()
    vi.clearAllMocks()
  })

  describe('Agent Info Popup', () => {
    it('shows agent logo button when activeAgent exists', async () => {
      agentStore.systemAgents = [
        { id: '1', agent_name: 'numina', display_name: 'Numina', description: 'AI Assistant', icon: '🤖', is_enabled: true } as any,
      ]

      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: agentStore.systemAgents[0],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const agentBtn = wrapper.find('.header-agent-logo-btn')
      expect(agentBtn.exists()).toBe(true)
      expect(agentBtn.attributes('aria-label')).toBe('aiChat.agentInfoAria')
    })

    it('hides agent logo button when no agents available', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.header-agent-logo-btn').exists()).toBe(false)
    })

    it('toggles agent info popup on click', async () => {
      agentStore.systemAgents = [
        { id: '1', agent_name: 'numina', display_name: 'Numina', description: 'AI Assistant', icon: '🤖', is_enabled: true } as any,
      ]

      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: agentStore.systemAgents[0],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.agent-info-popup').exists()).toBe(false)

      await wrapper.find('.header-agent-logo-btn').trigger('click')
      await nextTick()

      expect(wrapper.find('.agent-info-popup').exists()).toBe(true)
      expect(wrapper.find('.agent-info-popup').attributes('role')).toBe('dialog')
      expect(wrapper.find('.agent-info-popup').attributes('aria-label')).toBe('Agent information')
    })
  })

  describe('Header Title Computed', () => {
    it('returns "New Chat" when no active thread', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.headerTitle).toBe('aiChat.newChat')
    })

    it('returns thread title when active thread exists', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-1',
          sessions: [
            { thread_id: 'thread-1', title: 'My Conversation', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.headerTitle).toBe('My Conversation')
    })

    it('returns "New Chat" if thread has no title', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-2',
          sessions: [
            { thread_id: 'thread-2', title: '', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.headerTitle).toBe('aiChat.newChat')
    })
  })

  describe('Title Scroll Animation', () => {
    it('needs scroll when title length > 8', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-3',
          sessions: [
            { thread_id: 'thread-3', title: 'This is a very long conversation title', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.titleNeedsScroll).toBe(true)
      expect(wrapper.find('.header-title-container').classes()).toContain('needs-scroll')
    })

    it('does not need scroll for short titles (<=8 chars)', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-4',
          sessions: [
            { thread_id: 'thread-4', title: 'Short', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.titleNeedsScroll).toBe(false)
      expect(wrapper.find('.header-title-container').classes()).not.toContain('needs-scroll')
    })

    it('boundary case: exactly 8 chars does not scroll', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-5',
          sessions: [
            { thread_id: 'thread-5', title: '12345678', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.titleNeedsScroll).toBe(false)
    })

    it('boundary case: 9 chars scrolls', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-6',
          sessions: [
            { thread_id: 'thread-6', title: '123456789', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.titleNeedsScroll).toBe(true)
    })
  })

  describe('Can Edit Title Computed', () => {
    it('can edit when active thread has non-"New Chat" title', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-7',
          sessions: [
            { thread_id: 'thread-7', title: 'Editable Title', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.canEditTitle).toBe(true)
      expect(wrapper.find('.header-edit-btn').exists()).toBe(true)
    })

    it('cannot edit when no active thread', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.canEditTitle).toBeFalsy()
      expect(wrapper.find('.header-edit-btn').exists()).toBe(false)
    })

    it('cannot edit when title is "New Chat"', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-8',
          sessions: [
            { thread_id: 'thread-8', title: '', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.canEditTitle).toBe(false)
      expect(wrapper.find('.header-edit-btn').exists()).toBe(false)
    })
  })

  describe('Navigation Functions', () => {
    it('onOpenHistory pushes /ai/chat/history to router', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.onOpenHistory()
      expect(mockPush).toHaveBeenCalledWith('/ai/chat/history')
    })

    it('back button pushes /ai to router', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.onBack()
      expect(mockPush).toHaveBeenCalledWith('/ai')
    })
  })

  describe('Events', () => {
    it('emits newChat when new chat button clicked', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const newChatBtn = wrapper.findAll('.header-btn').find(btn => btn.attributes('aria-label') === 'aiChat.newChatAria')
      expect(newChatBtn).toBeDefined()
      await newChatBtn!.trigger('click')

      expect(wrapper.emitted('newChat')).toBeTruthy()
    })

    it('emits titleUpdated when title successfully updated', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-1',
          sessions: [
            { thread_id: 'thread-1', title: 'Old Title', updated_at: Date.now() } as any,
          ],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.editTitleInput = 'New Title'
      await vm.onConfirmEditTitle()

      expect(wrapper.emitted('titleUpdated')).toBeTruthy()
      expect(wrapper.emitted('titleUpdated')![0]).toEqual(['thread-1', 'New Title'])
    })
  })

  describe('Header Buttons Rendering', () => {
    it('renders back button with correct aria-label', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const buttons = wrapper.findAll('.header-btn')
      const backBtn = buttons[0]
      expect(backBtn.attributes('aria-label')).toBe('common.back')
    })

    it('renders history button with correct aria-label', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const buttons = wrapper.findAll('.header-btn')
      const historyBtn = buttons[1]
      expect(historyBtn.attributes('aria-label')).toBe('aiChat.historyAria')
    })

    it('renders new chat button with correct aria-label', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const newChatBtn = wrapper.find('.header-actions .header-btn')
      expect(newChatBtn.attributes('aria-label')).toBe('aiChat.newChatAria')
    })
  })

  describe('Accessibility', () => {
    it('all header buttons have aria-labels', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-1',
          sessions: [
            { thread_id: 'thread-1', title: 'Test', updated_at: Date.now() } as any,
          ],
          activeAgent: { id: '1', agent_name: 'numina', display_name: 'Numina', description: 'AI', icon: '🤖', is_enabled: true } as any,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const buttons = wrapper.findAll('.header-btn')
      for (const btn of buttons) {
        const ariaLabel = btn.attributes('aria-label')
        expect(ariaLabel).toBeDefined()
        expect(ariaLabel).not.toBe('')
      }
    })

    it('SVG icons in header have aria-hidden', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
          activeAgent: null,
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      // Check header SVGs (back button, history button, edit button, new chat button)
      const headerSvgs = wrapper.findAll('.chat-header svg')
      for (const svg of headerSvgs) {
        expect(svg.attributes('aria-hidden')).toBe('true')
      }
    })
  })
})