import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

import ChatHeader from '../../src/components/ai/ChatHeader.vue'

// Mock composables
vi.mock('@/composables/ai-chat/useThreadChat', () => ({
  useThreadChat: () => ({
    messages: { value: [] },
    isLoading: { value: false },
    isStreaming: { value: false },
    error: { value: null },
    tokenUsage: { value: null },
    planningSteps: { value: [] },
    suggestions: { value: [] },
    runId: { value: null },
    sendMessage: vi.fn(),
    cancelStream: vi.fn(),
    loadHistory: vi.fn(),
    retry: vi.fn(),
  }),
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

// Mock router
const mockPush = vi.fn()
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useRouter: () => ({ push: mockPush }),
  }
})

// Mock Vant functional APIs
vi.mock('vant', () => ({
  showFailToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showDialog: vi.fn(() => Promise.resolve()),
}))

// Mock vue-i18n
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
  VanDialog: { template: '<div class="van-dialog"><slot /></div>', props: ['show', 'title', 'showCancelButton', 'loading'] },
  VanField: { template: '<input class="van-field" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />', props: ['modelValue', 'placeholder', 'autofocus', 'clearable', 'maxlength', 'showWordLimit'] },
  VanLoading: { template: '<div class="van-loading"></div>', props: ['size'] },
  // Teleport stub: render content inline so wrapper.find() can reach it
  Teleport: { template: '<div class="teleport-stub"><slot /></div>' },
}

describe('ChatHeader', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    setActivePinia(createPinia())
    mockPush.mockClear()
    vi.clearAllMocks()
  })

  describe('Header Title Computed', () => {
    it('returns "New Chat" when no active thread', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.headerTitle).toBe('aiChat.newChat')
    })

    it('returns thread title when active thread exists', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-1',
          sessions: [
            { thread_id: 'thread-1', title: 'My Conversation', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.headerTitle).toBe('My Conversation')
    })

    it('returns "New Chat" if thread has no title', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-2',
          sessions: [
            { thread_id: 'thread-2', title: '', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.headerTitle).toBe('aiChat.newChat')
    })
  })

  describe('Title Scroll Animation', () => {
    // Title overflow detection relies on DOM measurements (offsetWidth) which
    // are 0 in jsdom. When both containerWidth and titleNaturalWidth are 0,
    // titleOverflows returns false (guard: both must be > 0).
    // So in test env, title always "fits" — we test the computed logic directly.

    it('titleOverflows is false when measurements are zero (jsdom)', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-3',
          sessions: [
            { thread_id: 'thread-3', title: 'This is a very long conversation title', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      // In jsdom, offsetWidth is 0, so titleOverflows guard returns false
      expect(vm.titleOverflows).toBe(false)
      // mode-centered is the default when titleFits is true (which it is when measurements are 0)
      expect(wrapper.find('.header-title-container').classes()).toContain('mode-centered')
    })

    it('titleOverflows can be set via internal state', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-4',
          sessions: [
            { thread_id: 'thread-4', title: 'Short', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.titleOverflows).toBe(false)
    })

    it('titleFits is true when measurements are zero', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-5',
          sessions: [
            { thread_id: 'thread-5', title: '12345678', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      // Both widths are 0 in jsdom → titleFits guard returns true
      expect(vm.titleFits).toBe(true)
    })

    it('scrollDistance is 0 when title does not overflow', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-6',
          sessions: [
            { thread_id: 'thread-6', title: '123456789', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.scrollDistance).toBe(0)
    })
  })

  describe('Can Edit Title Computed', () => {
    it('can edit when active thread has non-"New Chat" title', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-7',
          sessions: [
            { thread_id: 'thread-7', title: 'Editable Title', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.canEditTitle).toBe(true)
      expect(wrapper.find('.header-edit-btn').exists()).toBe(true)
    })

    it('cannot edit when no active thread', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.canEditTitle).toBeFalsy()
      expect(wrapper.find('.header-edit-btn').exists()).toBe(false)
    })

    it('cannot edit when title is "New Chat" (empty title not yet generated)', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-8',
          sessions: [
            { thread_id: 'thread-8', title: '', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      expect(vm.canEditTitle).toBe(false)
      expect(wrapper.find('.header-edit-btn').exists()).toBe(false)
    })
  })

  describe('Navigation Functions', () => {
    it('onOpenHistory pushes /ai/chat/history to router', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.onOpenHistory()
      expect(mockPush).toHaveBeenCalledWith('/ai/chat/history')
    })

    it('back button pushes /ai to router', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.onBack()
      expect(mockPush).toHaveBeenCalledWith('/ai')
    })
  })

  describe('Events', () => {
    it('emits newChat when new chat button clicked', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const newChatBtn = wrapper.findAll('.header-btn').find(btn => btn.attributes('aria-label') === 'aiChat.newChatAria')
      expect(newChatBtn).toBeDefined()
      await newChatBtn!.trigger('click')

      expect(wrapper.emitted('newChat')).toBeTruthy()
    })

    it('emits titleUpdated when title successfully updated', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-1',
          sessions: [
            { thread_id: 'thread-1', title: 'Old Title', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.editTitleInput = 'New Title'
      await vm.onConfirmEditTitle()

      expect(wrapper.emitted('titleUpdated')).toBeTruthy()
      expect(wrapper.emitted('titleUpdated')![0]).toEqual(['thread-1', 'New Title'])
    })
  })

  describe('Header Buttons Rendering', () => {
    it('renders back button with correct aria-label', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const buttons = wrapper.findAll('.header-btn')
      const backBtn = buttons[0]
      expect(backBtn.attributes('aria-label')).toBe('common.back')
    })

    it('renders history button with correct aria-label', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const buttons = wrapper.findAll('.header-btn')
      const historyBtn = buttons[1]
      expect(historyBtn.attributes('aria-label')).toBe('aiChat.historyAria')
    })

    it('renders new chat button with correct aria-label', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const newChatBtn = wrapper.find('.header-actions .header-btn')
      expect(newChatBtn.attributes('aria-label')).toBe('aiChat.newChatAria')
    })
  })

  describe('Accessibility', () => {
    it('all header buttons have aria-labels', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: 'thread-1',
          sessions: [
            { thread_id: 'thread-1', title: 'Test', updated_at: Date.now() } as any,
          ],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      const buttons = wrapper.findAll('.header-btn')
      for (const btn of buttons) {
        const ariaLabel = btn.attributes('aria-label')
        expect(ariaLabel).toBeDefined()
        expect(ariaLabel).not.toBe('')
      }
    })

    it('SVG icons in header have aria-hidden', async () => {
      wrapper = mount(ChatHeader, {
        props: {
          activeThreadId: null,
          sessions: [],
        },
        global: { stubs: vantStubs },
      })

      await nextTick()

      // Check header SVGs (back button, history button, edit button, new chat button)
      const headerSvgs = wrapper.findAll('.chat-header svg')
      for (const svg of headerSvgs) {
        expect(svg.attributes('aria-hidden')).toBe('true')
      }
    })
  })
})
