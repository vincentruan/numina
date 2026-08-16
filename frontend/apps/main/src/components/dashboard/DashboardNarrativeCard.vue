<script setup lang="ts">
/**
 * DashboardNarrativeCard — 本月洞察 (U15 + U17 + U21)
 *
 * Shows the AI-generated monthly financial narrative on the Dashboard.
 * Dual-mode (plan §R4 "双层模型"):
 *   - In-page: streamNarrative SSE (real-time streaming preview)
 *   - Out-of-page: useTaskPolling recovers progress/result via AITask
 * Cancel button when running (U21).
 */
import { ref, computed, onMounted, onActivated, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showFailToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { streamNarrative } from '@/api/dashboard'
import { getAITask } from '@/api/ai'
import { useTaskPolling } from '@/composables/useTaskPolling'
import type { NarrativeStreamHandle } from '@/api/dashboard'

const { t } = useI18n()

const narrative = ref<string | null>(null)
const thinking = ref('')
const generatedAt = ref<string | null>(null)
const loading = ref(true)
const streaming = ref(false)
const narrativeTaskId = ref<string | null>(null)
const cancelling = ref(false)
let streamHandle: NarrativeStreamHandle | null = null
let taskCheckTimer: ReturnType<typeof setTimeout> | null = null

// Minimal DOMPurify config (matches AIReportPage)
const PURIFY_CONFIG = {
  ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'h3', 'h4', 'span'],
  ALLOWED_ATTR: ['class'],
}

const renderedNarrative = computed(() => {
  if (!narrative.value) return ''
  const html = marked.parse(narrative.value, { async: false }) as string
  return DOMPurify.sanitize(html, PURIFY_CONFIG)
})

const isRunning = computed(() => streaming.value || narrativeTaskId.value !== null)

// U17: AITask polling for out-of-page recovery + cancel.
const { cancel: cancelPolling } = useTaskPolling(narrativeTaskId, {
  onComplete: async () => {
    narrativeTaskId.value = null
    streaming.value = false
    // Task completed in background — reload cached narrative
    await loadCached()
  },
  onError: (task) => {
    narrativeTaskId.value = null
    streaming.value = false
    showToast(task.error_message || t('dashboard.narrative.error.generation_failed'))
  },
})

async function loadCached() {
  loading.value = true
  try {
    await triggerStream(false)
  } finally {
    loading.value = false
  }
}

async function triggerStream(_force = true) {
  streaming.value = true
  thinking.value = ''
  narrative.value = null

  // Track AITask shortly after triggering (backend creates it on cache miss).
  // Cleanup handled by onUnmounted.
  taskCheckTimer = setTimeout(async () => {
    taskCheckTimer = null
    try {
      const task = await getAITask('narrative')
      if (task.task_id && ['running', 'queued', 'post_processing'].includes(task.status)) {
        narrativeTaskId.value = task.task_id
      }
    } catch {
      // best-effort
    }
  }, 500)

  streamHandle = await streamNarrative({
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
      generatedAt.value = new Date().toISOString()
      streaming.value = false
      narrativeTaskId.value = null
    },
    onError: (message) => {
      streaming.value = false
      narrativeTaskId.value = null
      if (message.includes('auth_expired')) {
        showFailToast(t('dashboard.narrative.error.auth_expired'))
      } else {
        showFailToast(t('dashboard.narrative.error.generation_failed'))
      }
    },
  })
}

async function onGenerate() {
  await triggerStream(true)
}

async function onCancel() {
  if (!narrativeTaskId.value || cancelling.value) return
  cancelling.value = true
  try {
    // cancelPolling() internally calls cancelTaskById + stops polling — no double-cancel.
    await cancelPolling()
    streamHandle?.abort()
    streamHandle = null
    narrativeTaskId.value = null
    streaming.value = false
    showToast(t('aiTask.cancelled'))
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    cancelling.value = false
  }
}

