<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadList } from '@/composables/useThreadList'
import type { ThreadSession } from '@/types/ai-chat/session'

defineOptions({ name: 'ChatHistory' })

const router = useRouter()
const store = useChatSessionStore()
const { dateGroups, isLoading, hasMore, loadMore, refresh, deleteSession, renameSession, togglePin, exportSession, shareSession } = useThreadList()
const { t } = useI18n()

// U4: in-memory cross-join of parent_thread_id -> parent title. The history
// list is the set of sessions already loaded for this family; if a branch's
// parent thread is among them, we can show its title without a new endpoint.
// When the parent is not in the loaded list (paginated out or deleted), the
// branch entry degrades to a title-less "from parent session" link (Open
// Question (a) fallback).
const parentTitleById = computed(() => {
  const map = new Map<string, string>()
  for (const group of dateGroups.value) {
    for (const s of group.sessions) {
      if (s.thread_id && s.title) map.set(s.thread_id, s.title)
    }
  }
  return map
})

function parentTitleOf(session: ThreadSession): string | undefined {
  return session.parent_thread_id ? parentTitleById.value.get(session.parent_thread_id) : undefined
}

function goToParentThread(session: ThreadSession) {
  if (!session.parent_thread_id) return
  // Rely on the target route's 404 fallback to surface "parent deleted" if
  // the parent thread no longer exists, rather than probing here.
  selectThread(session.parent_thread_id)
}

const renamingId = ref<string | null>(null)
const renameInput = ref('')

// Swipe-to-reveal state
const swipedSessionId = ref<string | null>(null)
const swipeStartX = ref(0)
const swipeCurrentX = ref(0)
const isSwiping = ref(false)
const SWIPE_THRESHOLD = 80

// Action sheet (Vant 4 dropped the showActionSheet function API; use the
// <van-action-sheet> component instead). Tracks visibility and the target
// session so action callbacks know which thread to export/share.
const actionSheetVisible = ref(false)
const actionSheetSession = ref<ThreadSession | null>(null)
const actionSheetActions = computed(() => {
  const session = actionSheetSession.value
  if (!session) return []
  return [
    { key: 'export', name: t('aiChat.exportAction'), icon: 'down' },
    { key: 'share', name: t('aiChat.shareSession'), icon: 'share-o' },
    { key: 'delete', name: t('aiChat.deleteAction'), icon: 'delete-o', color: 'var(--van-danger-color, #ee0a24)' },
  ]
})

const exportSheetVisible = ref(false)
const exportSheetActions = [
  { key: 'export-markdown', name: t('aiChat.exportAsMarkdown') },
  { key: 'export-json', name: t('aiChat.exportAsJson') },
]

// Infinite scroll observer
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

onMounted(() => {
  refresh()

  // Set up IntersectionObserver for infinite scroll
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0].isIntersecting && hasMore.value && !isLoading.value) {
        loadMore()
      }
    },
    { rootMargin: '100px' }
  )
  if (sentinelRef.value) {
    observer.observe(sentinelRef.value)
  }
})

onUnmounted(() => {
  observer?.disconnect()
})

function close() {
  // Clear active thread so the AI chat page enters welcome (new conversation) mode
  store.clearActiveThread()
  router.push({ name: 'AIChat' })
}

function selectThread(threadId: string) {
  store.setActiveThread(threadId)
  router.push(`/ai/chat?thread_id=${threadId}`)
}

function handleDelete(threadId: string) {
  showDialog({
    title: t('aiChat.confirmDeleteSession'),
    showCancelButton: true,
    confirmButtonColor: 'var(--van-danger-color, #ee0a24)',
  })
    .then(async () => {
      try {
        await deleteSession(threadId)
        showSuccessToast(t('aiChat.deleteSessionSuccess'))
      } catch {
        showFailToast(t('aiChat.sendFailed'))
      }
    })
    .catch(() => {
      // user cancelled
    })
}

function handleRename(threadId: string, currentTitle: string) {
  renamingId.value = threadId
  renameInput.value = currentTitle
}

