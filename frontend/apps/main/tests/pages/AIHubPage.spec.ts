import { beforeEach, describe, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import AIHubPage from '../../src/pages/AIHubPage.vue'
import { useAIStore } from '../../src/stores/ai'
import { useAgentStore } from '../../src/stores/agent'

const { push, loadAgents } = vi.hoisted(() => ({
  push: vi.fn(),
  loadAgents: vi.fn(() => Promise.resolve()),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
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
    ...actual,
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

vi.mock('../../src/composables/useAIReportWS', () => ({
  useAIReportWS: () => ({
    reset: vi.fn(),
    connect: vi.fn(),
    report: { value: null },
    generatedAt: { value: null },
    errorMessage: { value: '' },
    progressMessage: { value: '' },
  }),
}))

vi.mock('../../src/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: { role: 'owner', display_name: 'Demo User' },
  })),
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
    const wrapper = shallowMount(AIHubPage, {
      global: {
        stubs: {
          AIChatInput: {
            name: 'AIChatInput',
            props: ['modelValue', 'deepThink', 'webSearch'],
            emits: ['update:modelValue', 'update:deepThink', 'update:webSearch', 'submit'],
            template: '<button class="chat-input" @click="$emit(\'submit\', modelValue)">send</button>',
          },
          VanLoading: true,
          AgentGrid: true,
        },
      },
    })

    const input = wrapper.findComponent({ name: 'AIChatInput' })
    await input.vm.$emit('update:modelValue', '我们家净资产是多少？')
    await input.vm.$emit('update:mode', 'smart_full')
    await input.vm.$emit('submit', '我们家净资产是多少？')

    const aiStore = useAIStore()
    expect(aiStore.draftQuery).toBe('我们家净资产是多少？')
    expect(aiStore.deepThinkEnabled).toBe(true)
    expect(push).toHaveBeenCalledWith({
      path: '/ai/chat',
      query: {
        q: '我们家净资产是多少？',
        agentId: 'numina-id', // R4: every entry routes by agentId; default = numina
        newSession: '1',
        deepThink: '1',
      },
    })
  })

  it('calls loadAgents on mount and renders AgentGrid', async () => {
    const wrapper = shallowMount(AIHubPage, {
      global: {
        stubs: {
          AIChatInput: true,
          VanLoading: true,
          AgentGrid: true,
        },
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    expect(loadAgents).toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'AgentGrid' }).exists()).toBe(true)
  })
})
