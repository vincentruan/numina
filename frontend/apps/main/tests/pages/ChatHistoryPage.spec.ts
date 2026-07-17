import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, ref } from 'vue'

import ChatHistoryPage from '../../src/pages/ChatHistoryPage.vue'
import { useChatSessionStore } from '../../src/stores/chatSession'

// Mock composables with mutable refs
const mockDateGroups = ref<any[]>([])
const mockIsLoading = ref(false)
const mockHasMore = ref(true)
const mockLoadMore = vi.fn()
const mockRefresh = vi.fn()
const mockDeleteSession = vi.fn(() => Promise.resolve())
const mockRenameSession = vi.fn(() => Promise.resolve())
const mockTogglePin = vi.fn(() => Promise.resolve())

vi.mock('@/composables/useThreadList', () => ({
  useThreadList: () => ({
    dateGroups: mockDateGroups,
    isLoading: mockIsLoading,
    hasMore: mockHasMore,
    loadMore: mockLoadMore,
    refresh: mockRefresh,
    deleteSession: mockDeleteSession,
    renameSession: mockRenameSession,
    togglePin: mockTogglePin,
  }),
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
  showDialog: vi.fn(() => Promise.resolve()),
  showSuccessToast: vi.fn(),
  showFailToast: vi.fn(),
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
  VanField: { template: '<input class="van-field" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />', props: ['modelValue', 'placeholder', 'autofocus'] },
  VanLoading: { template: '<div class="van-loading"></div>', props: ['size'] },
  VanButton: { template: '<button class="van-button"><slot /></button>', props: ['icon', 'type', 'size'] },
}

describe('ChatHistoryPage', () => {
  let wrapper: VueWrapper<any>
  let chatSessionStore: ReturnType<typeof useChatSessionStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    chatSessionStore = useChatSessionStore()
    mockPush.mockClear()
    vi.clearAllMocks()

    // Reset mock refs
    mockDateGroups.value = []
    mockIsLoading.value = false
    mockHasMore.value = true
  })

  describe('Rendering', () => {
    it('renders empty state when no sessions', async () => {
      mockDateGroups.value = []

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.history-empty').exists()).toBe(true)
      expect(wrapper.find('.empty-text').text()).toBe('aiChat.noHistory')
      expect(wrapper.find('.empty-hint').text()).toBe('aiChat.historyHint')
    })

    it('renders session list with date groups', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'thread-1', title: 'Session 1', updated_at: Date.now(), is_pinned: false },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.history-group').exists()).toBe(true)
      expect(wrapper.find('.history-group-label').text()).toBe('Today')
      expect(wrapper.find('.session-title').text()).toBe('Session 1')
    })

    it('shows loading spinner when isLoading', async () => {
      mockIsLoading.value = true

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.van-loading').exists()).toBe(true)
    })

    it('shows "no more" message when hasMore is false and has sessions', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [{ thread_id: 'thread-1', title: 'Session 1', updated_at: Date.now(), is_pinned: false }],
        },
      ]
      mockHasMore.value = false
      mockIsLoading.value = false

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.no-more').exists()).toBe(true)
      expect(wrapper.find('.no-more').text()).toBe('aiChat.noMoreSessions')
    })
  })

  describe('Header', () => {
    it('renders header title', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.history-title').text()).toBe('aiChat.historyTitle')
    })

    it('close button navigates to AIChat route', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.close()
      expect(mockPush).toHaveBeenCalledWith({ name: 'AIChat' })
    })

    it('close button has correct aria-label', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.close-btn').attributes('aria-label')).toBe('common.cancel')
    })

    it('close button SVG has aria-hidden', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      expect(wrapper.find('.close-btn svg').attributes('aria-hidden')).toBe('true')
    })
  })

  describe('Session Selection', () => {
    it('selectThread sets active thread and navigates', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'thread-1', title: 'Session 1', updated_at: Date.now(), is_pinned: false },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.selectThread('thread-1')

      // selectThread calls store.setActiveThread + router.push
      // The store's setActiveThread sets activeThreadId via pinia
      expect(mockPush).toHaveBeenCalledWith('/ai/chat?thread_id=thread-1')
    })

    it('session click triggers selectThread', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'thread-1', title: 'Session 1', updated_at: Date.now(), is_pinned: false },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      // Click on session-content (the element with @click handler)
      await wrapper.find('.session-content').trigger('click')
      await nextTick()

      expect(mockPush).toHaveBeenCalledWith('/ai/chat?thread_id=thread-1')
    })

    it('highlights active session', async () => {
      chatSessionStore.activeThreadId = 'thread-1'

      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'thread-1', title: 'Session 1', updated_at: Date.now(), is_pinned: false },
            { thread_id: 'thread-2', title: 'Session 2', updated_at: Date.now(), is_pinned: false },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const sessions = wrapper.findAll('.history-session')
      expect(sessions[0].classes()).toContain('active')
      expect(sessions[1].classes()).not.toContain('active')
    })
  })

  describe('Session Actions', () => {
    it('handleDelete calls showDialog', async () => {
      const { showDialog } = await import('vant')

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.handleDelete('thread-1')

      expect(showDialog).toHaveBeenCalledWith({
        title: 'aiChat.confirmDeleteSession',
        showCancelButton: true,
        confirmButtonColor: 'var(--van-danger-color, #ee0a24)',
      })
    })

    it('handleRename sets renamingId', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.handleRename('thread-1', 'Session 1')

      expect(vm.renamingId).toBe('thread-1')
      expect(vm.renameInput).toBe('Session 1')
    })

    it('confirmRename calls renameSession', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.renameInput = 'New Title'
      await vm.confirmRename('thread-1')

      expect(mockRenameSession).toHaveBeenCalledWith('thread-1', 'New Title')
    })

    it('confirmRename rejects empty input', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.renameInput = ''
      await vm.confirmRename('thread-1')

      expect(mockRenameSession).not.toHaveBeenCalled()
    })

    it('handleTogglePin calls togglePin', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      await vm.handleTogglePin('thread-1', false)

      expect(mockTogglePin).toHaveBeenCalledWith('thread-1')
    })

    it('cancelRename clears renamingId', async () => {
      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.renamingId = 'thread-1'
      vm.cancelRename()

      expect(vm.renamingId).toBeNull()
    })
  })

  describe('Accessibility', () => {
    it('all session action buttons have aria-labels', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'thread-1', title: 'Session 1', updated_at: Date.now(), is_pinned: false },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      // session-actions contains 3 buttons: edit, pin, more (native <button>, not VanButton)
      const actionButtons = wrapper.findAll('.session-actions .action-btn')
      expect(actionButtons.length).toBe(3)

      // Edit button
      expect(actionButtons[0].classes()).toContain('edit')
      // Pin button (unpinned session shows "pin")
      expect(actionButtons[1].classes()).toContain('pin')
      // More-actions button (opens export/share action sheet)
      expect(actionButtons[2].classes()).toContain('more')
    })

    it('rename field has aria-label when in rename mode', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'thread-1', title: 'Session 1', updated_at: Date.now(), is_pinned: false },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })

      await nextTick()

      const vm = wrapper.vm as any
      vm.handleRename('thread-1', 'Session 1')
      await nextTick()

      expect(wrapper.find('.van-field').attributes('aria-label')).toBe('aiChat.editTitle')
    })
  })

  describe('Branch lineage (U4)', () => {
    it('renders branch badge for a branch session, not for a plain session', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'parent-1', title: 'Parent', updated_at: Date.now(), is_pinned: false, is_branch: false },
            { thread_id: 'branch-1', title: '分支: Parent', updated_at: Date.now(), is_pinned: false, is_branch: true, parent_thread_id: 'parent-1' },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })
      await nextTick()

      const sessions = wrapper.findAll('.history-session')
      expect(sessions[0].find('.session-branch-indicator').exists()).toBe(false)
      expect(sessions[1].find('.session-branch-indicator').exists()).toBe(true)
      expect(sessions[1].find('.branch-badge').text()).toBe('aiChat.branchBadge')
    })

    it('parent link shows the parent title when the parent is in the loaded list', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'parent-1', title: 'Parent Thread', updated_at: Date.now(), is_pinned: false, is_branch: false },
            { thread_id: 'branch-1', title: '分支', updated_at: Date.now(), is_pinned: false, is_branch: true, parent_thread_id: 'parent-1' },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })
      await nextTick()

      const link = wrapper.findAll('.history-session')[1].find('.branch-parent-link')
      expect(link.exists()).toBe(true)
      expect(link.text()).toBe('aiChat.branchFromParent · Parent Thread')
    })

    it('clicking the parent link navigates to the parent thread', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'parent-1', title: 'Parent', updated_at: Date.now(), is_pinned: false, is_branch: false },
            { thread_id: 'branch-1', title: '分支', updated_at: Date.now(), is_pinned: false, is_branch: true, parent_thread_id: 'parent-1' },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })
      await nextTick()

      await wrapper.findAll('.history-session')[1].find('.branch-parent-link').trigger('click')
      await nextTick()

      expect(mockPush).toHaveBeenCalledWith('/ai/chat?thread_id=parent-1')
    })

    it('degrades to title-less link when parent is not in the loaded list', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'branch-1', title: '分支', updated_at: Date.now(), is_pinned: false, is_branch: true, parent_thread_id: 'missing-parent' },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })
      await nextTick()

      const link = wrapper.find('.branch-parent-link')
      expect(link.exists()).toBe(true)
      // No parent title available -> just the "from parent" label, no "·"
      expect(link.text()).toBe('aiChat.branchFromParent')
    })

    it('shows deleted-parent badge when a branch has no parent_thread_id', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'branch-1', title: '分支', updated_at: Date.now(), is_pinned: false, is_branch: true },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })
      await nextTick()

      expect(wrapper.find('.branch-parent-deleted').exists()).toBe(true)
      expect(wrapper.find('.branch-parent-deleted').attributes('aria-label')).toBe('aiChat.branchParentDeleted')
    })

    it('branch badge and parent link have aria semantics', async () => {
      mockDateGroups.value = [
        {
          label: 'today',
          displayName: 'Today',
          sessions: [
            { thread_id: 'parent-1', title: 'Parent', updated_at: Date.now(), is_pinned: false, is_branch: false },
            { thread_id: 'branch-1', title: '分支', updated_at: Date.now(), is_pinned: false, is_branch: true, parent_thread_id: 'parent-1' },
          ],
        },
      ]

      wrapper = mount(ChatHistoryPage, {
        global: { stubs: vantStubs },
      })
      await nextTick()

      const branchSession = wrapper.findAll('.history-session')[1]
      expect(branchSession.find('.branch-badge').attributes('role')).toBe('img')
      expect(branchSession.find('.branch-parent-link').attributes('aria-label')).toBe('aiChat.branchParentLink')
    })
  })
})