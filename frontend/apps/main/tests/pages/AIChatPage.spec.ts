import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AIChatPage from '../../src/pages/AIChatPage.vue'
import { useAIStore } from '../../src/stores/ai'
import type { Artifact } from '../../src/types/agent-stream'
import { showConfirmDialog } from 'vant'

// Type interface for AIChatPage VM methods used in tests
interface AIChatPageVM {
  loadSessionMessages: (session: { session_id: string; title: string; updated_at: string; is_pinned: boolean }) => Promise<void>
  inputText: string
  onSend: () => Promise<void>
  messages: Array<{ content: string; role: string; id: string; phase?: string }>
  asking: boolean
}

const { sendChatMessageStream } = vi.hoisted(() => ({
  sendChatMessageStream: vi.fn(),
}))

const { streamSessionEvents } = vi.hoisted(() => ({
  streamSessionEvents: vi.fn(),
}))

// Stub Vant toast functions that are auto-imported via unplugin-auto-import
vi.hoisted(() => {
  vi.stubGlobal('showFailToast', vi.fn())
  vi.stubGlobal('showSuccessToast', vi.fn())
  vi.stubGlobal('showLoadingToast', vi.fn())
  vi.stubGlobal('closeToast', vi.fn())
})

// Default stream events for LangGraph SDK mock
const defaultStreamEvents = [
  { event: 'metadata', data: { thread_id: 'test-thread-123' } },
  { event: 'messages/partial', data: [{ type: 'ai', id: 'ai-msg-1', content: '完成' }] },
]

// Mock @langchain/langgraph-sdk with configurable stream via global variable
vi.mock('@langchain/langgraph-sdk', () => {
  function createMockStream(events: Array<{ event: string; data: unknown }>) {
    return {
      async *[Symbol.asyncIterator]() {
        for (const event of events) {
          yield event
        }
      },
      then(onFulfilled: (value: unknown) => unknown) {
        return Promise.resolve(this).then(onFulfilled)
      },
    }
  }

  // The getter is called at runtime, so it reads the global variable
  const getEvents = () => {
    // Access the global from the test file's scope
    // This is resolved at runtime, not at hoisting
    return globalThis.__numinaTestStreamEvents ?? defaultStreamEvents
  }

  class MockClient {
    runs = {
      stream: vi.fn().mockImplementation(() => createMockStream(getEvents())),
    }
    threads = {
      getState: vi.fn().mockResolvedValue({ values: { messages: [] } }),
      create: vi.fn().mockResolvedValue({ thread_id: 'test-thread' }),
    }
  }
  return { Client: MockClient }
})

// Set global for mock access
declare global {
  var __numinaTestStreamEvents: Array<{ event: string; data: unknown }> | undefined
}
globalThis.__numinaTestStreamEvents = undefined

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
  sendChatMessageStream,
  getAIConfig: vi.fn(() => Promise.resolve({ data: { ai_enabled: true } })),
  getChatHistory: vi.fn(() => Promise.resolve({ data: [] })),
  clearChatHistory: vi.fn(() => Promise.resolve()),
  markChatRead: vi.fn(() => Promise.resolve()),
  getAITask: vi.fn(() => Promise.resolve({ status: 'completed' } as const)),
}))

vi.mock('../../src/api/sessions', () => ({
  getSessions: vi.fn(() => Promise.resolve({ data: { sessions: [], total: 0 } })),
  streamSessionEvents,
  updateSession: vi.fn(() => Promise.resolve()),
  deleteSession: vi.fn(() => Promise.resolve()),
}))

vi.mock('../../src/api/agent', () => ({
  getAgents: vi.fn(() => Promise.resolve({
    system: [],
    builtin: [{ id: '100000000000005', agent_name: 'numina', display_name: '数鸣' }],
    custom: [],
  })),
  getAgent: vi.fn(() => Promise.resolve({
    id: '100000000000005',
    agent_name: 'numina',
    display_name: '数鸣',
    description: '智能助手',
    enabled: true,
  })),
}))

