<script setup lang="ts">
/**
 * DashboardNarrativeCard — 本月洞察 (U15 + U17 + U21)
 *
 * Shows the AI-generated monthly financial narrative on the Dashboard.
 * Dual-mode (plan §R4 "双层模型"):
 *   - In-page: streamNarrative SSE (real-time streaming preview)
 *   - Out-of-page: useTaskResume recovers progress/result via AITask
 * Cancel button when running + regenerate button in footer (U21 + U17).
 *
 * task_id is delivered as the first SSE metadata event — no polling needed.
 */
import { ref, computed, onMounted, onActivated, onDeactivated, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showFailToast } from 'vant'
import { marked } from 'marked'
import { sanitizeMarkdown } from '@/utils/sanitize'
import { streamNarrative } from '@/api/dashboard'
import { useTaskResume } from '@/composables/useTaskResume'
import IIcon from '@/components/IIcon.vue'
import type { NarrativeBlockReason, NarrativeStreamHandle } from '@/api/dashboard'

const { t } = useI18n()

const narrative = ref<string | null>(null)
const thinking = ref('')
const generatedAt = ref<string | null>(null)
const loading = ref(true)
const streaming = ref(false)
const cancelling = ref(false)
const queued = ref(false)
const refreshing = ref(false)
const blockReason = ref<NarrativeBlockReason | null>(null)
const initialLoadFailed = ref(false)
const isThinkingExpanded = ref(true)
const thinkingStart = ref<number | null>(null)
const thinkingElapsed = ref(0)
const showScrollButton = ref(false)
const thinkingContentRef = ref<HTMLElement | null>(null)
let streamHandle: NarrativeStreamHandle | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null
let isAutoScrolling = false

const hasContent = computed(() => narrative.value !== null && narrative.value !== '')
const hasThinking = computed(() => thinking.value.length > 0)

const renderedNarrative = computed(() => {
  if (!narrative.value) return ''
  const html = marked.parse(narrative.value, { async: false }) as string
  // S1 fix: shared sanitize config (matches AIReportPage) so both consumers
  // allow full HTML markdown output while stripping XSS vectors uniformly.
  return sanitizeMarkdown(html)
})

