import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AIChatPage from '../../src/pages/AIChatPage.vue'
import { useAIStore } from '../../src/stores/ai'
import type { Artifact } from '../../src/types/agent-stream'
import { showConfirmDialog, showToast } from 'vant'

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
            props: ['modelValue', 'mode'],
            emits: ['update:modelValue', 'submit', 'update:mode'],
            template:
              '<button class="chat-input" @click="$emit(\'update:mode\', \'smart\'); $emit(\'update:modelValue\', \'净资产\'); $emit(\'submit\')">send</button>',
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

describe('AIChatPage artifact registry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sendChatEventStream.mockReset()
    vi.clearAllMocks()
  })

  it('extracts artifact from tool result and shows badge', async () => {
    sendChatEventStream.mockResolvedValue(
      streamReaderFromText(
        '{"id":"1","type":"tool.call","tool":{"id":"tool-1","name":"get_report","display_name":"获取报告","icon":"📊","arguments":{}}}\n' +
          '{"id":"2","type":"tool.result","tool_id":"tool-1","result":{"success":true,"summary":"报告已生成: https://example.com/report.pdf","execution_time_ms":100}}\n' +
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
            template: '<button class="chat-input" @click="$emit(\'update:modelValue\', \'生成报告\'); $emit(\'submit\')">send</button>',
          },
          VanPopup: { template: '<div><slot /></div>' },
          AiArtifactBadge: {
            template: '<button v-if="$props.count > 0" class="artifact-badge">{{ $props.count }}</button>',
            props: ['count'],
          },
          AiArtifactSheet: { template: '<div class="artifact-sheet"></div>', props: ['visible', 'artifacts'] },
        },
      },
    })

    await wrapper.find('.chat-input').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 50))

    // Badge should appear with count 1
    expect(wrapper.find('.artifact-badge').exists()).toBe(true)
    expect(wrapper.find('.artifact-badge').text()).toBe('1')
  })

  it('hides badge when sessionArtifacts is empty', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: { template: '<div></div>' },
          VanPopup: { template: '<div><slot /></div>' },
          AiArtifactBadge: {
            template: '<button v-if="$props.count > 0" class="artifact-badge">{{ $props.count }}</button>',
            props: ['count'],
          },
        },
      },
    })

    // No artifacts → badge hidden
    expect(wrapper.find('.artifact-badge').exists()).toBe(false)
  })

  it('opens artifact sheet on badge tap', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: { template: '<div></div>' },
          VanPopup: { template: '<div><slot /></div>' },
          AiArtifactBadge: {
            template: '<button class="artifact-badge" @click="$emit(\'tap\')">1</button>',
            props: ['count'],
          },
          AiArtifactSheet: {
            template: '<div v-if="$props.visible" class="artifact-sheet"></div>',
            props: ['visible', 'artifacts'],
          },
        },
      },
    })

    // Set internal state to have one artifact
    const vm = wrapper.vm as unknown as { sessionArtifacts: Artifact[]; showArtifactSheet: boolean }
    vm.sessionArtifacts = [
      { id: 'artifact-1', title: 'Test Report', url: 'https://example.com/report.pdf', kind: 'report', sourceStepId: 'tool-1' },
    ]

    await wrapper.find('.artifact-badge').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(vm.showArtifactSheet).toBe(true)
    expect(wrapper.find('.artifact-sheet').exists()).toBe(true)
  })

  it('opens URL for link artifact', async () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: { template: '<div></div>' },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as { onArtifactTap: (artifact: Artifact) => void }
    const linkArtifact: Artifact = {
      id: 'artifact-1',
      title: 'External Link',
      url: 'https://example.com',
      kind: 'link',
      sourceStepId: 'tool-1',
    }

    vm.onArtifactTap(linkArtifact)

    expect(windowOpenSpy).toHaveBeenCalledWith('https://example.com', '_blank', 'noopener,noreferrer')
    windowOpenSpy.mockRestore()
  })

  it('copies path for file artifact and shows toast', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: { template: '<div></div>' },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as { onArtifactTap: (artifact: Artifact) => void }
    const fileArtifact: Artifact = {
      id: 'artifact-1',
      title: 'Generated File',
      path: '/tmp/result.json',
      kind: 'file',
      sourceStepId: 'tool-1',
    }

    vm.onArtifactTap(fileArtifact)

    // Wait for async clipboard operations
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))

    // Verify toast was shown (user-facing behavior)
    expect(showToast).toHaveBeenCalled()
  })

  it('opens URL for report artifact', async () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: { template: '<div></div>' },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as { onArtifactTap: (artifact: Artifact) => void }
    const reportArtifact: Artifact = {
      id: 'artifact-1',
      title: 'AI Report',
      url: 'https://example.com/report',
      kind: 'report',
      sourceStepId: 'tool-1',
    }

    vm.onArtifactTap(reportArtifact)

    expect(windowOpenSpy).toHaveBeenCalledWith('https://example.com/report', '_blank', 'noopener,noreferrer')
    windowOpenSpy.mockRestore()
  })

  it('shows JSON preview for data artifact', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: { template: '<div></div>' },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as { onArtifactTap: (artifact: Artifact) => void }
    const dataArtifact: Artifact = {
      id: 'artifact-1',
      title: 'Query Result',
      kind: 'data',
      sourceStepId: 'tool-1',
    }

    vm.onArtifactTap(dataArtifact)

    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(showConfirmDialog).toHaveBeenCalledWith({
      title: 'aiArtifact.jsonPreviewTitle',
      message: expect.stringContaining('artifact-1'),
      confirmButtonText: 'common.close',
      showCancelButton: false,
    })
  })

  it('clears sessionArtifacts on new chat', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          AIChatInput: { template: '<div></div>' },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    // Set initial state with artifacts
    const vm = wrapper.vm as unknown as {
      sessionArtifacts: Artifact[]
      messages: Array<{ id: string; role: string; content: string }>
      onNewChat: () => Promise<void>
    }
    vm.sessionArtifacts = [
      { id: 'artifact-1', title: 'Test', kind: 'link', sourceStepId: 'tool-1' },
    ]
    vm.messages = [
      { id: 'msg-1', role: 'user', content: 'test' },
      { id: 'msg-2', role: 'assistant', content: 'response' },
    ]

    // Trigger new chat
    await vm.onNewChat()

    expect(vm.sessionArtifacts).toEqual([])
  })

  it('deduplicates artifacts by sourceStepId', async () => {
    sendChatEventStream.mockResolvedValue(
      streamReaderFromText(
        '{"id":"1","type":"tool.call","tool":{"id":"tool-1","name":"get_report","display_name":"获取报告","icon":"📊","arguments":{}}}\n' +
          '{"id":"2","type":"tool.result","tool_id":"tool-1","result":{"success":true,"summary":"报告: https://example.com/report.pdf","execution_time_ms":100}}\n' +
          '{"id":"3","type":"tool.call","tool":{"id":"tool-1","name":"get_report","display_name":"获取报告","icon":"📊","arguments":{}}}\n' +
          '{"id":"4","type":"tool.result","tool_id":"tool-1","result":{"success":true,"summary":"报告: https://example.com/report.pdf","execution_time_ms":100}}\n' +
          '{"id":"5","type":"token.stream","token":"完成","is_thinking":false}\n',
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
            template: '<button class="chat-input" @click="$emit(\'update:modelValue\', \'生成报告\'); $emit(\'submit\')">send</button>',
          },
          VanPopup: { template: '<div><slot /></div>' },
          AiArtifactBadge: {
            template: '<button v-if="$props.count > 0" class="artifact-badge">{{ $props.count }}</button>',
            props: ['count'],
          },
        },
      },
    })

    await wrapper.find('.chat-input').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 50))

    // Same tool called twice with same ID → only one artifact
    expect(wrapper.find('.artifact-badge').text()).toBe('1')
  })
})