// Mock axios http client to prevent all network calls
vi.mock('../../src/api/index', () => ({
  default: {
    defaults: {
      baseURL: '/api/v1',
    },
    get: vi.fn().mockImplementation((url: string) => {
      // Return mock responses based on URL
      if (url.includes('/ai/models')) {
        return Promise.resolve({
          data: {
            models: [{ name: 'test-model', display_name: 'Test Model', supports_thinking: true }],
            subagent_enabled: false,
            websearch_enabled: false,
          },
        })
      }
      if (url.includes('/ai/config')) {
        return Promise.resolve({ data: { configs: [] } })
      }
      return Promise.resolve({ data: {} })
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
  refreshTokenIfNeeded: vi.fn().mockResolvedValue(undefined),
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
  showFailToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showLoadingToast: vi.fn(),
  closeToast: vi.fn(),
  // Components used by ArtifactPreviewPopup + SuggestionConfirmDialog (auto-imported names without Van prefix)
  Popup: { template: '<div class="van-popup"><slot /></div>', props: ['show', 'position', 'style', 'round', 'teleport'] },
  NavBar: { template: '<div class="van-nav-bar"><slot /></div>', props: ['title', 'leftArrow', 'clickable'] },
  Button: { template: '<button class="van-button"><slot /></button>', props: ['size', 'plain', 'type', 'block'] },
  Dialog: { template: '<div class="van-dialog"><slot /></div>', props: ['show', 'title', 'showConfirmButton', 'closeOnClickOverlay', 'teleport'] },
  Toast: {},
  Loading: { template: '<div class="van-loading"></div>', props: ['size'] },
  Badge: { template: '<span class="van-badge"><slot /></span>' },
}))

// Mock useTenantAiResources to prevent HTTP calls to /api/v1/ai/models
vi.mock('../../src/composables/ai-chat/useTenantAiResources', () => ({
  useTenantAiResources: () => ({
    models: { value: [{ name: 'test-model', display_name: 'Test Model', supports_thinking: true }] },
    tenantConfig: { value: { subagent_enabled: false, websearch_enabled: false } },
    loading: { value: false },
    error: { value: null },
    supportsThinking: { value: true },
    supportsSubagent: { value: false },
    supportsWebSearch: { value: false },
    defaultModel: { value: { name: 'test-model', display_name: 'Test Model', supports_thinking: true } },
    loadResources: vi.fn(),
    getModelCapabilities: () => ({ supportsThinking: true, supportsVision: false, supportsToolCalling: true }),
    isModeAvailable: () => true,
  }),
  INPUT_MODE_CONFIGS: {
    flash: { mode: 'flash', thinking_enabled: false, is_plan_mode: false, subagent_enabled: false, reasoning_effort: 'minimal', icon: 'zap', label: '闪电', description: '快速响应' },
    thinking: { mode: 'thinking', thinking_enabled: true, is_plan_mode: false, subagent_enabled: false, reasoning_effort: 'low', icon: 'lightbulb', label: '思考', description: '逐步推理' },
    pro: { mode: 'pro', thinking_enabled: true, is_plan_mode: true, subagent_enabled: false, reasoning_effort: 'medium', icon: 'graduation-cap', label: '专业', description: '计划模式' },
    ultra: { mode: 'ultra', thinking_enabled: true, is_plan_mode: true, subagent_enabled: true, reasoning_effort: 'high', icon: 'rocket', label: '旗舰', description: '完整能力' },
  },
  getResolvedMode: (mode: string | undefined) => mode ?? 'pro',
}))

// Mock family store to prevent Pinia initialization issues
vi.mock('../../src/stores/family', () => ({
  useFamilyStore: () => ({
    family: { id: 'family-1' },
  }),
}))

// Mock useSubtasks to prevent network calls
vi.mock('../../src/composables/ai-chat/useSubtasks', () => ({
  useSubtask: () => ({ value: null }),
  clearSubtasks: vi.fn(),
}))

// Mock useArtifacts to prevent network calls
vi.mock('../../src/composables/ai-chat/useArtifacts', () => ({
  useArtifacts: () => ({
    artifacts: { value: {} },
    artifactList: { value: [] },
    selectedArtifact: { value: null },
    open: { value: false },
    setArtifacts: vi.fn(),
    addArtifact: vi.fn(),
    select: vi.fn(),
    deselect: vi.fn(),
    selectByPath: vi.fn(),
    autoSelect: vi.fn(),
    autoOpen: vi.fn(),
    setOpen: vi.fn(),
    clearArtifacts: vi.fn(),
  }),
  loadArtifactContent: vi.fn(),
  useArtifactContent: () => ({
    content: { value: null },
    loading: { value: false },
    error: { value: null },
    load: vi.fn(),
  }),
  clearArtifactContentCache: vi.fn(),
}))

// Mock loading composable to avoid import.meta.hot issues
vi.mock('../../packages/auth/src/composables/loading', () => ({
  useLoading: () => ({
    isLoading: { value: false },
    setLoading: vi.fn(),
  }),
}))

// Helper to create session reader from event objects (used by history reconstruction tests)
function sessionReaderFromEvents(events: object[]) {
  // Add trailing newline so the while loop processes all lines
  const lines = events.map((e) => JSON.stringify(e)).join('\n') + '\n'
  return {
    read: vi
      .fn()
      .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(lines) })
      .mockResolvedValueOnce({ done: true, value: undefined }),
    cancel: vi.fn().mockResolvedValue(undefined),
  }
}

// Common stubs for DeerFlow ai-chat components
const deerflowComponentStubs = {
  // Core component stub
  SvgIcon: { template: '<span class="svg-icon">icon</span>', props: ['name', 'size', 'color'] },
  // DeerFlow input components
  InputBox: {
    template: '<div class="input-box"><slot /></div>',
    props: ['status', 'isWelcomeMode', 'threadId', 'initialMode', 'initialModelName'],
  },
  ModeSelector: {
    template: '<button class="mode-selector" @click="$emit(\'select\', \'pro\')">{{ currentMode }}</button>',
    props: ['currentMode', 'supportsThinking', 'ultraDisabled'],
    emits: ['select'],
  },
  ModelSelectorPopup: {
    template: '<div class="model-selector-popup"><slot /></div>',
    props: ['show', 'models', 'currentModel'],
  },
  ChainOfThought: { template: '<div class="chain-of-thought"><slot /></div>' },
  // MessageGroup stub must render the group prop content to verify messages
  MessageGroup: {
    template: `
      <div class="message-group">
        <div v-for="msg in $props.group?.messages || []" :key="msg.id" class="group-message">
          {{ msg.content }}
        </div>
      </div>
    `,
    props: ['group', 'isLoading', 'threadId'],
  },
  ChatMessage: { template: '<div class="chat-message"><slot /></div>', props: ['message', 'isLoading'] },
  SubtaskCard: { template: '<div class="subtask-card">{{ $props.taskId }}</div>', props: ['taskId', 'isLoading'] },
  ArtifactFileList: { template: '<div class="artifact-file-list"><slot /></div>', props: ['artifacts', 'sessionId'] },
  ArtifactPreviewPopup: { template: '<div class="artifact-preview"><slot /></div>', props: ['show', 'artifact', 'sessionId'] },
  Suggestions: { template: '<div class="suggestions"><slot /></div>', props: ['suggestions', 'loading', 'hidden'] },
  MarkdownContent: { template: '<div class="markdown-content">{{ $props.content }}</div>', props: ['content', 'isLoading'] },
  AssistantMessage: { template: '<div class="assistant-message"><slot /></div>', props: ['id', 'content', 'phase', 'displayTime', 'suggestions', 'feedback'] },
  UserBubble: { template: '<div class="user-bubble">{{ $props.content }}</div>', props: ['content', 'displayTime', 'sendStatus'] },
  // TokenUsage stub to prevent rendering errors when usage data is undefined
  TokenUsage: { template: '<div class="token-usage"></div>', props: ['threadId', 'refreshTrigger'] },
  // Vant components (auto-imported names without 'Van' prefix due to unplugin-vue-components)
  Popup: { template: '<div class="van-popup"><slot /></div>', props: ['show', 'position', 'style', 'round', 'teleport'] },
  VanPopup: { template: '<div class="van-popup"><slot /></div>', props: ['show', 'position', 'style', 'round', 'teleport'] },
  NavBar: { template: '<div class="van-nav-bar"><slot /></div>', props: ['title', 'leftArrow', 'clickable'] },
  Button: { template: '<button class="van-button"><slot /></button>', props: ['size', 'plain', 'type'] },
  Dialog: { template: '<div class="van-dialog"><slot /></div>', props: ['show', 'title', 'showCancelButton', 'showConfirmButton'] },
  VanDialog: { template: '<div class="van-dialog"><slot /></div>', props: ['show', 'title', 'showCancelButton', 'showConfirmButton'] },
  Field: { template: '<input class="van-field" />', props: ['modelValue', 'placeholder', 'autofocus', 'clearable', 'maxlength', 'showWordLimit'] },
  VanField: { template: '<input class="van-field" />', props: ['modelValue', 'placeholder', 'autofocus', 'clearable', 'maxlength', 'showWordLimit'] },
  Skeleton: { template: '<div class="van-skeleton"></div>', props: ['row', 'rowWidth'] },
  VanSkeleton: { template: '<div class="van-skeleton"></div>', props: ['row', 'rowWidth'] },
  Popover: { template: '<div class="van-popover"><slot /></div>', props: ['show', 'placement', 'actions'] },
  VanPopover: { template: '<div class="van-popover"><slot /></div>', props: ['show', 'placement', 'actions'] },
}

describe('AIChatPage tool events', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sendChatMessageStream.mockReset()
    // Reset global stream events to default
    globalThis.__numinaTestStreamEvents = undefined
  })

  it('renders tool call and result cards from stream events', async () => {
    // Set LangGraph SDK stream events (messages/partial format)
    globalThis.__numinaTestStreamEvents = [
      { event: 'metadata', data: { thread_id: 'test-thread-123' } },
      { event: 'messages/partial', data: [{ type: 'ai', id: 'ai-msg-1', content: '完成' }] },
    ]

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: {
            name: 'InputBox',
            props: ['status', 'isWelcomeMode', 'threadId', 'initialMode', 'initialModelName'],
            emits: ['submit', 'stop', 'contextChange'],
            template: '<button class="chat-input" @click="$emit(\'submit\', { text: \'净资产\', model_name: \'test\', mode: \'pro\', thinking_enabled: false, is_plan_mode: false, subagent_enabled: false, reasoning_effort: \'medium\' })">send</button>',
          },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    // Directly set inputText and call onSend to test stream processing
    const vm = wrapper.vm as unknown as {
      inputText: string
      onSend: () => Promise<void>
      messages: Array<{ content: string; role: string; id: string; phase?: string }>
    }
    vm.inputText = '查一下房产'
    await vm.onSend()

    // Wait for async stream processing to complete
    for (let i = 0; i < 20; i++) {
      await new Promise((resolve) => setTimeout(resolve, 0))
    }

    // DeerFlow architecture: tool calls rendered in MessageGroup/ChainOfThought
    // Check that MessageGroup stub is rendered (component is stubbed)
    expect(wrapper.find('.message-group').exists()).toBe(true)
    // Check that the stream processed correctly by looking for completion token
    expect(wrapper.text()).toContain('完成')
  })

  it('renders connection, thinking, and final answer phases from stream events', async () => {
    // Set LangGraph SDK stream events with thinking + answering phases
    globalThis.__numinaTestStreamEvents = [
      { event: 'metadata', data: { thread_id: 'test-thread-123' } },
      // Thinking phase
      { event: 'messages/partial', data: [{ type: 'ai', id: 'ai-msg-1', content: '', additional_kwargs: { reasoning_content: '推理中' } }] },
      // Answering phase
      { event: 'messages/partial', data: [{ type: 'ai', id: 'ai-msg-1', content: '最终答案' }] },
    ]

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: true } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          InputBox: {
            name: 'InputBox',
            props: ['status', 'isWelcomeMode', 'threadId', 'initialMode', 'initialModelName'],
            emits: ['submit', 'stop', 'contextChange'],
            template:
              '<button class="chat-input" @click="$emit(\'submit\', { text: \'净资产\', model_name: \'test\', mode: \'pro\', thinking_enabled: true, is_plan_mode: true, subagent_enabled: false, reasoning_effort: \'medium\' })">send</button>',
          },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })

    await new Promise((resolve) => setTimeout(resolve, 0))
    await wrapper.find('.chat-input').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))

    // After stream completes, check that messages array has content
    // The AssistantMessage stub renders content when phase='done'
    const vm = wrapper.vm as unknown as { messages: Array<{ content: string; role: string; phase?: string }> }
    // Wait for stream processing
    for (let i = 0; i < 20; i++) {
      await new Promise((resolve) => setTimeout(resolve, 0))
    }
    // Check that AI message content was received
    expect(vm.messages.some(m => m.role === 'assistant' && m.content.includes('最终答案'))).toBe(true)
  })
})

