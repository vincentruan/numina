<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { showDialog, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadList } from '@/composables/useThreadList'

defineOptions({ name: 'ChatHistory' })

const router = useRouter()
const store = useChatSessionStore()
const { dateGroups, isLoading, hasMore, loadMore, refresh, deleteSession, renameSession, togglePin } = useThreadList()
const { t } = useI18n()

const renamingId = ref<string | null>(null)
const renameInput = ref('')

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
  router.push('/ai/chat')
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
          :class="{ active: session.thread_id === store.activeThreadId }"
          @click="selectThread(session.thread_id)"
        >
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
            </template>
            <template v-else>
              <div class="session-title">{{ session.title || t('aiChat.newChat') }}</div>
              <div class="session-time">{{ new Date(session.updated_at).toLocaleString() }}</div>
            </template>
          </div>
          <div class="session-actions" @click.stop>
            <van-button
              icon="edit"
              type="default"
              size="small"
              :aria-label="t('aiChat.editTitle')"
              @click="handleRename(session.thread_id, session.title)"
            />
            <van-button
              :icon="session.is_pinned ? 'star' : 'star-o'"
              type="default"
              size="small"
              :aria-label="session.is_pinned ? t('aiChat.unpinSession') : t('aiChat.pinSession')"
              @click="handleTogglePin(session.thread_id, session.is_pinned)"
            />
            <van-button
              icon="delete"
              type="default"
              size="small"
              :aria-label="t('common.delete')"
              @click="handleDelete(session.thread_id)"
            />
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
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.history-session:hover,
.history-session.active {
  background: var(--van-primary-color-light, rgba(25, 137, 250, 0.1));
}

.session-info {
  flex: 1;
  min-width: 0;
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

.session-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.history-session:hover .session-actions {
  opacity: 1;
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

/* Dark mode */
:global([data-theme='dark']) .chat-history-page {
  background: var(--bg-primary);
}

:global([data-theme='dark']) .history-header {
  background: rgba(var(--bg-primary-rgb, 15, 17, 23), 0.95);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

:global([data-theme='dark']) .history-title {
  color: var(--text-primary);
}

:global([data-theme='dark']) .close-btn {
  color: var(--text-secondary);
}

:global([data-theme='dark']) .close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

:global([data-theme='dark']) .empty-icon {
  color: var(--text-secondary);
}

:global([data-theme='dark']) .empty-text {
  color: var(--text-secondary);
}

:global([data-theme='dark']) .empty-hint {
  color: var(--text-secondary);
}

:global([data-theme='dark']) .history-group-label {
  color: var(--text-secondary);
}

:global([data-theme='dark']) .session-title {
  color: var(--text-primary);
}

:global([data-theme='dark']) .session-time {
  color: var(--text-secondary);
}

:global([data-theme='dark']) .history-session:hover,
:global([data-theme='dark']) .history-session.active {
  background: rgba(25, 137, 250, 0.15);
}

:global([data-theme='dark']) .no-more {
  color: var(--text-secondary);
}
</style>