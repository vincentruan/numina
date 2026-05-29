import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AIChatPage from '../../src/pages/AIChatPage.vue'
import { useAIStore } from '../../src/stores/ai'

const { sendChatEventStream } = vi.hoisted(() => ({
  sendChatEventStream: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useRoute: () => ({ query: {} }),
    useRouter: () => ({
      push: vi.fn(),
      replace: vi.fn(),
      go: vi.fn(),
      back: vi.fn(),
    }),
  }
})

vi.mock('../../src/api/ai', () => ({
  sendChatEventStream,
  getAIConfig: vi.fn(() => Promise.resolve({ data: { ai_enabled: true } })),
  getChatHistory: vi.fn(() => Promise.resolve({ data: [] })),
  clearChatHistory: vi.fn(() => Promise.resolve()),
  markChatRead: vi.fn(() => Promise.resolve()),
}))

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }),
  }
})

vi.mock('vant', () => ({
  showConfirmDialog: vi.fn(() => Promise.resolve()),
  showToast: vi.fn(),
}))

// Mock loading composable to avoid import.meta.hot issues
vi.mock('../../packages/auth/src/composables/loading', () => ({
  useLoading: () => ({
    isLoading: { value: false },
    setLoading: vi.fn(),
  }),
}))

function streamReaderFromText(text: string) {
  return {
    read: vi
      .fn()
      .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(text) })
      .mockResolvedValueOnce({ done: true, value: undefined }),
  }
}

describe('AIChatPage tool events', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sendChatEventStream.mockReset()
  })

  it('renders tool call and result cards from stream events', async () => {
    sendChatEventStream.mockResolvedValue(
      streamReaderFromText(
        '{"id":"1","type":"tool.call","tool":{"id":"tool-1","name":"asset_search","display_name":"资产查询","icon":"search","arguments":{"query":"房产"}}}\n' +
          '{"id":"2","type":"tool.result","tool_id":"tool-1","result":{"success":true,"summary":"找到 2 条","execution_time_ms":24}}\n' +
          '{"id":"3","type":"token.stream","token":"完成","is_thinking":false}\n',
      ),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: {
            name: 'AIChatInput',
            props: ['modelValue'],
            emits: ['update:modelValue', 'submit'],
            template: '<button class="chat-input" @click="$emit(\'update:modelValue\', \'查一下房产\'); $emit(\'submit\')">send</button>',
          },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    await wrapper.find('.chat-input').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))

    // AiProcessBlock auto-collapses on done; expand it to see tool details
    const header = wrapper.find('.process-header')
    if (header.exists()) {
      await header.trigger('click')
    }

    expect(wrapper.text()).toContain('资产查询')
    expect(wrapper.text()).toContain('房产')
    expect(wrapper.text()).toContain('找到 2 条')
    expect(wrapper.text()).toContain('完成')
  })

  it('renders connection, thinking, and final answer phases from stream events', async () => {
    sendChatEventStream.mockResolvedValue(
      streamReaderFromText(
        '{"id":"1","type":"phase.connecting","phase":"connecting"}\n' +
          '{"id":"2","type":"phase.thinking","phase":"thinking"}\n' +
          '{"id":"3","type":"token.stream","token":"推理中","is_thinking":true}\n' +
          '{"id":"4","type":"phase.answering","phase":"answering"}\n' +
          '{"id":"5","type":"token.stream","token":"最终答案","is_thinking":false}\n' +
          '{"id":"6","type":"capability.end","result":{"summary":"最终答案"}}\n',
      ),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: true } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: {
            name: 'AIChatInput',
            props: ['modelValue', 'deepThink'],
            emits: ['update:modelValue', 'submit', 'update:deepThink'],
            template:
              '<button class="chat-input" @click="$emit(\'update:deepThink\', true); $emit(\'update:modelValue\', \'净资产\'); $emit(\'submit\')">send</button>',
          },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.find('.chat-input').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.find('.phase-strip').exists()).toBe(false)
    // AiProcessBlock auto-collapses when reasoning finishes (status=done → is-collapsed class)
    expect(wrapper.find('.ai-process-block.is-collapsed').exists()).toBe(true)
    expect(wrapper.text()).toContain('最终答案')
  })
})