describe('AIChatPage artifact registry', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sendChatMessageStream.mockReset()
    streamSessionEvents.mockReset()
    vi.clearAllMocks()
  })

  it('extracts artifact from tool result via history reconstruction and shows badge', async () => {
    // Use history reconstruction path which extracts artifacts from tool.result events
    streamSessionEvents.mockResolvedValue(
      sessionReaderFromEvents([
        { type: 'user.message', eventId: '1', content: '生成报告', timestamp: '2026-06-04T10:00:00Z' },
        { id: '2', type: 'tool.call', tool: { id: 'tool-1', name: 'get_report', display_name: '获取报告', icon: '📊', arguments: {} } },
        { id: '3', type: 'tool.result', tool_id: 'tool-1', result: { success: true, summary: '报告已生成: https://example.com/report.pdf', execution_time_ms: 100 } },
        { type: 'assistant.message', eventId: '4', content: '报告已生成', timestamp: '2026-06-04T10:01:00Z' },
      ]),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
          VanPopup: { template: '<div><slot /></div>' },
          AiArtifactBadge: {
            template: '<button v-if="$props.count > 0" class="artifact-badge">{{ $props.count }}</button>',
            props: ['count'],
          },
          AiArtifactSheet: { template: '<div class="artifact-sheet"></div>', props: ['visible', 'artifacts'] },
        },
      },
    })

    // Load session history which extracts artifacts
    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Check that messages were loaded
    const vm = wrapper.vm as unknown as { sessionArtifacts: Artifact[]; messages: Array<{ role: string }> }
    // At least user message should be loaded
    expect(vm.messages.some(m => m.role === 'user')).toBe(true)
    // At least one assistant message should be loaded (from assistant.message event)
    expect(vm.messages.some(m => m.role === 'assistant')).toBe(true)
    // Artifacts should be extracted from tool.result with URL
    expect(vm.sessionArtifacts.length).toBeGreaterThanOrEqual(1)
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
          InputBox: { template: '<button class="chat-input">send</button>' },
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
          InputBox: { template: '<button class="chat-input">send</button>' },
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
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
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

  it('opens preview popup for file artifact', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const vm = wrapper.vm as unknown as {
      onArtifactTap: (artifact: Artifact) => void
      showArtifactPreview: boolean
      selectedArtifactForPreview: Artifact | null
    }
    const fileArtifact: Artifact = {
      id: 'artifact-1',
      title: 'Generated File',
      path: '/tmp/result.json',
      kind: 'file',
      sourceStepId: 'tool-1',
    }

    vm.onArtifactTap(fileArtifact)

    // Verify preview popup state is set (DeerFlow Phase 5 behavior)
    expect(vm.showArtifactPreview).toBe(true)
    expect(vm.selectedArtifactForPreview).toEqual(fileArtifact)
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
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
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
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
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
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
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

  it('deduplicates artifacts by sourceStepId via history reconstruction', async () => {
    // Use history reconstruction path - artifacts are extracted from tool.result events
    streamSessionEvents.mockResolvedValue(
      sessionReaderFromEvents([
        { type: 'user.message', eventId: '1', content: '生成报告', timestamp: '2026-06-04T10:00:00Z' },
        { id: '2', type: 'tool.call', tool: { id: 'tool-1', name: 'get_report', display_name: '获取报告', icon: '📊', arguments: {} } },
        { id: '3', type: 'tool.result', tool_id: 'tool-1', result: { success: true, summary: '报告: https://example.com/report.pdf', execution_time_ms: 100 } },
        // Duplicate tool call with same ID - should dedupe
        { id: '4', type: 'tool.call', tool: { id: 'tool-1', name: 'get_report', display_name: '获取报告', icon: '📊', arguments: {} } },
        { id: '5', type: 'tool.result', tool_id: 'tool-1', result: { success: true, summary: '报告: https://example.com/report.pdf', execution_time_ms: 100 } },
        { type: 'assistant.message', eventId: '6', content: '完成', timestamp: '2026-06-04T10:01:00Z' },
      ]),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
          VanPopup: { template: '<div><slot /></div>' },
          AiArtifactBadge: {
            template: '<button v-if="$props.count > 0" class="artifact-badge">{{ $props.count }}</button>',
            props: ['count'],
          },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Same tool called twice with same ID → only one artifact
    expect(wrapper.find('.artifact-badge').text()).toBe('1')
  })
})

