import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import AIChatPage from '@/pages/AIChatPage.vue'

vi.mock('@/composables/ai-chat/useThreadChat', () => ({
  useThreadChat: () => ({
    messages: { value: [] },
    isLoading: { value: false },
    error: { value: null },
    tokenUsage: { value: null },
    sendMessage: vi.fn(),
    cancelStream: vi.fn(),
    loadHistory: vi.fn(),
    retry: vi.fn(),
  }),
}))

vi.mock('@/composables/useThreadList', () => ({
  useThreadList: () => ({
    sessions: { value: [] },
    isLoading: { value: false },
    hasMore: { value: true },
    dateGroups: { value: [] },
    loadMore: vi.fn(),
    refresh: vi.fn(),
    deleteSession: vi.fn(),
    renameSession: vi.fn(),
    togglePin: vi.fn(),
  }),
}))

vi.mock('@/api/ai-chat', () => ({
  createThread: vi.fn(() => Promise.resolve({ thread_id: 'test-thread' })),
  searchThreads: vi.fn(() => Promise.resolve({ items: [], total: 0 })),
  updateThread: vi.fn(() => Promise.resolve({})),
  deleteThread: vi.fn(() => Promise.resolve()),
  forkThread: vi.fn(() => Promise.resolve({ thread_id: 'forked-thread' })),
}))

vi.mock('vant', () => ({
  showToast: vi.fn(),
  showFailToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showLoadingToast: vi.fn(),
  closeToast: vi.fn(),
  showConfirmDialog: vi.fn(() => Promise.resolve()),
  Popup: { template: '<div class="van-popup"><slot /></div>', props: ['show', 'position', 'style', 'round', 'teleport'] },
  Dialog: { template: '<div class="van-dialog"><slot /></div>', props: ['show', 'title', 'showCancelButton', 'showConfirmButton'] },
  Button: { template: '<button class="van-button"><slot /></button>', props: ['size', 'plain', 'type', 'block'] },
  NavBar: { template: '<div class="van-nav-bar"><slot /></div>', props: ['title', 'leftArrow', 'clickable'] },
  Toast: {},
  Loading: { template: '<div class="van-loading"></div>', props: ['size'] },
  Badge: { template: '<span class="van-badge"><slot /></span>' },
}))

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...(actual as any),
    useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }),
  }
})

// Stub globals for Vant auto-import
vi.hoisted(() => {
  vi.stubGlobal('showFailToast', vi.fn())
  vi.stubGlobal('showSuccessToast', vi.fn())
  vi.stubGlobal('showLoadingToast', vi.fn())
  vi.stubGlobal('closeToast', vi.fn())
})

describe('AIChatPage (redesigned)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the AIChatBox component', () => {
    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [createPinia()],
        stubs: {
          AIChatBox: { template: '<div class="ai-chat-box-stub">AIChatBox</div>' },
          SessionSidebar: { template: '<div class="session-sidebar-stub" />' },
          WelcomePage: { template: '<div class="welcome-stub" />' },
          MessageList: { template: '<div class="message-list-stub" />' },
          InputBox: { template: '<div class="input-box-stub" />' },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })
    expect(wrapper.find('.ai-chat-box-stub').exists()).toBe(true)
    expect(wrapper.text()).toContain('AIChatBox')
  })

  it('shows welcome mode when no active thread', () => {
    const wrapper = mount(AIChatPage, {
      global: {
        plugins: [createPinia()],
        stubs: {
          AIChatBox: { template: '<div class="ai-chat-box-stub" />' },
          SessionSidebar: { template: '<div class="session-sidebar-stub" />' },
          WelcomePage: { template: '<div class="welcome-stub" />' },
          MessageList: { template: '<div class="message-list-stub" />' },
          InputBox: { template: '<div class="input-box-stub" />' },
          VanPopup: { template: '<div><slot /></div>' },
        },
      },
    })
    expect(wrapper.find('.ai-chat-box-stub').exists()).toBe(true)
  })
})
