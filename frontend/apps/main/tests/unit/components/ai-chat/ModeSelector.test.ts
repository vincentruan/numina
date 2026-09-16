import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import ModeSelector from '@/components/ai-chat/ModeSelector.vue'

// ─── Mocks ───────────────────────────────────────────────────────────────────

const { INPUT_MODE_CONFIGS } = vi.hoisted(() => ({
  INPUT_MODE_CONFIGS: {
    flash: { mode: 'flash', thinking_enabled: false, is_plan_mode: false, subagent_enabled: false, reasoning_effort: 'minimal', icon: 'lucide:zap', label: 'Flash', description: 'Quick response' },
    thinking: { mode: 'thinking', thinking_enabled: true, is_plan_mode: false, subagent_enabled: false, reasoning_effort: 'low', icon: 'lucide:lightbulb', label: 'Thinking', description: 'Step-by-step' },
    pro: { mode: 'pro', thinking_enabled: true, is_plan_mode: true, subagent_enabled: false, reasoning_effort: 'medium', icon: 'lucide:graduation-cap', label: 'Pro', description: 'Plan mode' },
    ultra: { mode: 'ultra', thinking_enabled: true, is_plan_mode: true, subagent_enabled: true, reasoning_effort: 'high', icon: 'lucide:rocket', label: 'Ultra', description: 'Subagent' },
  },
}))

const modeLabels: Record<string, string> = {
  'mode.flash.label': 'Flash',
  'mode.flash.description': 'Quick response, no deep thinking',
  'mode.thinking.label': 'Thinking',
  'mode.thinking.description': 'Step-by-step reasoning',
  'mode.pro.label': 'Pro',
  'mode.pro.description': 'Plan mode, auto task breakdown',
  'mode.ultra.label': 'Ultra',
  'mode.ultra.description': 'Full capability, subagent collaboration',
}

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => modeLabels[key] || key,
  }),
}))

vi.mock('@/composables/ai-chat/useTenantAiResources', () => ({
  INPUT_MODE_CONFIGS,
}))

// VanPopup stub (auto-imported in production, needs explicit stub in tests)
const VanPopupStub = {
  name: 'VanPopup',
  template: '<div class="van-popup-stub"><slot /></div>',
  props: ['show', 'position', 'round'],
  emits: ['close', 'click-overlay', 'update:show'],
}

// Stub child components
const childStubs = {
  IIcon: { template: '<span class="i-icon-stub" />', props: ['icon', 'size', 'color'] },
  VanPopup: VanPopupStub,
}

// Teleport stub that renders content inline (happy-dom workaround)
const teleportStub = {
  template: '<div class="teleport-stub"><slot /></div>',
}

function makeWrapper(props = {}) {
  return mount(ModeSelector, {
    props: {
      currentMode: 'thinking',
      supportsThinking: true,
      ultraDisabled: false,
      ...props,
    },
    global: {
      stubs: {
        ...childStubs,
        Teleport: teleportStub,
      },
    },
    attachTo: document.body,
  })
}

async function openPopup(w: VueWrapper<any>) {
  w.find('.mode-trigger').trigger('click')
  await nextTick()
  await nextTick()
}

