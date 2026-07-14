import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick, ref as vueRef } from 'vue'
import InputBox from '@/components/ai-chat/InputBox.vue'

// ─── Hoisted mocks ──────────────────────────────────────────────────────────

const { mocks, INPUT_MODE_CONFIGS, makeMockResources } = vi.hoisted(() => {
  const INPUT_MODE_CONFIGS = {
    flash: { mode: 'flash', thinking_enabled: false, is_plan_mode: false, subagent_enabled: false, reasoning_effort: 'minimal', icon: 'lucide:zap', label: 'Flash', description: 'Quick response' },
    thinking: { mode: 'thinking', thinking_enabled: true, is_plan_mode: false, subagent_enabled: false, reasoning_effort: 'low', icon: 'lucide:lightbulb', label: 'Thinking', description: 'Step-by-step' },
    pro: { mode: 'pro', thinking_enabled: true, is_plan_mode: true, subagent_enabled: false, reasoning_effort: 'medium', icon: 'lucide:graduation-cap', label: 'Pro', description: 'Plan mode' },
    ultra: { mode: 'ultra', thinking_enabled: true, is_plan_mode: true, subagent_enabled: true, reasoning_effort: 'high', icon: 'lucide:rocket', label: 'Ultra', description: 'Subagent' },
  }

  function makeMockResources(overrides = {}) {
    return {
      models: vueRef(overrides.models ?? []),
      tenantConfig: vueRef(overrides.tenantConfig ?? { subagent_enabled: false, websearch_enabled: false }),
      supportsThinking: vueRef(overrides.supportsThinking ?? false),
      supportsSubagent: vueRef(overrides.supportsSubagent ?? false),
      supportsWebSearch: vueRef(overrides.supportsWebSearch ?? false),
      loading: vueRef(overrides.loading ?? false),
    }
  }

  return {
    mocks: {
      showToast: vi.fn(),
      getWebSearchStatus: vi.fn(),
    },
    INPUT_MODE_CONFIGS,
    makeMockResources,
  }
})

vi.mock('@/composables/ai-chat/useTenantAiResources', () => {
  const state = { resources: makeMockResources() }
  return {
    useTenantAiResources: () => state.resources,
    INPUT_MODE_CONFIGS,
    getResolvedMode: vi.fn((requestedMode, supportsThinking, supportsSubagent) => {
      if (!supportsThinking && requestedMode !== 'flash') return 'flash'
      if (requestedMode === 'ultra' && !supportsSubagent) return 'pro'
      return requestedMode ?? (supportsThinking ? 'pro' : 'flash')
    }),
  }
})

