<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { updateThread } from '@/api/ai-chat'
import TokenUsage from '@/components/ai-chat/TokenUsage.vue'
import type { ThreadSession } from '@/types/ai-chat/session'

defineOptions({ name: 'ChatHeader' })

/**
 * Realtime token usage from SSE values events.
 * Passed through to TokenUsage for header display.
 */
interface RealtimeTokenUsage {
  inputTokens: number
  outputTokens: number
  totalTokens: number
}

const props = defineProps<{
  activeThreadId: string | null
  sessions: ThreadSession[]
  /** Realtime token usage computed from SSE values events (AIChatBox.vue) */
  realtimeTokenUsage?: RealtimeTokenUsage | null
  isStreaming?: boolean
}>()

const emit = defineEmits<{
  back: []
  history: []
  newChat: []
  titleUpdated: [threadId: string, newTitle: string]
}>()

const router = useRouter()
const { t } = useI18n()

// Edit title state
const showEditTitleDialog = ref(false)
const editTitleInput = ref('')
const isUpdatingTitle = ref(false)

// Header title: show thread title or "New Chat"
const headerTitle = computed(() => {
  if (!props.activeThreadId) return t('aiChat.newChat')
  const session = props.sessions.find(s => s.thread_id === props.activeThreadId)
  return session?.title || t('aiChat.newChat')
})

// Check if title can be edited - only when there's an active thread AND the
// title has been generated (not the default "新对话"). Before the first
// message or while the LLM title is still pending, the edit button is hidden.
const canEditTitle = computed(() => {
  return !!props.activeThreadId && headerTitle.value !== t('aiChat.newChat')
})

/**
 * Responsive title overflow detection.
 *
 * The title container fills the flex space between the left buttons (back +
 * history) and the right actions (token usage + new chat). Its actual width
 * varies with viewport size. We measure:
 *   - container width (via ResizeObserver)
 *   - title text natural width (via an off-screen measurement span)
 *   - edit button width (24px fixed + gap)
 *
 * Two display modes:
 *   1. Fits: title + edit button centered together in the container
 *   2. Overflows: title scrolls left→right, edit button pinned to container right
 */
const titleWrapRef = ref<HTMLElement | null>(null)
const titleContainerRef = ref<HTMLElement | null>(null)
const titleTextRef = ref<HTMLElement | null>(null)
const measureSpanRef = ref<HTMLElement | null>(null)

const containerWidth = ref(0)
const titleNaturalWidth = ref(0)

// Edit button width: 24px icon + 4px gap from title
const EDIT_BTN_WIDTH = 28

// Whether title + edit button fits in the container
const titleFits = computed(() => {
  if (containerWidth.value === 0 || titleNaturalWidth.value === 0) return true
  // If no edit button, title always fits (no need to reserve space)
  if (!canEditTitle.value) return true
  return titleNaturalWidth.value + EDIT_BTN_WIDTH <= containerWidth.value
})

// Whether the title overflows its container (needs scroll animation)
const titleOverflows = computed(() => {
  if (containerWidth.value === 0 || titleNaturalWidth.value === 0) return false
  return titleNaturalWidth.value > containerWidth.value
})

// How far the title should scroll (text width minus visible width, + padding for breathing room)
const scrollDistance = computed(() => {
  if (!titleOverflows.value) return 0
  // The visible width is the container width; the text scrolls from 0 to
  // -(textWidth - containerWidth + padding). The padding gives a brief pause
  // at each end before reversing.
  return titleNaturalWidth.value - containerWidth.value + 40
})

// Dynamic style for title container based on mode
const titleContainerStyle = computed(() => {
  if (titleOverflows.value) {
    return { '--scroll-distance': scrollDistance.value + 'px' }
  }
  return {}
})

let resizeObserver: ResizeObserver | null = null

