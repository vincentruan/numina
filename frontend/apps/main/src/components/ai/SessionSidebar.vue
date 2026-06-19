<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { showDialog, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadList } from '@/composables/useThreadList'

const emit = defineEmits<{
  selectThread: [threadId: string]
}>()

const store = useChatSessionStore()
const { dateGroups, isLoading, hasMore, loadMore, refresh, deleteSession, renameSession, togglePin } = useThreadList()
const { t } = useI18n()

const visible = ref(false)
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

function open() {
  visible.value = true
  refresh()
}

function close() {
  visible.value = false
}

function refreshSidebar() {
  refresh()
}

function selectThread(threadId: string) {
  store.setActiveThread(threadId)
  emit('selectThread', threadId)
  close()
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

defineExpose({ open, close, refreshSidebar })
</script>

<template>
  <!-- Overlay trigger button -->
  <van-button
    class="sidebar-trigger"
    icon="bars"
    type="default"
    size="small"
    @click="open"
  />

  <!-- Sidebar overlay -->
  <van-overlay :show="visible" @click="close">
    <div class="sidebar-overlay" @click.stop>
      <div class="sidebar-header">
        <h3 class="sidebar-title">{{ t('aiChat.historyTitle') }}</h3>
        <van-button icon="cross" type="default" size="small" @click="close" />
      </div>

      <div class="sidebar-content">
        <template v-if="dateGroups.length === 0 && !isLoading">
          <div class="sidebar-empty">{{ t('aiChat.noHistory') }}</div>
        </template>

        <div v-for="group in dateGroups" :key="group.label" class="sidebar-group">
          <div class="sidebar-group-label">{{ group.displayName }}</div>
          <div
            v-for="session in group.sessions"
            :key="session.thread_id"
            class="sidebar-session"
            :class="{ active: session.thread_id === store.activeThreadId }"
            @click="selectThread(session.thread_id)"
          >
            <div class="session-info">
              <template v-if="renamingId === session.thread_id">
                <van-field
                  v-model="renameInput"
                  :placeholder="session.title"
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
                @click="handleRename(session.thread_id, session.title)"
              />
              <van-button
                :icon="session.is_pinned ? 'star' : 'star-o'"
                type="default"
                size="small"
                @click="handleTogglePin(session.thread_id, session.is_pinned)"
              />
              <van-button
                icon="delete"
                type="default"
                size="small"
                @click="handleDelete(session.thread_id)"
              />
            </div>
          </div>
        </div>

        <!-- Infinite scroll sentinel -->
        <div ref="sentinelRef" class="sidebar-sentinel">
          <van-loading v-if="isLoading" size="20" />
        </div>
      </div>
    </div>
  </van-overlay>
</template>

<style scoped>
.sidebar-trigger {
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 100;
}

.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 300px;
  background: var(--van-background-2, #f7f8fa);
  display: flex;
  flex-direction: column;
  z-index: 2000;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--van-border-color, #eee);
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--van-text-color, #333);
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.sidebar-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--van-text-color-3, #999);
  font-size: 14px;
}

.sidebar-group {
  margin-bottom: 8px;
}

.sidebar-group-label {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--van-text-color-3, #999);
  font-weight: 500;
}

.sidebar-session {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}

.sidebar-session:hover,
.sidebar-session.active {
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

.sidebar-session:hover .session-actions {
  opacity: 1;
}

.sidebar-sentinel {
  display: flex;
  justify-content: center;
  padding: 16px;
}
</style>