async function confirmRename(threadId: string) {
  if (!renameInput.value.trim()) return
  try {
    await renameSession(threadId, renameInput.value.trim())
    renamingId.value = null
    renameInput.value = ''
    showSuccessToast(t('aiChat.renameSessionSuccess'))
  } catch {
    showFailToast(t('aiChat.sendFailed'))
  }
}

function cancelRename() {
  renamingId.value = null
  renameInput.value = ''
}

async function handleTogglePin(threadId: string, isPinned: boolean) {
  try {
    await togglePin(threadId)
    showSuccessToast(isPinned ? t('aiChat.unpinSessionSuccess') : t('aiChat.pinSessionSuccess'))
  } catch {
    showFailToast(t('aiChat.sendFailed'))
  }
}

async function handleExport(threadId: string, format: 'markdown' | 'json') {
  try {
    await exportSession(threadId, format)
    showSuccessToast(t('aiChat.exportSuccess'))
  } catch {
    showFailToast(t('aiChat.exportFailed'))
  }
}

async function handleShare(threadId: string) {
  try {
    await shareSession(threadId)
    showSuccessToast(t('aiChat.shareLinkCopied'))
  } catch {
    showFailToast(t('aiChat.shareFailed'))
  }
}

function handleMore(session: ThreadSession) {
  actionSheetSession.value = session
  actionSheetVisible.value = true
}

function onActionSelect(action: { key: string }) {
  const session = actionSheetSession.value
  if (!session) return
  actionSheetVisible.value = false
  const key = action.key
  if (key === 'export') {
    // Open second-level export format picker
    exportSheetVisible.value = true
  } else if (key === 'share') {
    handleShare(session.thread_id)
  } else if (key === 'delete') {
    handleDelete(session.thread_id)
  }
}

function onExportSelect(action: { key: string }) {
  const session = actionSheetSession.value
  if (!session) return
  exportSheetVisible.value = false
  if (action.key === 'export-markdown') handleExport(session.thread_id, 'markdown')
  else if (action.key === 'export-json') handleExport(session.thread_id, 'json')
}

// Long press to open action sheet
let longPressTimer: ReturnType<typeof setTimeout> | null = null
const LONG_PRESS_DURATION = 500

function startLongPress(session: ThreadSession) {
  cancelLongPress()
  longPressTimer = setTimeout(() => {
    handleMore(session)
  }, LONG_PRESS_DURATION)
}