function measureTitle() {
  if (measureSpanRef.value && titleTextRef.value) {
    // Copy the title text to the measurement span (which has no width
    // constraints) to get the natural text width
    measureSpanRef.value.textContent = titleTextRef.value.textContent || ''
    titleNaturalWidth.value = measureSpanRef.value.offsetWidth
  }
}

function onResize(entries: ResizeObserverEntry[]) {
  for (const entry of entries) {
    if (entry.target === titleWrapRef.value) {
      containerWidth.value = entry.contentRect.width
    }
  }
}

onMounted(() => {
  nextTick(() => {
    measureTitle()
    if (titleWrapRef.value) {
      resizeObserver = new ResizeObserver(onResize)
      resizeObserver.observe(titleWrapRef.value)
      // Initial measurement
      containerWidth.value = titleWrapRef.value.offsetWidth
    }
  })
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
})

// Re-measure when the title text changes (e.g., LLM-generated title arrives)
watch(headerTitle, () => {
  nextTick(measureTitle)
})

function onEditTitle() {
  // If the title is still the default (LLM title not yet generated), start
  // with an empty input so the user can type a custom title from scratch.
  editTitleInput.value = headerTitle.value === t('aiChat.newChat') ? '' : headerTitle.value
  showEditTitleDialog.value = true
}

async function onConfirmEditTitle() {
  if (isUpdatingTitle.value) return // Prevent double submission
  if (!props.activeThreadId || !editTitleInput.value.trim()) return
  const newTitle = editTitleInput.value.trim()
  isUpdatingTitle.value = true
  try {
    await updateThread(props.activeThreadId, { title: newTitle })
    showSuccessToast(t('aiChat.renameSessionSuccess'))
    showEditTitleDialog.value = false // Close dialog only on success
    emit('titleUpdated', props.activeThreadId, newTitle)
  } catch {
    showFailToast(t('aiChat.renameSessionFailed'))
    // Keep dialog open on failure so user can retry
  } finally {
    isUpdatingTitle.value = false
  }
}

function onBack() {
  emit('back')
  router.push('/ai')
}

function onOpenHistory() {
  emit('history')
}

function onNewChat() {
  emit('newChat')
}
</script>

<template>
  <div class="chat-header">
    <button class="header-btn" :aria-label="t('common.back')" @click="onBack">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="15 18 9 12 15 6"/>
      </svg>
    </button>
    <button class="header-btn" :aria-label="t('aiChat.historyAria')" @click="onOpenHistory">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
    </button>
    <!-- Title wrap: title (truncated or scrolling) + inline edit button
         Layout modes (driven by JS measurement):
         - Fits: title + edit centered together
         - Overflows: title scrolls, edit pinned right -->
    <div ref="titleWrapRef" class="header-title-wrap">
      <div
        ref="titleContainerRef"
        class="header-title-container"
        :class="{
          'mode-centered': titleFits,
          'mode-scroll': titleOverflows,
          'mode-truncate': !titleFits && !titleOverflows,
        }"
        :style="titleContainerStyle"
      >
        <h1 ref="titleTextRef" class="header-title">{{ headerTitle }}</h1>
      </div>
      <button
        v-if="canEditTitle"
        class="header-edit-btn"
        :class="{ 'edit-pinned-right': titleOverflows }"
        :aria-label="t('aiChat.editTitle')"
        @click="onEditTitle"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
      </button>
      <!-- Off-screen measurement span: mirrors title text to compute natural width -->
      <span ref="measureSpanRef" class="title-measure-span" aria-hidden="true"></span>
    </div>
    <div class="header-actions">
      <TokenUsage v-if="activeThreadId" :thread-id="activeThreadId" :realtime-usage="realtimeTokenUsage" :is-streaming="isStreaming" />
      <button class="header-btn" :aria-label="t('aiChat.newChatAria')" @click="onNewChat">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </button>
    </div>

    <!-- Edit title dialog
         teleport="body" is required: .chat-header has backdrop-filter which
         creates a containing block for position:fixed descendants, trapping
         the dialog inside the 50px header without it. -->
    <van-dialog
      v-model:show="showEditTitleDialog"
      teleport="body"
      :title="t('aiChat.editTitle')"
      show-cancel-button
      :loading="isUpdatingTitle"
      @confirm="onConfirmEditTitle"
      @cancel="showEditTitleDialog = false"
    >
      <div style="padding: 16px 16px 8px">
        <van-field
          v-model="editTitleInput"
          :placeholder="t('aiChat.editTitlePlaceholder')"
          autofocus
          clearable
          maxlength="30"
          show-word-limit
        />
      </div>
    </van-dialog>
  </div>
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  padding: 0 4px;
  padding-top: env(safe-area-inset-top);
  height: calc(50px + env(safe-area-inset-top));
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.header-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: rgba(0, 0, 0, 0.7);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.header-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.9);
}

