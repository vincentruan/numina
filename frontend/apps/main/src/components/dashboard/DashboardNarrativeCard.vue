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
import { sanitizeMarkdown } from '@/utils/sanitize'
import { streamNarrative } from '@/api/dashboard'
import { useTaskResume } from '@/composables/useTaskResume'
import type { NarrativeBlockReason, NarrativeStreamHandle } from '@/api/dashboard'

const { t } = useI18n()

const narrative = ref<string | null>(null)
const thinking = ref('')
const generatedAt = ref<string | null>(null)
const loading = ref(true)
const streaming = ref(false)
const cancelling = ref(false)
const blockReason = ref<NarrativeBlockReason | null>(null)
const expanded = ref<string[]>([])
let streamHandle: NarrativeStreamHandle | null = null
let taskCheckTimer: ReturnType<typeof setTimeout> | null = null

const hasContent = computed(() => narrative.value !== null && narrative.value !== '')

const renderedNarrative = computed(() => {
  if (!narrative.value) return ''
  const html = marked.parse(narrative.value, { async: false }) as string
  // S1 fix: shared sanitize config (matches AIReportPage) so both consumers
  // allow full HTML markdown output while stripping XSS vectors uniformly.
  return sanitizeMarkdown(html)
})

// v3: useTaskResume replaces inline resumeIfRunning + useTaskPolling
const resumeHandle = useTaskResume('narrative', {
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
    streaming.value = false
    await loadCached()
  },
  onError: () => {
    streaming.value = false
    // Don't toast here — the template shows inline error + retry instead
  },
})

const isRunning = computed(() => streaming.value || resumeHandle.taskId.value !== null)

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
  blockReason.value = null
  resumeHandle.triggerFailed.value = false

  // T20: progressive retry (500ms->1s->2s->4s) to locate the AITask created
  // by this trigger. Runs in background; cleanup on unmount via checkCancelled.
  taskCheckTimer = setTimeout(async () => {
    taskCheckTimer = null
    await resumeHandle.waitForTask()
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
      resumeHandle.taskId.value = null
      // Cancel T20 timer — no task expected (cache hit)
      if (taskCheckTimer) { clearTimeout(taskCheckTimer); taskCheckTimer = null }
    },
    onBlocked: (info) => {
      blockReason.value = info
      streaming.value = false
      resumeHandle.taskId.value = null
      // Cancel T20 timer — no task expected (threshold gate)
      if (taskCheckTimer) { clearTimeout(taskCheckTimer); taskCheckTimer = null }
    },
    onError: (message) => {
      streaming.value = false
      resumeHandle.taskId.value = null
      if (taskCheckTimer) { clearTimeout(taskCheckTimer); taskCheckTimer = null }
      // Only toast auth_expired (global condition needing user action).
      // Other errors (circuit breaker, agent unavailable, network) are shown
      // inline via the template's error state — not as misleading toasts
      // on page load. Matches FinanceCoachCard's silent-error pattern.
      if (message.includes('auth_expired')) {
        showFailToast(t('dashboard.narrative.error.auth_expired'))
      }
    },
  })
}

async function onGenerate() {
  await triggerStream(true)
}

// T20: retry button handler. Re-checks for a reusable task (running/completed),
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

// Dashboard is KeepAlive-cached; onActivated re-runs resume logic.
let hasActivated = false
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  await resumeHandle.resume()
})

// Cleanup on unmount: stop task-check timer + abort in-flight SSE + cleanup resume.
onUnmounted(() => {
  if (taskCheckTimer) {
    clearTimeout(taskCheckTimer)
    taskCheckTimer = null
  }
  streamHandle?.abort()
  streamHandle = null
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
    <van-collapse v-model="expanded">
      <van-collapse-item name="narrative">
        <template #title>
          <div class="narrative-header">
            <span class="narrative-title">
              <span class="narrative-icon">📈</span>
              {{ t('dashboard.narrative.title') }}
            </span>
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
              <van-loading v-else size="12px" type="spinner" />
            </span>
            <span v-else-if="generatedAt" class="narrative-status">
              {{ t('dashboard.narrative.generatedAt', { time: formatTime(generatedAt) }) }}
            </span>
            <span v-else-if="blockReason" class="narrative-status narrative-status--empty">
              {{ t('dashboard.financeCoach.empty') }}
            </span>
            <span v-else-if="!loading" class="narrative-status narrative-status--empty">
              {{ t('dashboard.financeCoach.empty') }}
            </span>
            <span v-else class="narrative-status">
              <van-loading size="12px" type="spinner" />
            </span>
          </div>
        </template>

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

        <!-- Completed narrative -->
        <div v-else-if="hasContent" class="narrative-content" v-html="renderedNarrative" />

        <!-- Threshold gate: clear reason why generation is unavailable -->
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

        <!-- Retry button when trigger task creation failed (T20) -->
        <div v-else-if="resumeHandle.triggerFailed" class="narrative-retry-row">
          <p class="narrative-retry-hint">{{ t('dashboard.narrative.retryHint') }}</p>
          <van-button plain type="primary" size="small" @click="onRetry">
            {{ t('dashboard.narrative.retry') }}
          </van-button>
        </div>

        <!-- Inline error when task failed (replaces error toast) -->
        <div v-else-if="resumeHandle.status.value === 'failed'" class="narrative-retry-row">
          <p class="narrative-retry-hint narrative-error-text">
            {{ resumeHandle.task.value?.error_message || t('dashboard.narrative.error.generation_failed') }}
          </p>
          <van-button plain type="primary" size="small" @click="onRetry">
            {{ t('dashboard.narrative.retry') }}
          </van-button>
        </div>

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
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<style scoped>
.narrative-card {
  display: block;
  margin: 8px 0;
}
.narrative-card :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}
.narrative-card :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  min-width: 0;
}
.narrative-card :deep(.van-cell__value) {
  flex: none;
  width: 0;
}
.narrative-header {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
}
.narrative-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  font-weight: 600;
}
.narrative-icon {
  font-size: 16px;
}
.narrative-status {
  margin-left: 8px;
  font-size: 12px;
  color: var(--van-text-color-2);
}
.narrative-status--running {
  display: inline-flex;
  align-items: center;
}
.narrative-cancel-btn {
  margin-left: 4px;
}
.narrative-status--empty {
  color: var(--van-text-color-3);
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