const formattedElapsed = computed(() => {
  const secs = Math.round(thinkingElapsed.value / 1000)
  if (secs < 60) return `${secs}秒`
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}分${s}秒`
})

// v3: useTaskResume replaces inline resumeIfRunning + useTaskPolling
const resumeHandle = useTaskResume('dashboard-narrative', {
  onStreamEvent: (event, data) => {
    if (event === 'custom' && typeof data === 'object' && data !== null) {
      const d = data as Record<string, unknown>
      if (d.type === 'reasoning_delta') {
        thinking.value += (d.content as string) || ''
      } else if (d.type === 'messages') {
        if (!narrative.value) narrative.value = ''
        narrative.value += (d.content as string) || ''
      } else if (d.type === 'dashboard_narrative.result') {
        const payload = d.payload as Record<string, string> | undefined
        if (payload?.narrative) {
          narrative.value = payload.narrative
        }
      }
    }
  },
  onComplete: async () => {
    stopElapsedTimer()
    streaming.value = false
    queued.value = false
    // Task just finished — fetch the persisted result (may be JSON cache).
    await loadCached()
  },
  onError: () => {
    stopElapsedTimer()
    streaming.value = false
    queued.value = false
    // Don't toast here — the template shows inline error + retry instead
  },
})

const isRunning = computed(() => streaming.value || resumeHandle.taskId.value !== null)

function startElapsedTimer() {
  thinkingStart.value = Date.now()
  thinkingElapsed.value = 0
  stopElapsedTimer()
  elapsedTimer = setInterval(() => {
    if (thinkingStart.value) {
      thinkingElapsed.value = Date.now() - thinkingStart.value
    }
  }, 500)
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

function toggleThinking() {
  isThinkingExpanded.value = !isThinkingExpanded.value
}

function handleScroll() {
  const el = thinkingContentRef.value
  if (!el) return
  // Check if scrolled to bottom (within 20px threshold)
  const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20
  showScrollButton.value = !isAtBottom
}

function scrollToBottom() {
  const el = thinkingContentRef.value
  if (!el) return
  isAutoScrolling = true
  el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  // Reset flag after animation
  setTimeout(() => {
    isAutoScrolling = false
    showScrollButton.value = false
  }, 300)
}

function autoScrollToBottom() {
  if (isAutoScrolling) return
  const el = thinkingContentRef.value
  if (!el) return
  // Only auto-scroll if already at bottom
  const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 20
  if (isAtBottom) {
    el.scrollTop = el.scrollHeight
  }
}

// Watch thinking changes to auto-scroll during streaming
watch(
  () => thinking.value,
  () => {
    if (streaming.value) {
      nextTick(() => autoScrollToBottom())
    }
  },
)

// Watch expansion state to check scroll button visibility
watch(
  () => isThinkingExpanded.value,
  (expanded) => {
    if (expanded) {
      nextTick(() => {
        const el = thinkingContentRef.value
        if (el && el.scrollHeight > el.clientHeight) {
          showScrollButton.value = true
        }
      })
    }
  },
)

async function loadCached() {
  loading.value = true
  // `loading` is cleared by onDone/onError callbacks — NOT in a finally block.
  // This ensures the skeleton stays visible when the initial POST fails
  // (instead of falling through to the retry/error UI prematurely).
  await triggerStream(false)
}

async function triggerStream(force = true) {
  if (force) {
    thinking.value = ''
    narrative.value = null
    blockReason.value = null
    refreshing.value = true
    initialLoadFailed.value = false
    // Reset thinking to expanded for fresh generation
    isThinkingExpanded.value = true
  }
  streaming.value = true
  cancelling.value = false
  queued.value = false
  resumeHandle.triggerFailed.value = false
  resumeHandle.taskId.value = null

  startElapsedTimer()

  streamHandle = await streamNarrative({
    onTaskId: (taskId) => {
      resumeHandle.taskId.value = taskId
      queued.value = false
    },
    onQueued: (info) => {
      resumeHandle.taskId.value = info.taskId
      queued.value = true
      loading.value = false
    },
    onReasoningDelta: (content) => {
      thinking.value += content
    },
    onNarrativeDelta: (content) => {
      if (!narrative.value) narrative.value = ''
      narrative.value += content
    },
    onDone: (result) => {
      narrative.value = result.narrative || narrative.value
      thinking.value = result.thinking || thinking.value
      // Use backend timestamp for cache hits, current time for fresh generation
      generatedAt.value = result.generatedAt || new Date().toISOString()
      streaming.value = false
      queued.value = false
      refreshing.value = false
      loading.value = false
      resumeHandle.taskId.value = null
      stopElapsedTimer()
      // Collapse thinking after completion
      isThinkingExpanded.value = false
    },
    onBlocked: (info) => {
      blockReason.value = info
      streaming.value = false
      queued.value = false
      refreshing.value = false
      loading.value = false
      resumeHandle.taskId.value = null
      stopElapsedTimer()
    },
    onError: (message) => {
      const hadTaskId = resumeHandle.taskId.value !== null
      queued.value = false
      refreshing.value = false
      stopElapsedTimer()
      // T20: SSE stream failed. Two scenarios:
      // 1. Task was created (hadTaskId) → keep streaming + taskId so
      //    useTaskResume polling can recover the connection.
      // 2. POST itself failed (no taskId) → clear state, show skeleton/retry.
      if (!hadTaskId) {
        streaming.value = false
        loading.value = false
        resumeHandle.taskId.value = null
        if (!force) {
          initialLoadFailed.value = true
        } else {
          resumeHandle.triggerFailed.value = true
        }
      }
      // hadTaskId: streaming stays true, taskId preserved → polling resumes
      if (message.includes('auth_expired')) {
        showFailToast(t('dashboard.narrative.error.auth_expired'))
      }
    },
  }, force)
}

async function onGenerate() {
  await triggerStream(true)
}

// Retry button handler. Re-checks for a reusable task (running/completed),
// falls back to a fresh trigger when none exists.
async function onRetry() {
  const reused = await resumeHandle.retryTrigger()
  if (!reused) {
    await triggerStream(true)
  }
}

async function onCancel() {
  if (!resumeHandle.taskId.value || cancelling.value) return
  cancelling.value = true
  try {
    await resumeHandle.cancel()
    streamHandle?.abort()
    streamHandle = null
    resumeHandle.taskId.value = null
    streaming.value = false
    queued.value = false
    stopElapsedTimer()
    showToast(t('aiTask.cancelled'))
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    cancelling.value = false
  }
}

// v3: resume replaced by useTaskResume
onMounted(async () => {
  const resumed = await resumeHandle.resume()
  if (!resumed) {
    await loadCached()
  } else {
    loading.value = false
  }
})

// Dashboard is KeepAlive-cached; onActivated re-checks for running tasks.
// If content is already loaded, skip re-fetch to avoid flicker.
let hasActivated = false
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  if (hasContent.value) return
  await resumeHandle.resume()
})

// Dashboard is KeepAlive-cached — disconnect on deactivate, cleanup on unmount.
onDeactivated(() => {
  streamHandle?.abort()
  stopElapsedTimer()
  resumeHandle.disconnect()
})

onUnmounted(() => {
  stopElapsedTimer()
  resumeHandle.cleanup()
})

function formatTime(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}
</script>

<template>
  <van-cell-group inset class="narrative-card" data-test="dashboard-narrative-card">
    <!-- Header -->
    <div class="narrative-header">
      <span class="narrative-title">
        <span v-if="isRunning" class="narrative-icon narrative-icon--loading">
          <van-loading size="16px" type="spinner" color="#1989fa" />
        </span>
        <span v-else class="narrative-icon"></span>
        {{ t('dashboard.narrative.title') }}
      </span>

      <!-- Running: cancel button + shimmer status -->
      <span v-if="isRunning" class="narrative-status narrative-status--running">
        <van-button
          v-if="resumeHandle.taskId"
          plain
          type="danger"
          size="mini"
          :loading="cancelling"
          :disabled="cancelling"
          class="narrative-cancel-btn"
          @click.stop="onCancel"
        >
          {{ t('aiTask.cancelBtn') }}
        </van-button>
        <span v-else class="narrative-thinking-label">
          <van-loading size="12px" type="spinner" />
          {{ t('dashboard.narrative.thinking') }}
        </span>
      </span>

      <!-- Done: thinking elapsed time -->
      <span v-else-if="generatedAt && thinkingElapsed > 0" class="narrative-status narrative-status--done">
        {{ t('dashboard.narrative.thoughtFor', { duration: formattedElapsed }) }}
      </span>

      <!-- Done: generated time (cache hit, no elapsed tracked) -->
      <span v-else-if="generatedAt" class="narrative-status narrative-status--done">
        {{ t('dashboard.narrative.generatedAt', { time: formatTime(generatedAt) }) }}
      </span>

      <!-- Empty / blocked -->
      <span v-else-if="blockReason || (!loading && !hasContent)" class="narrative-status narrative-status--empty">
        {{ t('dashboard.narrative.empty') }}
      </span>

      <!-- Loading -->
      <span v-else class="narrative-status">
        <van-loading size="12px" type="spinner" />
      </span>
    </div>

    <!-- Streaming: thinking section (expanded by default) + narrative preview -->
    <div v-if="streaming" class="narrative-streaming">
      <div class="narrative-thinking-section">
        <div class="narrative-thinking-header-wrapper">
          <div class="narrative-thinking-header" @click="toggleThinking">
            <IIcon :icon="'lucide:brain'" size="18" class="narrative-thinking-icon" />
            <span class="narrative-thinking-title">{{ t('dashboard.narrative.thinking') }}</span>
            <span class="narrative-thinking-chevron">
              <van-loading size="12px" type="spinner" />
            </span>
          </div>
        </div>
        <div class="narrative-thinking-content-wrapper">
          <div
            ref="thinkingContentRef"
            class="narrative-thinking-content narrative-thinking-content--scrollable"
            @scroll="handleScroll"
          >
            <div v-if="hasThinking" class="narrative-thinking-text shimmer-text">{{ thinking }}</div>
            <div v-else class="narrative-thinking-text narrative-thinking-placeholder">
              {{ t('dashboard.narrative.thinkingPlaceholder') }}
            </div>
            <div class="narrative-thinking-loading-dot">
              <span class="loading-dot"></span>
            </div>
          </div>
          <button
            v-if="showScrollButton"
            class="narrative-scroll-to-bottom"
            @click="scrollToBottom"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
        </div>
      </div>
      <div v-if="narrative" class="narrative-preview" v-html="renderedNarrative" />
      <van-skeleton v-else title :row="3" animate />
    </div>

    <!-- Completed: thinking section (collapsible) + narrative content -->
    <template v-else-if="hasContent">
      <div v-if="hasThinking" class="narrative-thinking-section narrative-thinking--done">
        <div class="narrative-thinking-header-wrapper">
          <div class="narrative-thinking-header" @click="toggleThinking">
            <IIcon :icon="'lucide:brain'" size="18" class="narrative-thinking-icon" />
            <span class="narrative-thinking-title">
              {{ t('dashboard.narrative.thoughtFor', { duration: formattedElapsed }) }}
            </span>
            <span class="narrative-thinking-chevron" :class="{ 'narrative-thinking-chevron--collapsed': !isThinkingExpanded }">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </span>
          </div>
        </div>
        <div v-show="isThinkingExpanded" class="narrative-thinking-content-wrapper">
          <div
            ref="thinkingContentRef"
            class="narrative-thinking-content narrative-thinking-content--scrollable"
            @scroll="handleScroll"
          >
            <div class="narrative-thinking-text">{{ thinking }}</div>
          </div>
          <button
            v-if="showScrollButton"
            class="narrative-scroll-to-bottom"
            @click="scrollToBottom"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
        </div>
      </div>
      <div class="narrative-content narrative-content--with-thinking" v-if="hasThinking" v-html="renderedNarrative" />
      <div class="narrative-content" v-else v-html="renderedNarrative" />
    </template>

    <!-- Threshold gate -->
    <div v-else-if="blockReason" class="narrative-blocked">
      <p class="narrative-blocked-text">
        {{ blockReason.reason === 'insufficient_assets'
          ? t('dashboard.narrative.blocked.insufficient_assets', {
              count: blockReason.asset_count ?? 0,
              threshold: blockReason.threshold ?? 5,
            })
          : t('dashboard.narrative.blocked.insufficient_history')
        }}
      </p>
    </div>

    <!-- Loading skeleton — checked before any error/retry state so the
         skeleton stays visible during the initial POST request even when
         initialLoadFailed has already been set by onError (batched update). -->
    <div v-else-if="loading" class="narrative-loading">
      <van-skeleton title :row="2" animate />
    </div>

    <!-- Retry: initial auto-load POST failed (no cached narrative) -->
    <div v-else-if="initialLoadFailed" class="narrative-retry-row">
      <p class="narrative-retry-hint">{{ t('dashboard.narrative.retryHint') }}</p>
      <van-button plain type="primary" size="small" @click="onRetry">
        {{ t('dashboard.narrative.retry') }}
      </van-button>
    </div>

    <!-- Retry: resume-polling task creation failed -->
    <div v-else-if="resumeHandle.triggerFailed" class="narrative-retry-row">
      <p class="narrative-retry-hint">{{ t('dashboard.narrative.retryHint') }}</p>
      <van-button plain type="primary" size="small" @click="onRetry">
        {{ t('dashboard.narrative.retry') }}
      </van-button>
    </div>

    <!-- Inline error when task failed -->
    <div v-else-if="resumeHandle.status.value === 'failed'" class="narrative-retry-row">
      <p class="narrative-retry-hint narrative-error-text">
        {{ resumeHandle.task.value?.error_message || t('dashboard.narrative.error.generation_failed') }}
      </p>
      <van-button plain type="primary" size="small" @click="onRetry">
        {{ t('dashboard.narrative.retry') }}
      </van-button>
    </div>

    <!-- Empty state -->
    <div v-else class="narrative-empty">
      <p class="narrative-empty-text">{{ t('dashboard.narrative.empty') }}</p>
      <van-button plain type="primary" size="small" @click="onGenerate">
        {{ t('dashboard.narrative.generate') }}
      </van-button>
    </div>

    <!-- Footer: disclaimer + refresh button (matches FinanceCoachCard layout) -->
    <div v-if="hasContent && !streaming" class="narrative-footer">
      <span class="narrative-disclaimer">{{ t('dashboard.narrative.disclaimer') }}</span>
      <van-button size="mini" plain icon="replay" :loading="refreshing" @click.stop="onGenerate" />
    </div>
  </van-cell-group>
</template>

<style scoped>
.narrative-card {
  display: block;
  margin: 8px 0;
}
.narrative-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
}
.narrative-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.narrative-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4em;
  height: 1.4em;
  flex-shrink: 0;
  font-size: 16px;
}
.narrative-icon--loading {
  width: 20px;
  height: 20px;
}
.narrative-icon__svg {
  color: #1989fa;
}
.narrative-status {
  margin-left: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.narrative-status--running {
  color: var(--van-primary-color);
}
.narrative-status--done {
  color: var(--text-secondary);
}
.narrative-status--empty {
  opacity: 0.6;
}
.narrative-thinking-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.narrative-cancel-btn {
  margin-left: 4px;
}
.narrative-streaming {
  padding: 0 16px 12px;
}
.narrative-thinking-section {
  margin-bottom: 4px;
}
.narrative-thinking--done {
  margin-bottom: 8px;
}
.narrative-thinking-header-wrapper {
  padding-left: 9px;
}
.narrative-thinking-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  cursor: pointer;
  user-select: none;
}
.narrative-thinking-icon {
  color: #1989fa;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
}
.narrative-thinking-icon :deep(svg) {
  display: block;
}
.narrative-thinking-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}
.narrative-thinking-chevron {
  flex-shrink: 0;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  transition: transform 0.2s ease;
}
.narrative-thinking-chevron--collapsed {
  transform: rotate(-90deg);
}
.narrative-thinking-content-wrapper {
  position: relative;
  margin-left: 9px;
}
.narrative-thinking-content {
  padding-left: 12px;
  border-left: 2px solid #e8e8e8;
}
.narrative-thinking-content--scrollable {
  max-height: 200px;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #d0d0d0 transparent;
}
.narrative-thinking-content--scrollable::-webkit-scrollbar {
  width: 4px;
}
.narrative-thinking-content--scrollable::-webkit-scrollbar-track {
  background: transparent;
}
.narrative-thinking-content--scrollable::-webkit-scrollbar-thumb {
  background: #d0d0d0;
  border-radius: 2px;
}
.narrative-thinking-text {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
  color: #999;
}
.narrative-thinking-placeholder {
  font-style: italic;
  opacity: 0.6;
}
/* Shimmer animation for streaming thinking text */
.shimmer-text {
  background: linear-gradient(
    90deg,
    var(--text-secondary) 0%,
    var(--text-primary) 50%,
    var(--text-secondary) 100%
  );
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer 2s ease-in-out infinite;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.narrative-thinking-loading-dot {
  padding: 8px 0;
}
.loading-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1989fa;
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}
.narrative-scroll-to-bottom {
  position: absolute;
  bottom: 8px;
  right: 8px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.2s ease;
  z-index: 1;
}
.narrative-scroll-to-bottom:hover {
  background: #fff;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.16);
  color: var(--text-primary);
}
.narrative-preview {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  opacity: 0.85;
}
.narrative-content {
  padding: 0 16px 8px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
}
.narrative-content--with-thinking {
  padding-top: 0;
}
.narrative-content :deep(p) {
  margin: 0 0 8px;
}
.narrative-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 16px 8px;
}
.narrative-disclaimer {
  font-size: 11px;
  color: var(--van-text-color-3, #c8c9cc);
}
.narrative-empty {
  padding: 16px;
  text-align: center;
}
.narrative-empty-text {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.narrative-blocked {
  padding: 12px 16px;
}
.narrative-blocked-text {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}
.narrative-retry-row {
  padding: 16px;
  text-align: center;
}
.narrative-retry-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.narrative-error-text {
  color: var(--van-danger-color, #ee0a24);
}
.narrative-loading {
  padding: 12px 16px;
}
</style>
