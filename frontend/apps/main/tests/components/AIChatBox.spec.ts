import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { flushPromises } from '@vue/test-utils'

import AIChatBox from '../../src/components/ai/AIChatBox.vue'
import { useAgentStore } from '../../src/stores/agent'
import { useChatSessionStore } from '../../src/stores/chatSession'

// Mock composables
vi.mock('@/composables/ai-chat/useThreadChat', () => ({
  useThreadChat: () => ({
    messages: { value: [] },
    visibleMessages: { value: [] },
    isLoading: { value: false },
    isStreaming: { value: false },
    error: { value: null },
    tokenUsage: { value: null },
    planningSteps: { value: [] },
    suggestions: { value: [] },
    answeredInterruptIds: { value: new Set() },
    interruptErrorId: { value: null },
    runId: { value: null },
    todos: { value: [] },
    serverGoal: { value: undefined },
    sendMessage: vi.fn(),
    cancelStream: vi.fn(),
    loadHistory: vi.fn(),
    retry: vi.fn(),
    clearMessages: vi.fn(),
    resumeInterrupt: vi.fn(),
    handleCompact: vi.fn(),
    handleGoalCommand: vi.fn(),
  }),
  // parseGoalCommand is a pure module-level export used by AIChatBox to detect
  // /goal commands before they reach the agent.
  parseGoalCommand: vi.fn(() => null),
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

// Mock ai-tasks API (U19 task preflight)
vi.mock('@/api/ai-tasks', () => ({
  getChatTaskForSession: vi.fn(() => Promise.resolve(null)),
  cancelTaskById: vi.fn(() => Promise.resolve()),
}))

// A1b (Plan B T6): useAiContext imports getAiContext from @/api/ai, which
// otherwise pulls in the real http/router/i18n graph. Mock the module so the
// composable stays lightweight in this component-render test.
vi.mock('@/api/ai', () => ({
  getAiContext: vi.fn(),
}))

// Mock router - useRouter returns mock push function; useRoute returns empty
// query (A1b useAiContext reads route.query.source/id).
const mockPush = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useRouter: () => ({ push: mockPush }),
    useRoute: () => ({ query: {} }),
  }
})

// Mock Vant functional APIs
vi.mock('vant', () => ({
  showFailToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showDialog: vi.fn(() => Promise.resolve()),
}))

// Mock vue-i18n - keep createI18n for proper initialization
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
  VanDialog: { template: '<div class="van-dialog"><slot /></div>', props: ['show', 'title', 'showCancelButton'] },
  VanField: { template: '<input class="van-field" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />', props: ['modelValue', 'placeholder', 'autofocus', 'clearable', 'maxlength', 'showWordLimit'] },
  VanLoading: { template: '<div class="van-loading"></div>', props: ['size'] },
}

describe('AIChatBox', () => {
  let wrapper: VueWrapper<any>
  let agentStore: ReturnType<typeof useAgentStore>
  let chatSessionStore: ReturnType<typeof useChatSessionStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    agentStore = useAgentStore()
    chatSessionStore = useChatSessionStore()
    mockPush.mockClear()
    vi.clearAllMocks()
  })

  describe('Active Agent Computed', () => {
    it('activeAgent defaults to numina agent', async () => {
      agentStore.systemAgents = [
        { id: '1', agent_name: 'other', display_name: 'Other Agent', description: 'Other', icon: '⚙️', is_enabled: true } as any,
        { id: '2', agent_name: 'numina', display_name: 'Numina', description: 'Numina AI', icon: '🤖', is_enabled: true } as any,
      ]

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.activeAgent?.agent_name).toBe('numina')
      expect(vm.activeAgent?.display_name).toBe('Numina')
    })

    it('falls back to first agent if numina not found', async () => {
      agentStore.systemAgents = [
        { id: '1', agent_name: 'other', display_name: 'Other Agent', description: 'Other', icon: '⚙️', is_enabled: true } as any,
      ]

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.activeAgent?.agent_name).toBe('other')
      expect(vm.activeAgent?.display_name).toBe('Other Agent')
    })

    it('returns null when systemAgents is empty', async () => {
      agentStore.systemAgents = []

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.activeAgent).toBeNull()
    })
  })

  describe('ChatHeader Integration', () => {
    it('passes expected props to ChatHeader', async () => {
      agentStore.systemAgents = [
        { id: '1', agent_name: 'numina', display_name: 'Numina', description: 'AI', icon: '🤖', is_enabled: true } as any,
      ]

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const chatHeader = wrapper.findComponent({ name: 'ChatHeader' })
      expect(chatHeader.exists()).toBe(true)
      // ChatHeader no longer receives activeAgent prop; it receives
      // activeThreadId, sessions, realtimeTokenUsage, isStreaming
      expect(chatHeader.props('activeThreadId')).toBeDefined()
      expect(chatHeader.props('sessions')).toBeDefined()
    })

    it('passes activeThreadId to ChatHeader', async () => {
      chatSessionStore.activeThreadId = 'thread-1'

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      // Wait for async onMounted to complete (initialLoading becomes false)
      await flushPromises()

      const chatHeader = wrapper.findComponent({ name: 'ChatHeader' })
      expect(chatHeader.props('activeThreadId')).toBe('thread-1')
    })

    it('passes sessions to ChatHeader', async () => {
      chatSessionStore.sessions = [
        { thread_id: 'thread-1', title: 'Test Session', updated_at: Date.now() } as any,
      ]

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const chatHeader = wrapper.findComponent({ name: 'ChatHeader' })
      expect(chatHeader.props('sessions').length).toBe(1)
      expect(chatHeader.props('sessions')[0].thread_id).toBe('thread-1')
    })
  })

  describe('handleNewChat', () => {
    it('clears active thread', async () => {
      chatSessionStore.activeThreadId = 'existing-thread'

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.handleNewChat()
      expect(chatSessionStore.activeThreadId).toBeNull()
    })
  })

  describe('handleTitleUpdated', () => {
    it('updates session title in store', async () => {
      chatSessionStore.sessions = [
        { thread_id: 'thread-1', title: 'Old Title', updated_at: Date.now() } as any,
      ]

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.handleTitleUpdated('thread-1', 'New Title')

      expect(chatSessionStore.sessions[0].title).toBe('New Title')
    })

    it('ignores update for unknown thread', async () => {
      chatSessionStore.sessions = [
        { thread_id: 'thread-1', title: 'Title', updated_at: Date.now() } as any,
      ]

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.handleTitleUpdated('unknown-thread', 'New Title')

      // Should not change existing session
      expect(chatSessionStore.sessions[0].title).toBe('Title')
    })
  })

  describe('Artifact Handling', () => {
    it('handleArtifactTap validates artifact kind', async () => {
      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      // Test valid kind
      vm.handleArtifactTap({ id: '1', title: 'Test', kind: 'data' })
      // Test invalid kind falls back to 'other'
      vm.handleArtifactTap({ id: '2', title: 'Test', kind: 'invalid-kind' })
      // Function should not throw
    })
  })

  describe('Welcome Mode', () => {
    it('shows WelcomePage when isWelcomeMode', async () => {
      chatSessionStore.activeThreadId = null

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.findComponent({ name: 'WelcomePage' }).exists()).toBe(true)
    })

    it('shows MessageList when not in welcome mode', async () => {
      chatSessionStore.activeThreadId = 'thread-1'

      wrapper = mount(AIChatBox, {
        global: { stubs: vantStubs },
      })

      // Wait for async onMounted to complete (initialLoading becomes false)
      await flushPromises()

      expect(wrapper.findComponent({ name: 'MessageList' }).exists()).toBe(true)
    })
  })
})