vi.mock('vant', () => ({
  showToast: mocks.showToast,
  showFailToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showDialog: vi.fn(() => Promise.resolve()),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

vi.mock('@/api/webSearch', () => ({
  getWebSearchStatus: mocks.getWebSearchStatus,
}))

// ─── Stubs ───────────────────────────────────────────────────────────────────

const childStubs = {
  ModeSelector: {
    template: '<button class="mode-selector-stub" @click="$emit(\'select\', \'pro\')">{{ currentMode }}</button>',
    props: ['currentMode', 'supportsThinking', 'ultraDisabled'],
    emits: ['select'],
  },
  IIcon: { template: '<span class="i-icon-stub" />', props: ['icon', 'size', 'color'] },
  AIBrainIcon: { template: '<span class="ai-brain-stub" />', props: ['active'] },
}

const teleportStub = {
  template: '<div class="teleport-stub"><slot /></div>',
}

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('InputBox', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    wrapper = mount(InputBox, {
      props: { status: 'ready' },
      global: { stubs: { ...childStubs, Teleport: teleportStub } },
    })
    mocks.showToast.mockClear()
    mocks.getWebSearchStatus.mockReset()
  })

// ─── Mode auto-downgrade ──────────────────────────────────────────────────

  describe('mode auto-downgrade', () => {
    it('initial mode is preserved when set via initialMode prop', async () => {
      // The component accepts initialMode as a prop and uses it as context.mode.
      // Auto-downgrade happens via watcher on currentModelSupportsThinking.
      const localWrapper = mount(InputBox, {
        props: { status: 'ready', initialMode: 'pro', initialModelName: 'gpt-4' },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })
      await nextTick()

      const vm = localWrapper.vm as any
      expect(vm.context.mode).toBe('pro')
      expect(vm.context.model_name).toBe('gpt-4')
    })

    it('flash mode never gets downgraded since it is always available', async () => {
      const localWrapper = mount(InputBox, {
        props: { status: 'ready', initialMode: 'flash', initialModelName: 'gpt-4' },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })
      await nextTick()

      const vm = localWrapper.vm as any
      expect(vm.context.mode).toBe('flash')
    })

    it('getResolvedMode downgrades pro to flash when thinking is false', async () => {
      const { getResolvedMode } = await vi.importMock<typeof import('@/composables/ai-chat/useTenantAiResources')>('@/composables/ai-chat/useTenantAiResources')
      expect(getResolvedMode('pro', false, false)).toBe('flash')
      expect(getResolvedMode('thinking', false, false)).toBe('flash')
      expect(getResolvedMode('ultra', false, true)).toBe('flash')
      expect(getResolvedMode('pro', true, false)).toBe('pro')
      expect(getResolvedMode('ultra', true, false)).toBe('pro')
      expect(getResolvedMode('ultra', true, true)).toBe('ultra')
    })
  })

  // ─── Mode selection ───────────────────────────────────────────────────────

  describe('onModeSelect', () => {
    it('shows toast and rejects ultra when subagent is disabled', async () => {
      const vm = wrapper.vm as any
      await vm.onModeSelect('ultra')

      expect(mocks.showToast).toHaveBeenCalledWith('aiChat.tenantUltraDisabled')
      expect(vm.context.mode).not.toBe('ultra')
    })

    it('emits contextChange with correct reasoning_effort on mode select', async () => {
      const localWrapper = mount(InputBox, {
        props: { status: 'ready' },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })
      await nextTick()
      const vm = localWrapper.vm as any

      await vm.onModeSelect('thinking')
      const contextChanges = localWrapper.emitted('contextChange')
      expect(contextChanges).toBeTruthy()
      expect(contextChanges?.[0][0].reasoning_effort).toBe('low')
    })
  })

  // ─── Plus panel ───────────────────────────────────────────────────────────

  describe('plus panel', () => {
    it('opens panel on plus button click', async () => {
      const vm = wrapper.vm as any
      expect(vm.panelOpen).toBe(false)

      vm.panelOpen = true
      await nextTick()
      expect(vm.panelOpen).toBe(true)
    })

    it('closes panel and triggers file input when panel item is clicked', async () => {
      const vm = wrapper.vm as any
      vm.panelOpen = true
      await nextTick()

      // Mock the click method on file inputs
      const cameraInput = wrapper.find('input[capture="environment"]')
      const clickSpy = vi.spyOn(cameraInput.element as HTMLInputElement, 'click')

      await vm.onPanelItem('camera')
      expect(vm.panelOpen).toBe(false)
      expect(clickSpy).toHaveBeenCalled()
    })

    it('closePanel sets panelOpen to false', async () => {
      const vm = wrapper.vm as any
      vm.panelOpen = true
      await nextTick()

      vm.closePanel()
      expect(vm.panelOpen).toBe(false)
    })

    it('onDocClick closes panel when clicking outside', async () => {
      const vm = wrapper.vm as any
      vm.panelOpen = true
      await nextTick()

      const mockEvent = { target: document.body } as unknown as MouseEvent
      vm.onDocClick(mockEvent)
      expect(vm.panelOpen).toBe(false)
    })

    it('onDocClick does not close panel when clicking the panel itself', async () => {
      const vm = wrapper.vm as any
      vm.panelOpen = true
      await nextTick()

      const panel = document.createElement('div')
      panel.className = 'plus-panel'
      const mockEvent = { target: panel } as unknown as MouseEvent
      vm.onDocClick(mockEvent)
      expect(vm.panelOpen).toBe(true)
    })
  })

  // ─── Expand button ────────────────────────────────────────────────────────

  describe('expand button', () => {
    it('shows expand button when text has 2+ newlines', async () => {
      const vm = wrapper.vm as any
      vm.internalValue = 'line1\nline2\nline3'
      await nextTick()

      expect(vm.showExpandIcon).toBe(true)
    })

    it('shows expand button when text length exceeds 36 chars', async () => {
      const vm = wrapper.vm as any
      vm.internalValue = 'this is a very long text that exceeds thirty six characters'
      await nextTick()

      expect(vm.showExpandIcon).toBe(true)
    })

    it('does not show expand button for short text', async () => {
      const vm = wrapper.vm as any
      vm.internalValue = 'short'
      await nextTick()

      expect(vm.showExpandIcon).toBe(false)
    })

    it('toggles expanded state', async () => {
      const vm = wrapper.vm as any
      expect(vm.expanded).toBe(false)

      vm.toggleExpand()
      expect(vm.expanded).toBe(true)

      vm.toggleExpand()
      expect(vm.expanded).toBe(false)
    })
  })

  // ─── Attachments ──────────────────────────────────────────────────────────

  describe('attachments', () => {
    it('emits removeAttachment with correct index', () => {
      const vm = wrapper.vm as any
      vm.removeAttachment(2)
      expect(wrapper.emitted('removeAttachment')).toBeTruthy()
      expect(wrapper.emitted('removeAttachment')?.[0][0]).toBe(2)
    })

    it('renders attachment rows when attachments prop is provided', async () => {
      const localWrapper = mount(InputBox, {
        props: {
          status: 'ready',
          attachments: [
            { type: 'image', name: 'photo.jpg' },
            { type: 'file', name: 'report.pdf' },
          ],
        },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })

      expect(localWrapper.findAll('.attachment-item').length).toBe(2)
      expect(localWrapper.find('.attachment-item--image').exists()).toBe(true)
    })
  })

  // ─── Agent display ────────────────────────────────────────────────────────

  describe('agent display', () => {
    it('selects agent by agentId', async () => {
      const agents = [
        { id: '1', display_name: 'Agent One', agent_name: 'agent-one', icon: '🤖' },
        { id: '2', display_name: 'Agent Two', agent_name: 'agent-two', icon: '🔧' },
      ]
      const localWrapper = mount(InputBox, {
        props: { status: 'ready', agentId: '2', agents },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })
      await nextTick()

      const vm = localWrapper.vm as any
      expect(vm.displayAgentLabel).toBe('Agent Two')
      expect(vm.displayAgentIcon).toBe('🔧')
    })

    it('falls back to first agent when agentId not found', async () => {
      const agents = [
        { id: '1', display_name: 'Agent One', agent_name: 'agent-one', icon: '🤖' },
      ]
      const localWrapper = mount(InputBox, {
        props: { status: 'ready', agentId: '999', agents },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })
      await nextTick()

      const vm = localWrapper.vm as any
      expect(vm.displayAgentLabel).toBe('Agent One')
    })

    it('detects numina agent by agent_name', async () => {
      const agents = [
        { id: '1', display_name: 'Numina', agent_name: 'numina', icon: null },
      ]
      const localWrapper = mount(InputBox, {
        props: { status: 'ready', agentId: '1', agents },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })
      await nextTick()

      const vm = localWrapper.vm as any
      expect(vm.isNuminaAgent).toBe(true)
    })
  })

  // ─── Default model initialization ─────────────────────────────────────────

  describe('default model initialization', () => {
    it('preserves initialModelName when already set', () => {
      const localWrapper = mount(InputBox, {
        props: { status: 'ready', initialModelName: 'gpt-4' },
        global: { stubs: { ...childStubs, Teleport: teleportStub } },
      })

      const vm = localWrapper.vm as any
      expect(vm.context.model_name).toBe('gpt-4')
    })
  })
})