.header-title-wrap {
  /* flex:1 so the title region fills the space between the left buttons and
   * the right-pinned actions; the title then centers within this region
   * instead of shrinking to content width and hugging the left edge. */
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 0 4px;
  gap: 4px;
  position: relative;
}

.header-title-container {
  min-width: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  transition: max-width 0.2s ease;
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.9);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: center;
}

/* Mode 1: Title + edit button fit - center both */
.header-title-container.mode-centered {
  /* No max-width constraint - let content determine width so title + edit
   * button are centered together by parent's justify-content: center */
}

.header-title-container.mode-centered .header-title {
  white-space: nowrap;
  overflow: visible;
  text-overflow: unset;
}

/* Mode 2: Title overflows container - scroll animation */
.header-title-container.mode-scroll {
  max-width: 100%;
  /* Fade mask on right side so title doesn't scroll behind pinned edit button */
  mask-image: linear-gradient(to right, black calc(100% - 40px), transparent 100%);
  -webkit-mask-image: linear-gradient(to right, black calc(100% - 40px), transparent 100%);
}

.header-title-container.mode-scroll .header-title {
  white-space: nowrap;
  overflow: visible;
  text-overflow: unset;
  animation: title-scroll var(--scroll-duration, 8s) linear infinite;
  padding-right: 40px; /* Space for visual gap before repeat */
}

/* Mode 3: Title doesn't fit but doesn't overflow - truncate */
.header-title-container.mode-truncate {
  max-width: calc(100% - 32px); /* Reserve space for edit button */
}

.header-title-container.mode-truncate .header-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@keyframes title-scroll {
  0%, 10% {
    transform: translateX(0);
  }
  45%, 55% {
    transform: translateX(calc(-1 * var(--scroll-distance, 0px)));
  }
  90%, 100% {
    transform: translateX(0);
  }
}

.header-edit-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: rgba(0, 0, 0, 0.4);
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.header-edit-btn.edit-pinned-right {
  position: absolute;
  right: 4px;
}

.title-measure-span {
  position: absolute;
  visibility: hidden;
  white-space: nowrap;
  font-size: 15px;
  font-weight: 600;
  pointer-events: none;
}

.header-edit-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.7);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  /* Pin to the right edge so token-usage / new-chat buttons stay fixed
   * regardless of title length. */
  margin-left: auto;
  flex-shrink: 0;
}

/* Dark mode
 * Wrap the FULL selector in :global() - Vue scoped CSS only scopes the last
 * simple selector outside :global(), so `:global([data-theme='dark']) .x`
 * compiles to `[data-theme='dark'] .x` (no [data-v-xxx]) and never matches.
 * See AIChatInput.vue:472 for the same gotcha. */
:global([data-theme='dark'] .chat-header) {
  background: rgba(var(--bg-primary-rgb, 15, 17, 23), 0.95);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

:global([data-theme='dark'] .header-btn) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .header-btn:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

:global([data-theme='dark'] .header-title) {
  color: var(--text-primary);
}

:global([data-theme='dark'] .header-edit-btn) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .header-edit-btn:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}
</style>