function cancelLongPress() {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

// Swipe-to-reveal handlers
function handleTouchStart(e: TouchEvent, sessionId: string) {
  swipeStartX.value = e.touches[0].clientX
  swipeCurrentX.value = e.touches[0].clientX
  isSwiping.value = false
}

function handleTouchMove(e: TouchEvent, sessionId: string) {
  const deltaX = swipeStartX.value - e.touches[0].clientX
  if (Math.abs(deltaX) > 10) {
    isSwiping.value = true
    swipeCurrentX.value = e.touches[0].clientX
  }
}

function handleTouchEnd(e: TouchEvent, sessionId: string) {
  const deltaX = swipeStartX.value - swipeCurrentX.value

  if (deltaX > SWIPE_THRESHOLD) {
    // Swipe left - reveal actions
    swipedSessionId.value = sessionId
  } else if (deltaX < -SWIPE_THRESHOLD) {
    // Swipe right - hide actions
    swipedSessionId.value = null
  }

  // Reset
  swipeStartX.value = 0
  swipeCurrentX.value = 0
  isSwiping.value = false
}

function closeSwipe(sessionId: string) {
  if (swipedSessionId.value === sessionId) {
    swipedSessionId.value = null
  }
}
</script>

<template>
  <div class="chat-history-page">
    <!-- Header -->
    <div class="history-header">
      <h3 class="history-title">{{ t('aiChat.historyTitle') }}</h3>
      <button class="close-btn" :aria-label="t('common.cancel')" @click="close">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <!-- Content -->
    <div class="history-content">
      <template v-if="dateGroups.length === 0 && !isLoading">
        <div class="history-empty">
          <div class="empty-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div class="empty-text">{{ t('aiChat.noHistory') }}</div>
          <div class="empty-hint">{{ t('aiChat.historyHint') }}</div>
        </div>
      </template>

      <div v-for="group in dateGroups" :key="group.label" class="history-group">
        <div class="history-group-label">{{ group.displayName }}</div>
        <div
          v-for="session in group.sessions"
          :key="session.thread_id"
          class="history-session"
          :class="{ active: session.thread_id === store.activeThreadId, swiped: swipedSessionId === session.thread_id }"
          @touchstart="handleTouchStart($event, session.thread_id)"
          @touchmove="handleTouchMove($event, session.thread_id)"
          @touchend="handleTouchEnd($event, session.thread_id)"
        >
          <div class="session-content" @click="selectThread(session.thread_id)">
            <div class="session-info">
              <template v-if="renamingId === session.thread_id">
                <van-field
                  v-model="renameInput"
                  :placeholder="session.title"
                  :aria-label="t('aiChat.editTitle')"
                  autofocus
                  @blur="cancelRename"
                  @keydown.enter="confirmRename(session.thread_id)"
                  @click.stop
                />
                <div v-if="session.original_title" class="session-original-title">
                  {{ t('aiChat.originalTitleHint', { title: session.original_title }) }}
                </div>
              </template>
              <template v-else>
                <div class="session-title">{{ session.title || t('aiChat.newChat') }}</div>
                <div class="session-time">{{ new Date(session.updated_at).toLocaleString() }}</div>
              </template>
            </div>
            <div class="session-pin-indicator" v-if="session.is_pinned">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
            </div>
            <!-- U4: branch lineage badge + parent link -->
            <div v-if="session.is_branch" class="session-branch-indicator">
              <span class="branch-badge" role="img" :aria-label="t('aiChat.branchBadge')">{{ t('aiChat.branchBadge') }}</span>
              <a
                v-if="session.parent_thread_id"
                class="branch-parent-link"
                href="#"
                :aria-label="t('aiChat.branchParentLink')"
                @click.prevent="goToParentThread(session)"
              >{{ parentTitleOf(session) ? t('aiChat.branchFromParent') + ' · ' + parentTitleOf(session) : t('aiChat.branchFromParent') }}</a>
              <span v-else class="branch-parent-deleted" role="img" :aria-label="t('aiChat.branchParentDeleted')">{{ t('aiChat.branchParentDeleted') }}</span>
            </div>
          </div>
          <div class="session-actions">
            <button class="action-btn edit" @click.stop="handleRename(session.thread_id, session.title)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
              {{ t('aiChat.editTitle') }}
            </button>
            <button class="action-btn pin" @click.stop="handleTogglePin(session.thread_id, session.is_pinned)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
              {{ session.is_pinned ? t('aiChat.unpinSession') : t('aiChat.pinSession') }}
            </button>
            <button class="action-btn more" @click.stop="handleMore(session)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Infinite scroll sentinel -->
      <div ref="sentinelRef" class="history-sentinel">
        <van-loading v-if="isLoading" size="20" />
        <div v-else-if="!hasMore && dateGroups.length > 0" class="no-more">
          {{ t('aiChat.noMoreSessions') }}
        </div>
      </div>
    </div>

    <!-- More-actions sheet (Vant 4 component API; showActionSheet was removed) -->
    <van-action-sheet
      v-model:show="actionSheetVisible"
      :actions="actionSheetActions"
      :cancel-text="t('common.cancel')"
      close-on-click-action
      @select="onActionSelect"
    />

    <!-- Export format picker (second level) -->
    <van-action-sheet
      v-model:show="exportSheetVisible"
      :title="t('aiChat.exportAsTitle')"
      :actions="exportSheetActions"
      :cancel-text="t('common.cancel')"
      close-on-click-action
      @select="onExportSelect"
    />
  </div>
</template>

<style scoped>
.chat-history-page {
  display: flex;
  flex-direction: column;
  position: fixed;
  inset: 0;
  background: var(--van-background, #f7f8fa);
  z-index: 100;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  padding-top: env(safe-area-inset-top);
  height: calc(56px + env(safe-area-inset-top));
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid var(--van-border-color, #eee);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.history-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--van-text-color, #333);
}

.close-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--van-text-color-2, #666);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
}

.close-btn:hover {
  background: var(--van-active-color, rgba(0, 0, 0, 0.06));
  color: var(--van-text-color, #333);
}

.history-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 0;
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 16px;
  text-align: center;
}

.empty-icon {
  color: var(--van-text-color-3, #999);
  margin-bottom: 16px;
}

.empty-text {
  font-size: 16px;
  color: var(--van-text-color-2, #666);
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 14px;
  color: var(--van-text-color-3, #999);
}

.history-group {
  margin-bottom: 8px;
}

.history-group-label {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--van-text-color-3, #999);
  font-weight: 500;
}

.history-session {
  position: relative;
  width: 100%;
  margin-bottom: 1px;
}

.session-content {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: var(--van-background-2, #fff);
  cursor: pointer;
  transition: transform 0.3s ease;
  z-index: 2;
}

.history-session.swiped .session-content {
  transform: translateX(-240px);
}

.session-actions {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  width: 240px;
  z-index: 1;
}

.action-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: none;
  color: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.action-btn:active {
  opacity: 0.7;
}

.action-btn.edit {
  background: var(--van-primary-color, #1989fa);
}

.action-btn.pin {
  background: var(--van-warning-color, #ff976a);
}

.action-btn.more {
  background: var(--van-text-color-2, #969799);
}

:global([data-theme='dark'] .session-content) {
  background: var(--bg-primary);
}

.session-title {
  font-size: 14px;
  color: var(--van-text-color, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 11px;
  color: var(--van-text-color-3, #999);
  margin-top: 2px;
}

.session-original-title {
  font-size: 11px;
  color: var(--van-text-color-3, #999);
  margin-top: 4px;
  font-style: italic;
}

.session-branch-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.branch-badge {
  display: inline-block;
  padding: 1px 6px;
  font-size: 10px;
  line-height: 1.4;
  color: var(--van-primary-color, #1989fa);
  background: rgba(25, 137, 250, 0.12);
  border-radius: 4px;
  white-space: nowrap;
}

.branch-parent-link {
  font-size: 11px;
  color: var(--van-primary-color, #1989fa);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}

.branch-parent-link:active {
  opacity: 0.7;
}

.branch-parent-deleted {
  font-size: 11px;
  color: var(--van-text-color-3, #999);
  white-space: nowrap;
}

.swipe-action-btn {
  height: 100%;
  min-width: 60px;
  padding: 0 12px;
}

.history-sentinel {
  display: flex;
  justify-content: center;
  padding: 16px;
}

.no-more {
  font-size: 12px;
  color: var(--van-text-color-3, #999);
}

/* Dark mode
 * Wrap the FULL selector in :global() - `:global([data-theme='dark']) .x`
 * compiles without the [data-v-xxx] scoping attr and never matches.
 * See AIChatInput.vue:472. */
:global([data-theme='dark'] .chat-history-page) {
  background: var(--bg-primary);
}

:global([data-theme='dark'] .history-header) {
  background: rgba(var(--bg-primary-rgb, 15, 17, 23), 0.95);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

:global([data-theme='dark'] .history-title) {
  color: var(--text-primary);
}

:global([data-theme='dark'] .close-btn) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .close-btn:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

:global([data-theme='dark'] .empty-icon) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .empty-text) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .empty-hint) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .history-group-label) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .session-title) {
  color: var(--text-primary);
}

:global([data-theme='dark'] .session-time) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .session-original-title) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .history-session.active) {
  background: rgba(25, 137, 250, 0.15);
}

:global([data-theme='dark'] .no-more) {
  color: var(--text-secondary);
}
</style>