<template>
  <div class="literacy-report-page">
    <PageHeader :title="t('literacyReport.title')" back-to="/baby" />

    <!-- Loading skeleton -->
    <van-skeleton v-if="loading" :rows="6" animated class="page-skeleton" />

    <!-- Load failed -->
    <div v-else-if="loadError" class="failed-state">
      <EmptyState image="error" :description="t('literacyReport.loadFailed')" />
      <van-button plain type="primary" size="small" @click="reload">
        {{ t('literacyReport.retry') }}
      </van-button>
    </div>

    <!-- No children -->
    <div v-else-if="children.length === 0" class="empty-state">
      <EmptyState image="search" :description="t('literacyReport.noChildren')" />
    </div>

    <!-- Main content -->
    <template v-else>
      <ChildSelector
        :children="children"
        :selected-child-id="selectedChildId"
        @update:selected-child-id="onChildChange"
      />

      <!-- Week navigation -->
      <div v-if="history.length > 0" class="week-nav">
        <van-button
          size="small"
          icon="arrow-left"
          plain
          :disabled="!canGoPrev"
          @click="goPrev"
        />
        <span class="week-label">{{ currentWeekStart ? formatWeekStart(currentWeekStart) : '' }}</span>
        <van-button
          size="small"
          icon="arrow"
          plain
          :disabled="!canGoNext"
          @click="goNext"
        />
      </div>

      <!-- Report content -->
      <WeeklyReportCard v-if="report" :report="report" />

      <!-- Streaming preview (during generation) -->
      <div v-else-if="stream.status.value === 'streaming' || stream.status.value === 'connecting'" class="streaming-preview">
        <div class="streaming-header">
          <van-loading size="18" color="var(--van-primary-color)" />
          <span class="streaming-label">{{ t('literacyReport.generating') }}</span>
          <!-- U21: cancel button when AITask is running -->
          <van-button
            v-if="resumeHandle.taskId"
            plain
            type="danger"
            size="small"
            :loading="literacyCancelling"
            :disabled="literacyCancelling"
            class="streaming-cancel-btn"
            @click="onLiteracyCancel"
          >
            {{ t('aiTask.cancelBtn') }}
          </van-button>
        </div>
        <div v-if="stream.narrative.value" class="streaming-text">
          {{ stream.narrative.value }}
        </div>
      </div>

      <!-- Stream error -->
      <div v-else-if="stream.status.value === 'error'" class="stream-error">
        <EmptyState image="error" :description="stream.errorMessage.value || t('literacyReport.generateFailed')" />
        <van-button plain type="primary" size="small" @click="regenerate">
          {{ t('literacyReport.retry') }}
        </van-button>
      </div>

      <!-- Task failed (from resume detection) -->
      <div v-else-if="resumeHandle.status.value === 'failed'" class="stream-error">
        <EmptyState image="error" :description="resumeHandle.task.value?.error_message || t('literacyReport.generateFailed')" />
        <van-button plain type="primary" size="small" @click="onTaskRetry">
          {{ t('literacyReport.retry') }}
        </van-button>
      </div>

      <!-- No report for this week -->
      <div v-else class="empty-state">
        <EmptyState image="search" :description="t('literacyReport.noReport')" />
      </div>

      <!-- Regenerate button (bottom, only when a report exists or stream completed) -->
      <div v-if="report || stream.status.value === 'completed'" class="regenerate-bar">
        <van-button
          plain
          type="primary"
          size="small"
          icon="replay"
          :loading="stream.status.value === 'streaming' || stream.status.value === 'connecting'"
          @click="regenerate"
        >
          {{ t('literacyReport.regenerate') }}
        </van-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast, showFailToast } from 'vant'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ChildSelector from '@/components/literacy/ChildSelector.vue'
import WeeklyReportCard from '@/components/literacy/WeeklyReportCard.vue'
import {
  getReportChildren,
  getReport,
  getReportHistory,
} from '@/api/literacy'
import { parseApiDate } from '@/utils/format'
import type { ReportChild, WeeklyReportResponse, ReportHistoryWeek } from '@/api/literacy'
import { useLiteracyStream } from '@/composables/useLiteracyStream'
import { useTaskResume } from '@/composables/useTaskResume'

defineOptions({ name: 'LiteracyReportPage' })

const { t } = useI18n()
const route = useRoute()

const loading = ref(true)
const loadError = ref(false)
const children = ref<ReportChild[]>([])
const selectedChildId = ref('')
const report = ref<WeeklyReportResponse | null>(null)
const history = ref<ReportHistoryWeek[]>([])
const currentWeekStart = ref<string | null>(null)

const reportLoading = ref(false)
const stream = useLiteracyStream()

// v3: useTaskResume replaces inline resumeIfRunning + useTaskPolling
const resumeHandle = useTaskResume('literacy', {
  onComplete: async () => {
    if (selectedChildId.value) {
      await loadReport()
    }
  },
  onError: () => {
    // Task failed — still try to load whatever persisted report exists
    if (selectedChildId.value) {
      loadReport()
    }
  },
})
const literacyCancelling = ref(false)

const currentHistoryIndex = computed(() => {
  if (!currentWeekStart.value) return -1
  return history.value.findIndex(w => w.week_start === currentWeekStart.value)
})

const canGoPrev = computed(() => {
  const idx = currentHistoryIndex.value
  return idx > 0 && history.value.slice(0, idx).some(w => w.has_report)
})

