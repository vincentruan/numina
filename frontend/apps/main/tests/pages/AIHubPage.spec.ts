import { describe, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AIHubPage from '../../src/pages/AIHubPage.vue'
import { useAIStore } from '../../src/stores/ai'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('../../src/utils/storage', () => ({
  getUser: () => ({ display_name: 'Demo User' }),
}))

vi.mock('../../src/api/ai', () => ({
  getAIConfig: vi.fn(() => Promise.resolve({ data: { ai_enabled: true } })),
  getAIReport: vi.fn(() => Promise.resolve({ data: { report: null } })),
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
  it('passes draft text and input mode selections to AI chat page', async () => {
    setActivePinia(createPinia())
    push.mockClear()

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
        deepThink: '1',
        webSearch: '1',
      },
    })
  })
})