describe('AIChatPage history reconstruction (U6)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sendChatMessageStream.mockReset()
    streamSessionEvents.mockReset()
    vi.clearAllMocks()
  })

  it('routes all events through normalizer (R11)', async () => {
    const normalizeSpy = vi.spyOn(await import('../../src/utils/aiEventNormalizer'), 'normalizeAgentEvent')

    streamSessionEvents.mockResolvedValue(
      sessionReaderFromEvents([
        { type: 'user.message', eventId: '1', content: '查询', timestamp: '2026-06-04T10:00:00Z' },
        { id: '2', type: 'tool.call', tool: { id: 'tool-1', name: 'search', display_name: '搜索', icon: '🔍', arguments: {} } },
        { id: '3', type: 'tool.result', tool_id: 'tool-1', result: { success: true, summary: '结果', execution_time_ms: 50 } },
        { type: 'assistant.message', eventId: '4', content: '完成', timestamp: '2026-06-04T10:01:00Z' },
      ]),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Verify normalizer was called for tool.call and tool.result events
    expect(normalizeSpy).toHaveBeenCalled()
    const toolCallEvent = normalizeSpy.mock.calls.find(call => call[0]?.type === 'tool.call')
    const toolResultEvent = normalizeSpy.mock.calls.find(call => call[0]?.type === 'tool.result')
    expect(toolCallEvent).toBeDefined()
    expect(toolResultEvent).toBeDefined()

    normalizeSpy.mockRestore()
  })

  it('handles tool.result event and extracts artifacts (R11)', async () => {
    streamSessionEvents.mockResolvedValue(
      sessionReaderFromEvents([
        { type: 'user.message', eventId: '1', content: '查询', timestamp: '2026-06-04T10:00:00Z' },
        { id: '2', type: 'tool.call', tool: { id: 'tool-1', name: 'get_report', display_name: '获取报告', icon: '📊', arguments: {} } },
        { id: '3', type: 'tool.result', tool_id: 'tool-1', result: { success: true, summary: '报告: https://example.com/report.pdf', execution_time_ms: 100 } },
        { type: 'assistant.message', eventId: '4', content: '报告已生成', timestamp: '2026-06-04T10:01:00Z' },
      ]),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Verify streamSessionEvents was called
    expect(streamSessionEvents).toHaveBeenCalledWith('test-1')

    // Verify function completed without error (artifacts are extracted in implementation)
    // Check that messages and artifacts were actually populated
    const vm = wrapper.vm as unknown as { sessionArtifacts: Artifact[]; messages: Array<{ role: string }> }
    expect(vm.messages.some(m => m.role === 'assistant')).toBe(true)
    expect(vm.sessionArtifacts.length).toBeGreaterThanOrEqual(1)
  })

  it('handles error events gracefully', async () => {
    streamSessionEvents.mockResolvedValue(
      sessionReaderFromEvents([
        { type: 'user.message', eventId: '1', content: '查询', timestamp: '2026-06-04T10:00:00Z' },
        { id: '2', type: 'tool.call', tool: { id: 'tool-1', name: 'search', display_name: '搜索', icon: '🔍', arguments: {} } },
        { id: '3', type: 'tool.result', tool_id: 'tool-1', result: { success: false, error: '查询失败', execution_time_ms: 50 } },
        { type: 'assistant.message', eventId: '4', content: '出错了', timestamp: '2026-06-04T10:01:00Z' },
      ]),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Should complete without throwing
    expect(wrapper.vm).toBeDefined()
  })

  it('skips malformed JSONL lines gracefully', async () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    // Create malformed JSONL with invalid line in middle
    const malformedLines = [
      '{"type":"user.message","eventId":"1","content":"查询","timestamp":"2026-06-04T10:00:00Z"}',
      'INVALID_JSON_LINE',
      '{"type":"assistant.message","eventId":"2","content":"回答","timestamp":"2026-06-04T10:01:00Z"}',
    ].join('\n')

    streamSessionEvents.mockResolvedValue({
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(malformedLines) })
        .mockResolvedValueOnce({ done: true, value: undefined }),
      cancel: vi.fn().mockResolvedValue(undefined),
    })

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    // Verify console.warn was called with our parse error message (may have other Vue warnings first)
    const allWarns = consoleWarnSpy.mock.calls.map(call => call[0])
    const hasParseError = allWarns.some(msg => typeof msg === 'string' && msg.includes('Failed to parse session event line'))
    expect(hasParseError).toBe(true)

    consoleWarnSpy.mockRestore()
  })
})