const canGoNext = computed(() => {
  const idx = currentHistoryIndex.value
  if (idx < 0 || idx >= history.value.length - 1) return false
  return history.value.slice(idx + 1).some(w => w.has_report)
})

async function init() {
  loading.value = true
  loadError.value = false
  try {
    const childListRes = await getReportChildren()
    children.value = childListRes.children
    if (children.value.length > 0) {
      // Pre-select child from query param (e.g. from BabyPage navigation)
      const queryChildId = route.query.child_id as string | undefined
      const match = queryChildId && children.value.find(c => c.child_id === queryChildId)
      selectedChildId.value = match ? match.child_id : children.value[0].child_id
    }
  } catch (err) {
    loadError.value = true
    console.error('[LiteracyReport] init failed:', err)
    showFailToast(t('literacyReport.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadReport() {
  if (!selectedChildId.value) return
  reportLoading.value = true
  try {
    const [reportRes, historyRes] = await Promise.all([
      getReport(selectedChildId.value, currentWeekStart.value ?? undefined).catch(() => null),
      getReportHistory(selectedChildId.value).catch(() => ({ weeks: [] })),
    ])
    report.value = reportRes
    history.value = historyRes.weeks ?? []
    if (!currentWeekStart.value && history.value.length > 0) {
      const firstWithReport = history.value.find(w => w.has_report)
      currentWeekStart.value = firstWithReport?.week_start ?? history.value[0].week_start
      skipNextWatch = true
      if (firstWithReport && !reportRes) {
        const retry = await getReport(selectedChildId.value, currentWeekStart.value).catch(() => null)
        report.value = retry
      }
    }
  } catch {
    report.value = null
    showFailToast(t('literacyReport.loadFailed'))
  } finally {
    reportLoading.value = false
  }
}

function onChildChange(childId: string) {
  selectedChildId.value = childId
  currentWeekStart.value = null
}

async function reload() {
  await init()
  if (children.value.length > 0) {
    await loadReport()
  }
}

function goPrev() {
  const idx = currentHistoryIndex.value
  for (let i = idx - 1; i >= 0; i--) {
    if (history.value[i]?.has_report) {
      currentWeekStart.value = history.value[i].week_start
      return
    }
  }
}

function goNext() {
  const idx = currentHistoryIndex.value
  for (let i = idx + 1; i < history.value.length; i++) {
    if (history.value[i]?.has_report) {
      currentWeekStart.value = history.value[i].week_start
      return
    }
  }
}

function formatWeekStart(weekStart: string): string {
  try {
    const d = parseApiDate(weekStart)
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return weekStart
  }
}

async function regenerate() {
  if (!selectedChildId.value) return
  stream.reset()
  report.value = null
  await stream.connect(selectedChildId.value, true)
  // After stream completes, reload the persisted report
  if (stream.status.value === 'completed') {
    await loadReport()
  }
}

async function onTaskRetry() {
  report.value = null
  await regenerate()
}

watch(stream.status, (val) => {
  if (val === 'completed' && selectedChildId.value) {
    loadReport()
  }
})

watch(selectedChildId, () => {
  if (skipNextWatch) { skipNextWatch = false; return }
  loadReport()
})

watch(currentWeekStart, (val, oldVal) => {
  if (val !== oldVal && val) {
    loadReport()
  }
})

let skipNextWatch = true

// v3: resume replaced by useTaskResume

async function onLiteracyCancel() {
  if (!resumeHandle.taskId.value || literacyCancelling.value) return
  literacyCancelling.value = true
  try {
    await resumeHandle.cancel()
    stream.abort()
    resumeHandle.taskId.value = null
    showToast(t('aiTask.cancelled'))
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    literacyCancelling.value = false
  }
}

onMounted(async () => {
  await init()
  if (children.value.length > 0) {
    // Always load the cached report first for immediate display.
    // resume() checks for running literacy tasks — if found, SSE will
    // update the report via onComplete when the stream finishes.
    await loadReport()
    await resumeHandle.resume()
    // If a running task was found, SSE will deliver updates via onStreamEvent.
    // No need to poll; the stream will trigger loadReport() on completion.
  }
})

onUnmounted(() => {
  // v3 fix: use disconnect() (not cleanup()) to preserve step-state so that
  // resume() can restore the timeline when the user navigates back.
  resumeHandle.disconnect()
})
</script>

<style scoped>
.literacy-report-page {
  min-height: 100vh;
  padding-bottom: 24px;
  background: var(--bg-primary);
}

.page-skeleton {
  padding: 16px;
}

.failed-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  gap: 12px;
}

.week-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 8px 16px 4px;
}

.week-label {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  min-width: 100px;
  text-align: center;
}

.streaming-preview {
  margin: 12px 16px;
  padding: 16px;
  background: var(--card-bg, #f5f5ff);
  border-radius: 12px;
  border: 1px dashed var(--van-primary-color);
}

.streaming-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.streaming-label {
  font-size: 14px;
  color: var(--van-primary-color);
  font-weight: 500;
}

/* U21: cancel button inside streaming header */
.streaming-cancel-btn {
  margin-left: auto;
}

.streaming-text {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.stream-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 24px;
  gap: 12px;
}

.regenerate-bar {
  display: flex;
  justify-content: center;
  padding: 16px;
}
</style>