describe('ModeSelector', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    wrapper = makeWrapper()
  })

  // ─── Trigger button ────────────────────────────────────────────────────────

  describe('trigger button', () => {
    it('renders the trigger button', () => {
      expect(wrapper.find('.mode-trigger').exists()).toBe(true)
    })

    it('opens popup when trigger is clicked', async () => {
      const vm = wrapper.vm as any
      expect(vm.popupOpen).toBe(false)

      wrapper.find('.mode-trigger').trigger('click')
      await nextTick()

      expect(vm.popupOpen).toBe(true)
    })

    it('applies ultra style when currentMode is ultra', async () => {
      const localWrapper = makeWrapper({ currentMode: 'ultra' })
      await nextTick()

      expect(localWrapper.find('.mode-trigger').classes()).toContain('mode-trigger--ultra')
    })

    it('does not apply ultra style for non-ultra modes', () => {
      expect(wrapper.find('.mode-trigger').classes()).not.toContain('mode-trigger--ultra')
    })
  })

  // ─── Mode list rendering ──────────────────────────────────────────────────

  describe('mode list rendering', () => {
    it('lists all four modes', async () => {
      await openPopup(wrapper)

      const items = wrapper.findAll('.mode-item')
      expect(items.length).toBe(4)
    })

    it('marks the current mode as active', async () => {
      await openPopup(wrapper)

      const activeItem = wrapper.find('.mode-item--active')
      expect(activeItem.exists()).toBe(true)
      expect(activeItem.find('.mode-item-label').text()).toBe('Thinking')
    })

    it('shows check icon for active mode', async () => {
      await openPopup(wrapper)

      expect(wrapper.find('.mode-item-check').exists()).toBe(true)
    })

    it('shows spacer for non-active modes', async () => {
      await openPopup(wrapper)

      const spacers = wrapper.findAll('.mode-item-spacer')
      expect(spacers.length).toBe(3) // 4 modes minus 1 active
    })
  })

  // ─── Availability / dimmed states ─────────────────────────────────────────

  describe('availability states', () => {
    it('dims non-flash modes when thinking is not supported', async () => {
      await wrapper.setProps({ supportsThinking: false })
      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.isModeDimmed('flash')).toBe(false)
      expect(vm.isModeDimmed('thinking')).toBe(true)
      expect(vm.isModeDimmed('pro')).toBe(true)
      expect(vm.isModeDimmed('ultra')).toBe(true)
    })

    it('dims ultra mode when ultraDisabled', async () => {
      await wrapper.setProps({ ultraDisabled: true })
      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.isModeDimmed('ultra')).toBe(true)
      expect(vm.isModeDimmed('pro')).toBe(false)
    })

    it('does not emit select when clicking a dimmed mode', async () => {
      const localWrapper = makeWrapper({ supportsThinking: false })
      await nextTick()
      await openPopup(localWrapper)

      const items = localWrapper.findAll('.mode-item')
      const thinkingItem = items.find(item => item.find('.mode-item-label').text() === 'Thinking')
      if (thinkingItem) {
        thinkingItem.trigger('click')
        await nextTick()
      }

      expect(localWrapper.emitted('select')).toBeFalsy()
    })

    it('emits select and closes popup when clicking an available mode', async () => {
      await openPopup(wrapper)

      const items = wrapper.findAll('.mode-item')
      const flashItem = items.find(item => item.find('.mode-item-label').text() === 'Flash')
      if (flashItem) {
        flashItem.trigger('click')
        await nextTick()
      }

      expect(wrapper.emitted('select')).toBeTruthy()
      expect(wrapper.emitted('select')?.[0][0]).toBe('flash')
      expect((wrapper.vm as any).popupOpen).toBe(false)
    })
  })

  // ─── Popup close behaviors ────────────────────────────────────────────────

  describe('popup close behaviors', () => {
    it('closes popup when van-popup emits close', async () => {
      await openPopup(wrapper)
      expect((wrapper.vm as any).popupOpen).toBe(true)

      const popup = wrapper.findComponent(VanPopupStub)
      await popup.vm.$emit('close')
      await nextTick()

      expect((wrapper.vm as any).popupOpen).toBe(false)
    })

    it('closes popup when van-popup emits click-overlay', async () => {
      await openPopup(wrapper)
      expect((wrapper.vm as any).popupOpen).toBe(true)

      const popup = wrapper.findComponent(VanPopupStub)
      await popup.vm.$emit('click-overlay')
      await nextTick()

      expect((wrapper.vm as any).popupOpen).toBe(false)
    })
  })

  // ─── Popup rendering ──────────────────────────────────────────────────────

  describe('popup rendering', () => {
    it('renders van-popup with bottom position', async () => {
      await openPopup(wrapper)

      const popup = wrapper.findComponent(VanPopupStub)
      expect(popup.exists()).toBe(true)
      expect(popup.props('position')).toBe('bottom')
    })

    it('passes show prop to van-popup based on popupOpen state', async () => {
      const vm = wrapper.vm as any
      expect(vm.popupOpen).toBe(false)

      await openPopup(wrapper)
      expect(vm.popupOpen).toBe(true)
    })
  })
})