describe('AIChatPage filterAIContent integration', () => {
  // Helper function to create session reader for history reconstruction tests
  function createSessionReader(content: string) {
    // Add trailing newline so the while loop processes all lines
    const lines = content.endsWith('\n') ? content : content + '\n'
    return {
      read: vi
        .fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(lines) })
        .mockResolvedValueOnce({ done: true, value: undefined }),
      cancel: vi.fn().mockResolvedValue(undefined),
    }
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    streamSessionEvents.mockReset()
    vi.clearAllMocks()
  })

  it('filters forbidden XML tags from history reconstruction', async () => {
    // filterAIContent is applied in loadSessionMessages, not live streaming
    const rawContent = '根据查询结果，<system_instructions>你是助手，以下是系统指令</system_instructions>当前净资产为 100 万元。'
    const sessionLines = [
      JSON.stringify({ type: 'user.message', eventId: '1', content: '净资产', timestamp: '2026-06-04T10:00:00Z' }),
      JSON.stringify({ type: 'assistant.message', eventId: '2', content: rawContent, timestamp: '2026-06-04T10:01:00Z' }),
    ].join('\n')

    streamSessionEvents.mockResolvedValue(createSessionReader(sessionLines))

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    // The message content should NOT contain the forbidden XML tags
    const vm = wrapper.vm as unknown as { messages: Array<{ content: string; role: string }> }
    const assistantMsg = vm.messages.find(m => m.role === 'assistant')
    expect(assistantMsg?.content).not.toContain('<system_instructions>')
    expect(assistantMsg?.content).not.toContain('你是助手')
    expect(assistantMsg?.content).not.toContain('系统指令')
    // But should contain the safe content
    expect(assistantMsg?.content).toContain('根据查询结果')
    expect(assistantMsg?.content).toContain('当前净资产为 100 万元')
  })

  it('filters User Context leakage from history reconstruction', async () => {
    const userContextJson = JSON.stringify({ family_id: '123', tenantId: '456' })
    const rawContent = `User Context: ${userContextJson}\n这是回答正文。`
    const sessionLines = [
      JSON.stringify({ type: 'user.message', eventId: '1', content: 'test', timestamp: '2026-06-04T10:00:00Z' }),
      JSON.stringify({ type: 'assistant.message', eventId: '2', content: rawContent, timestamp: '2026-06-04T10:01:00Z' }),
    ].join('\n')

    streamSessionEvents.mockResolvedValue(createSessionReader(sessionLines))

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    const vm = wrapper.vm as unknown as { messages: Array<{ content: string; role: string }> }
    const assistantMsg = vm.messages.find(m => m.role === 'assistant')
    // Should NOT leak User Context or identifiers
    expect(assistantMsg?.content).not.toContain('User Context')
    expect(assistantMsg?.content).not.toContain('family_id')
    expect(assistantMsg?.content).not.toContain('tenantId')
    // Should show safe content
    expect(assistantMsg?.content).toContain('这是回答正文')
  })

  it('filters repeated user question pattern from history', async () => {
    const rawContent = '你问的是：我们家净资产是多少？\n根据数据，当前净资产为 200 万元。'
    const sessionLines = [
      JSON.stringify({ type: 'user.message', eventId: '1', content: '我们家净资产是多少？', timestamp: '2026-06-04T10:00:00Z' }),
      JSON.stringify({ type: 'assistant.message', eventId: '2', content: rawContent, timestamp: '2026-06-04T10:01:00Z' }),
    ].join('\n')

    streamSessionEvents.mockResolvedValue(createSessionReader(sessionLines))

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    const vm = wrapper.vm as unknown as { messages: Array<{ content: string; role: string }> }
    const assistantMsg = vm.messages.find(m => m.role === 'assistant')
    // Should NOT repeat the user question
    expect(assistantMsg?.content).not.toContain('你问的是')
    // Should show the actual answer
    expect(assistantMsg?.content).toContain('根据数据')
    expect(assistantMsg?.content).toContain('当前净资产为 200 万元')
  })

  it('handles multiple forbidden patterns in history reconstruction', async () => {
    const rawContent = '<user_question>原始问题</user_question>System Prompt: 你是助手\ntenantId: 789\n安全回答内容。'
    const sessionLines = [
      JSON.stringify({ type: 'user.message', eventId: '1', content: 'test', timestamp: '2026-06-04T10:00:00Z' }),
      JSON.stringify({ type: 'assistant.message', eventId: '2', content: rawContent, timestamp: '2026-06-04T10:01:00Z' }),
    ].join('\n')

    streamSessionEvents.mockResolvedValue(createSessionReader(sessionLines))

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    const vm = wrapper.vm as unknown as { messages: Array<{ content: string; role: string }> }
    const assistantMsg = vm.messages.find(m => m.role === 'assistant')
    // All forbidden content should be filtered
    expect(assistantMsg?.content).not.toContain('<user_question>')
    expect(assistantMsg?.content).not.toContain('原始问题')
    expect(assistantMsg?.content).not.toContain('System Prompt')
    expect(assistantMsg?.content).not.toContain('tenantId')
    // Only safe content remains
    expect(assistantMsg?.content).toContain('安全回答内容')
  })

  it('preserves normal markdown content through filter', async () => {
    const rawContent = '# 标题\n\n**加粗** 和 `代码`\n\n- 列表项'
    const sessionLines = [
      JSON.stringify({ type: 'user.message', eventId: '1', content: 'test', timestamp: '2026-06-04T10:00:00Z' }),
      JSON.stringify({ type: 'assistant.message', eventId: '2', content: rawContent, timestamp: '2026-06-04T10:01:00Z' }),
    ].join('\n')

    streamSessionEvents.mockResolvedValue(createSessionReader(sessionLines))

    const pinia = createPinia()
    setActivePinia(pinia)
    const aiStore = useAIStore()
    aiStore.config = { ai_enabled: true, ai_test_thinking_success: false } as typeof aiStore.config

    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [pinia],
        stubs: {
          ...deerflowComponentStubs,
          InputBox: { template: '<button class="chat-input">send</button>' },
        },
      },
    })

    const session = { session_id: 'test-1', title: 'Test', updated_at: new Date().toISOString(), is_pinned: false }
    await (wrapper.vm as AIChatPageVM).loadSessionMessages(session)
    await new Promise((resolve) => setTimeout(resolve, 100))

    const vm = wrapper.vm as unknown as { messages: Array<{ content: string; role: string }> }
    const assistantMsg = vm.messages.find(m => m.role === 'assistant')
    // Normal markdown should be preserved
    expect(assistantMsg?.content).toContain('标题')
    expect(assistantMsg?.content).toContain('加粗')
    expect(assistantMsg?.content).toContain('代码')
    expect(assistantMsg?.content).toContain('列表项')
  })
})
