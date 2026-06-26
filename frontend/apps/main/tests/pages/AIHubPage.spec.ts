import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

// Increased timeout to allow Vue watchers and async callbacks to settle in tests
// 0ms was insufficient for watcher propagation in shallowMount scenarios
const flushPromises = () => new Promise((resolve) => setTimeout(resolve, 50))

import AIHubPage from '../../src/pages/AIHubPage.vue'
import { useAIStore } from '../../src/stores/ai'
import { useAgentStore } from '../../src/stores/agent'

const { push, loadAgents, aiStoreMock } = vi.hoisted(() => ({
  push: vi.fn(),
  loadAgents: vi.fn(() => Promise.resolve()),
  aiStoreMock: {
    aiEnabled: true,
    draftQuery: '',
    deepThinkEnabled: false,
    webSearchEnabled: false,
    fetchConfig: vi.fn(() => Promise.resolve()),
  },
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useRouter: () => ({ push }),
    createRouter: vi.fn(() => ({
      push,
      beforeEach: vi.fn(),
      afterEach: vi.fn(),
    })),
  }
})

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useI18n: () => ({ t: (key: string) => key }),
  }
})

vi.mock('../../src/utils/storage', () => ({
  getUser: () => ({ display_name: 'Demo User' }),
}))

vi.mock('../../src/api/ai', () => ({
  getAIConfig: vi.fn(() => Promise.resolve({ data: { ai_enabled: true } })),
  getAIReport: vi.fn(() => Promise.resolve({ data: { report: null } })),
  getAITask: vi.fn(() => Promise.resolve({ status: 'idle' })),
}))

vi.mock('../../src/composables/useAIReportStream', () => ({
  useAIReportStream: () => ({
    reset: vi.fn(),
    connect: vi.fn(),
    report: { value: null },
    generatedAt: { value: null },
    errorMessage: { value: '' },
    progressMessage: { value: '' },
  }),
}))

vi.mock('../../src/stores/ai', () => ({
  useAIStore: vi.fn(() => aiStoreMock),
}))

vi.mock('../../src/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: { role: 'owner', display_name: 'Demo User' },
  })),
}))

vi.mock('../../src/api/sessions', () => ({
  getSystemDefaultSession: vi.fn(() => Promise.resolve({ data: { session: null } })),
}))

vi.mock('../../src/stores/agent', () => ({
  useAgentStore: vi.fn(() => ({
    tasks: [],
    // U8/U9: AgentGrid prop renamed; AIHubPage now reads systemAgents +
    // customAgents. The recipient chip (U11) defaults to numina, so the
    // mock must include an enabled numina row for startChat to fire.
    systemAgents: [
      {
        id: 'numina-id',
        agent_name: 'numina',
        display_name: '数鸣',
        description: '家庭财务大使',
        is_enabled: true,
      },
      {
        id: 'ai-assistant-id',
        agent_name: 'ai-assistant',
        display_name: 'AI 问答',
        description: '通用对话助手',
        is_enabled: true,
      },
    ],
    builtinAgents: [],
    customAgents: [],
    loadAgents,
  })),
}))


vi.mock('vant', () => ({
  showToast: vi.fn(),
}))

describe('AIHubPage chat entry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
    loadAgents.mockClear()
  })

  it('passes draft text and input mode selections to AI chat page', async () => {
    const wrapper = mount(AIHubPage, {
      global: {
        stubs: {
          InputBox: {
            name: 'InputBox',
            props: ['modelValue', 'webSearch', 'isWelcomeMode', 'status'],
            emits: ['update:modelValue', 'update:webSearch', 'submit'],
            template: '<button class="chat-input" @click="$emit(\'submit\', modelValue)">send</button>',
          },
          AIHubSkeleton: true,
          VanLoading: true,
          VanIcon: true,
          VanButton: true,
          VanActionSheet: true,
          VanCellGroup: true,
          VanCell: true,
          AgentCard: true,
          NuminaAgentCard: true,
          AIBrainIcon: true,
          SvgIcon: true,
        },
      },
    })

    // Wait for onMounted to complete and initialLoading to become false
    // onMounted calls: fetchConfig(), loadAgents(), loadReport() -> then initialLoading = false
    await flushPromises()
    await nextTick()

    // Manually select agent since the watcher may not trigger properly with mocked store
    wrapper.vm.selectAgent({
      id: 'numina-id',
      agent_name: 'numina',
      display_name: '数鸣',
      description: '家庭财务大使',
      is_enabled: true,
    } as any)
    wrapper.vm.chatInput = '我们家净资产是多少？'
    wrapper.vm.chatMode = 'thinking'
    wrapper.vm.webSearch = true
    await nextTick()

    const input = wrapper.findComponent({ name: 'InputBox' })

    // Trigger submit which calls submitChatFromInput
    input.vm.$emit('submit', {
      text: '我们家净资产是多少？',
      model_name: '',
      mode: 'thinking',
      thinking_enabled: true,
      is_plan_mode: false,
      subagent_enabled: false,
      reasoning_effort: 'low',
      thread_id: undefined,
    })
    await flushPromises()

    const aiStore = useAIStore()
    expect(aiStore.draftQuery).toBe('我们家净资产是多少？')
    expect(aiStore.deepThinkEnabled).toBe(true)
    expect(aiStore.webSearchEnabled).toBe(true)
    expect(push).toHaveBeenCalledWith({
      path: '/ai/chat',
      query: {
        q: '我们家净资产是多少？',
        agentId: 'numina-id', // R4: every entry routes by agentId; default = numina
        newSession: '1',
        deepThink: '1',
        webSearch: '1',
      },
    })
  })

  it('calls loadAgents on mount and renders agent cards', async () => {
    const wrapper = shallowMount(AIHubPage, {
      global: {
        stubs: {
          InputBox: true,
          AIHubSkeleton: true,
          VanLoading: true,
          VanIcon: true,
          VanButton: true,
          VanActionSheet: true,
          VanCellGroup: true,
          VanCell: true,
          AgentCard: true,
          NuminaAgentCard: true,
          AIBrainIcon: true,
          SvgIcon: true,
        },
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    expect(loadAgents).toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'NuminaAgentCard' }).exists()).toBe(true)
  })
})
