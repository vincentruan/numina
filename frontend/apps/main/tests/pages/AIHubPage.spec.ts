import { beforeEach, describe, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import AIHubPage from '../../src/pages/AIHubPage.vue'
import { useAIStore } from '../../src/stores/ai'

const push = vi.fn()
const { getAICapabilities } = vi.hoisted(() => ({
  getAICapabilities: vi.fn(() =>
    Promise.resolve({
      data: [
        {
          id: 'chat',
          name: 'AI 问答',
          description: '自由对话助手',
          ui: { route: '/ai/chat' },
        },
        {
          id: 'report',
          name: '资产体检',
          description: '综合健康评分',
          ui: { route: '/ai/report' },
        },
      ],
    }),
  ),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('../../src/utils/storage', () => ({
  getUser: () => ({ display_name: 'Demo User' }),
}))

vi.mock('../../src/api/ai', () => ({
  getAIConfig: vi.fn(() => Promise.resolve({ data: { ai_enabled: true } })),
  getAIReport: vi.fn(() => Promise.resolve({ data: { report: null } })),
  getAICapabilities,
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

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('vant', () => ({
  showToast: vi.fn(),
}))

describe('AIHubPage chat entry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
    getAICapabilities.mockClear()
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
        },
      },
    })

    const input = wrapper.findComponent({ name: 'AIChatInput' })
    await input.vm.$emit('update:modelValue', '我们家净资产是多少？')
    await input.vm.$emit('update:deepThink', true)
    await input.vm.$emit('update:webSearch', true)
    await input.vm.$emit('submit', '我们家净资产是多少？')

    const aiStore = useAIStore()
    expect(aiStore.draftQuery).toBe('我们家净资产是多少？')
    expect(aiStore.deepThinkEnabled).toBe(true)
    expect(aiStore.webSearchEnabled).toBe(true)
    expect(push).toHaveBeenCalledWith({
      path: '/ai/chat',
      query: {
        q: '我们家净资产是多少？',
        newSession: '1',
        deepThink: '1',
        webSearch: '1',
      },
    })
  })

  it('renders capability cards from the registry and navigates by route', async () => {
    const wrapper = shallowMount(AIHubPage, {
      global: {
        stubs: {
          AIChatInput: true,
          VanLoading: true,
        },
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await nextTick()

    expect(getAICapabilities).toHaveBeenCalled()
    expect(wrapper.text()).toContain('AI 问答')
    expect(wrapper.text()).toContain('资产体检')

    await wrapper.find('[data-testid="capability-chat"]').trigger('click')

    expect(push).toHaveBeenCalledWith('/ai/chat')
  })
})