// U17: resume polling if a narrative task is still running (user navigated
// away while generation was in progress, then returned to Dashboard).
async function resumeIfRunning() {
  try {
    const task = await getAITask('narrative')
    if (task.task_id && ['running', 'queued', 'post_processing'].includes(task.status)) {
      narrativeTaskId.value = task.task_id
      return true
    }
    if (['completed', 'failed', 'cancelled', 'timeout'].includes(task.status)) {
      narrativeTaskId.value = null
    }
  } catch {
    // ignore
  }
  return false
}

onMounted(async () => {
  const resumed = await resumeIfRunning()
  if (!resumed) {
    await loadCached()
  } else {
    loading.value = false
  }
})

// Dashboard is KeepAlive-cached; onActivated re-runs resume logic.
let hasActivated = false
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  await resumeIfRunning()
})

// Cleanup on unmount: stop task-check timer + abort in-flight SSE (C2/C3 fix).
onUnmounted(() => {
  if (taskCheckTimer) {
    clearTimeout(taskCheckTimer)
    taskCheckTimer = null
  }
  streamHandle?.abort()
  streamHandle = null
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
    <div class="narrative-header">
      <span class="narrative-title">
        <span class="narrative-icon">📈</span>
        {{ t('dashboard.narrative.title') }}
      </span>
      <span v-if="isRunning" class="narrative-status narrative-status--running">
        <van-loading size="12" type="spinner" color="var(--van-primary-color)" />
        {{ t('aiTask.status.running') }}
      </span>
      <span v-else-if="generatedAt" class="narrative-status">
        {{ t('dashboard.narrative.generatedAt', { time: formatTime(generatedAt) }) }}
      </span>
    </div>

    <!-- Streaming preview -->
    <div v-if="streaming" class="narrative-streaming">
      <div v-if="thinking" class="narrative-thinking">
        <van-collapse>
          <van-collapse-item :title="t('dashboard.narrative.thinking')" name="thinking">
            <div class="narrative-thinking-text">{{ thinking }}</div>
          </van-collapse-item>
        </van-collapse>
      </div>
      <div v-if="narrative" class="narrative-preview" v-html="renderedNarrative" />
      <van-skeleton v-else title :row="3" animate />
    </div>

    <!-- Cancel button when running (U21) -->
    <div v-else-if="isRunning && narrativeTaskId" class="narrative-cancel-row">
      <van-button
        plain
        type="danger"
        size="small"
        :loading="cancelling"
        :disabled="cancelling"
        @click="onCancel"
      >
        {{ t('aiTask.cancelBtn') }}
      </van-button>
    </div>

    <!-- Completed narrative -->
    <div v-else-if="narrative" class="narrative-content" v-html="renderedNarrative" />

    <!-- Empty state with generate button -->
    <div v-else-if="!loading" class="narrative-empty">
      <p class="narrative-empty-text">{{ t('dashboard.narrative.empty') }}</p>
      <van-button plain type="primary" size="small" :loading="loading" @click="onGenerate">
        {{ t('dashboard.narrative.generate') }}
      </van-button>
    </div>

    <!-- Loading initial state -->
    <div v-else class="narrative-loading">
      <van-skeleton title :row="2" animate />
    </div>
  </van-cell-group>
</template>

<style scoped>
.narrative-card {
  margin: 12px 0;
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
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.narrative-icon {
  font-size: 16px;
}
.narrative-status {
  font-size: 12px;
  color: var(--text-secondary);
}
.narrative-status--running {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--van-primary-color);
}
.narrative-streaming {
  padding: 0 16px 12px;
}
.narrative-thinking {
  margin-bottom: 8px;
}
.narrative-thinking :deep(.van-collapse-item__content) {
  font-size: 12px;
  color: var(--text-secondary);
}
.narrative-thinking-text {
  white-space: pre-wrap;
  max-height: 120px;
  overflow-y: auto;
}
.narrative-preview {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  opacity: 0.85;
}
.narrative-cancel-row {
  display: flex;
  justify-content: center;
  padding: 12px 16px;
}
.narrative-content {
  padding: 0 16px 16px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
}
.narrative-content :deep(p) {
  margin: 0 0 8px;
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
.narrative-loading {
  padding: 12px 16px;
}
</style>
