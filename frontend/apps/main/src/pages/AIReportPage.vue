<template>
  <div class="ai-report-page">
    <PageHeader :title="t('aiReport.title')" />

    <!-- Three-step timeline (shown only during active generation or cache hit) -->
    <ReportStepTimeline
      v-if="isGenerating || stream.cached.value"
      :step1-status="stream.step1Status.value"
      :step2-status="stream.step2Status.value"
      :step3-status="stream.step3Status.value"
      :step1-thinking="stream.step1Thinking.value"
      :tool-calls="stream.toolCalls.value"
      :tool-results="stream.toolResults.value"
      :step2-json="stream.step2Json.value"
      :streaming="isGenerating"
      :cached="stream.cached.value"
      :progress-message="stream.progressMessage.value"
      :has-markdown-fallback="hasMarkdownFallback"
      @force="onGenerate(true)"
      @view-markdown="loadFallbackMarkdown"
    />

    <!-- Cancel button when generating (U21: user-initiated task cancel) -->
    <div v-if="isGenerating && reportTaskId" class="report-cancel-row">
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

    <!-- Notice bar when generating new report while previous exists -->
    <div v-if="isGenerating && currentReport && !stream.cached.value" class="previous-report-banner">
      <van-notice-bar
        mode="closeable"
        left-icon="info-o"
        :text="t('aiReport.previousReportWhileGenerating')"
        background="#e8f4ff"
        color="#1890ff"
      />
    </div>

    <!-- Failed state (show only when error and no report) -->
    <div v-if="stream.status.value === 'error' && !currentReport" class="failed-placeholder">
      <van-icon name="warning-o" size="48" class="failed-icon" />
      <!-- Elastic fallback: step1 markdown 落盘 succeeded but step2/3 failed -->
      <template v-if="hasMarkdownFallback">
        <p class="failed-text">{{ t('aiReport.conversionFailedButMarkdown') }}</p>
        <van-button type="primary" size="small" @click="loadFallbackMarkdown">
          {{ t('aiReport.viewMarkdownFallback') }}
        </van-button>
      </template>
      <template v-else>
        <p class="failed-text">{{ stream.errorMessage.value || t('toast.aiGenerateFailed') }}</p>
      </template>
      <van-button plain size="small" :loading="false" style="margin-top: 8px" @click="onGenerate()">
        {{ t('aiTask.retry') }}
      </van-button>
    </div>

    <!-- Task failed from resume detection (replaces error toast) -->
    <div v-else-if="resumeHandle.status.value === 'failed' && !currentReport && !isGenerating" class="failed-placeholder">
      <van-icon name="warning-o" size="48" class="failed-icon" />
      <p class="failed-text">{{ resumeHandle.task.value?.error_message || t('toast.aiGenerateFailed') }}</p>
      <van-button plain size="small" style="margin-top: 8px" @click="onGenerate()">
        {{ t('aiTask.retry') }}
      </van-button>
    </div>

    <!-- No report yet (only show when not failed/generating and no report) -->
    <div v-else-if="!currentReport && !isGenerating" class="empty-state">
      <EmptyState image="search" :description="t('aiReport.noReport')" />
      <div class="empty-actions">
        <van-button type="primary" block :loading="isGenerating" @click="onGenerate()">
          {{ t('aiTask.startBtn') }}
        </van-button>
        <p class="empty-tip">{{ t('aiReport.startAnalyze') }}</p>
      </div>
    </div>

    <!-- Report content (show when report exists, whether generating or not) -->
    <template v-if="currentReport">
      <div ref="reportContentRef">
      <!-- Overall score -->
      <div class="overall-section">
        <div class="overall-score-wrap">
          <div class="overall-score-circle">
            <svg viewBox="0 0 120 120" class="score-ring-svg">
              <circle cx="60" cy="60" r="54" fill="none" class="score-ring-bg" />
              <circle
                cx="60"
                cy="60"
                r="54"
                fill="none"
                class="score-ring-fill"
                :stroke-dasharray="`${scoreProgress} ${324 - scoreProgress}`"
                stroke-dashoffset="81"
              />
            </svg>
            <div class="score-inner">
              <span class="score-number">{{ currentReport.overall_score ?? 0 }}</span>
              <span class="score-unit">{{ t('aiReport.scoreUnit') }}</span>
            </div>
          </div>
          <div class="overall-label">{{ t('aiReport.overallScore') }}</div>
        </div>
        <!-- eslint-disable vue/no-v-html -->
        <p class="overall-summary" v-html="renderedSummary" />
        <div class="report-meta">
          <span>{{ t('aiReport.generatedAt', { time: formatDate(reportGeneratedAt) }) }}</span>
          <span v-if="hasMarkdownPreview" class="markdown-link" role="button" tabindex="0" @click="loadMarkdownPreview" @keydown.enter="loadMarkdownPreview" @keydown.space.prevent="loadMarkdownPreview">
            <van-icon name="description" /> {{ t('aiReport.viewMarkdown') }}
          </span>
          <span v-if="currentReport.data_completeness_score != null">
            {{ t('aiReport.dataCompleteness', { score: currentReport.data_completeness_score.toFixed(0) }) }}
          </span>
        </div>
        <div class="report-actions">
          <van-button
            size="small"
            plain
            type="primary"
            :loading="isExportingImage"
            @click="onExportImage"
          >
            <van-icon name="photo-o" />
            {{ t('aiReport.exportImage') }}
          </van-button>
          <van-button
            size="small"
            plain
            type="primary"
            :loading="isExportingPdf"
            @click="onExportPdf"
          >
            <van-icon name="description" />
            {{ t('aiReport.exportPdf') }}
          </van-button>
        </div>
      </div>

      <!-- New format: Indicators array (dynamic rendering) -->
      <template v-if="hasIndicatorsFormat">
        <div class="indicators-section">
          <div v-for="indicator in renderedIndicators" :id="`indicator-${indicator.key}`" :key="indicator.key" class="indicator-card">
            <!-- Header with icon + label + score -->
            <div class="indicator-header">
              <van-icon :name="indicator.icon" class="indicator-icon" />
              <span class="indicator-label">{{ indicator.label }}</span>
              <div class="indicator-score">
                <span :class="indicator.scoreClass">{{ indicator.score }}/5</span>
              </div>
            </div>
            <!-- Narrative markdown -->
            <!-- eslint-disable vue/no-v-html -->
            <div class="indicator-narrative" v-html="indicator.narrativeHtml" />
            <!-- Suggestions list -->
            <div v-if="indicator.suggestions?.length" class="indicator-suggestions">
              <div class="suggestions-title">{{ t('aiReport.suggestions') }}</div>
              <div v-for="(s, idx) in indicator.suggestions" :key="idx" class="suggestion-item">
                <van-icon name="info-o" /> {{ s }}
              </div>
            </div>
            <!-- Dynamic data visualization: only render when there is actual content
                 (new-format items array or legacy non-empty flat key-value data).
                 Prevents a bare "Items" label from showing when data.items is empty. -->
            <div v-if="hasIndicatorData(indicator)" class="indicator-data">
              <!-- New format: items array with bilingual labels -->
              <template v-if="getIndicatorDataItems(indicator)">
                <div v-for="item in getIndicatorDataItems(indicator)!" :key="item.key" class="data-row">
                  <span>{{ item.zh === item.en ? item.zh : (locale === 'en-US' ? item.en : item.zh) }}</span>
                  <span v-if="typeof item.value === 'number'">{{ formatValue(item.key, item.value) }}</span>
                  <span v-else>{{ item.value }}</span>
                </div>
              </template>
              <!-- Legacy fallback: flat key-value object -->
              <template v-else>
                <div v-for="(value, key) in indicator.data" :key="key" class="data-row">
                  <span>{{ getDataLabel(String(key)) }}</span>
                  <!-- Array value: render each element as a sub-row -->
                  <template v-if="Array.isArray(value)">
                    <div v-for="(item, itemIdx) in (value as unknown[])" :key="itemIdx" class="data-sub-row">
                      <span v-if="typeof item === 'object' && item !== null">{{ Array.isArray(item) ? item.join(', ') : Object.entries(item as Record<string, unknown>).map(([k, v]) => `${getDataLabel(k)}: ${typeof v === 'number' ? formatValue(k, v) : String(v)}`).join(', ') }}</span>
                      <span v-else>{{ typeof item === 'number' ? formatValue(String(key), item) : String(item) }}</span>
                    </div>
                  </template>
                  <template v-else>
                    <span v-if="typeof value === 'number'">{{ formatValue(String(key), value) }}</span>
                    <span v-else>{{ String(value) }}</span>
                  </template>
                </div>
              </template>
            </div>
          </div>
        </div>
      </template>

      <!-- Regenerate -->
      <div class="regen-section">
        <van-button plain block :loading="isGenerating" @click="onGenerate(true)">
          {{ t('aiTask.regenBtn') }}
        </van-button>
      </div>
      </div>
    </template>

    <!-- Markdown preview popup -->
    <ReportMarkdownPreview
      v-model:visible="markdownVisible"
      :content="markdownContent"
      :filename="markdownFilename"
      :file-size="markdownFileSize"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, showSuccessToast, showFailToast, showLoadingToast, closeToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { marked } from 'marked'
import { parseApiDate } from '@/utils/format'
import { useAIStore } from '@/stores/ai'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'
import { getAIReport, getAIReportMarkdown, getAITask } from '@/api/ai'
import { cancelTaskById } from '@/api/ai-tasks'
import type { AIReport, AIReportIndicator } from '@/types'
import { useReportStream } from '@/composables/useReportStream'
import { useTaskResume } from '@/composables/useTaskResume'
import { generateReportImage, generateReportPdf, downloadImage, downloadBlob, reportImageFilename, reportPdfFilename } from '@/utils/reportImage'
import { sanitizeMarkdown } from '@/utils/sanitize'
import { getIndicatorLabel } from '@/utils/report'
import PageHeader from '@/components/common/PageHeader.vue'
import ReportStepTimeline from '@/components/ai/ReportStepTimeline.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ReportMarkdownPreview from '@/components/ai/ReportMarkdownPreview.vue'

const { t, locale } = useI18n()
const { formatIn } = useCurrency()

const aiStore = useAIStore()
const familyStore = useFamilyStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const currentReport = ref<AIReport | null>(null)
const reportGeneratedAt = ref<string | null>(null)
const retryTimer = ref<ReturnType<typeof setTimeout> | null>(null)

// Report content root for image export
const reportContentRef = ref<HTMLElement | null>(null)
const isExportingImage = ref(false)
const isExportingPdf = ref(false)
const reportTaskId = ref<string | null>(null)
const cancelling = ref(false)

// Markdown preview state
const markdownVisible = ref(false)
const markdownContent = ref('')
const markdownFilename = ref('')
const markdownFileSize = ref(0)

// Indicator icon mapping
const INDICATOR_ICON_MAP: Record<string, string> = {
  net_worth_health: 'balance-o',
  allocation_analysis: 'bar-chart-o',
  liability_pressure: 'bill-o',
  asset_efficiency: 'chart-trending-o',
  liquidity_analysis: 'gold-coin-o',
  risk_assessment: 'warning-o',
  growth_potential: 'arrow-up',
  _default: 'records-o',
}

// Score class mapping (1-5 scale)
function getIndicatorIcon(key: string): string {
  return INDICATOR_ICON_MAP[key] || INDICATOR_ICON_MAP._default
}

function getScoreClass(score: number): string {
  if (score >= 5) return 'score-excellent'
  if (score >= 4) return 'score-good'
  if (score >= 3) return 'score-fair'
  if (score >= 2) return 'score-poor'
  return 'score-critical'
}

async function loadExistingReport() {
  try {
    const res = await getAIReport()
    if (res.data.report) {
      currentReport.value = res.data.report
      reportGeneratedAt.value = res.data.generated_at ?? null
    }
  } catch {
    // No report yet or non-critical fetch error — template handles
    // empty state and inline error display. Matches AIHubPage pattern.
  }
}

// Load markdown for elastic fallback when structured conversion failed
async function loadFallbackMarkdown() {
  try {
    const res = await getAIReportMarkdown()
    markdownContent.value = res.data.content
    markdownFilename.value = res.data.filename
    markdownFileSize.value = res.data.file_size
    markdownVisible.value = true
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

async function loadMarkdownPreview() {
  if (!currentReport.value?.markdown_file_path) {
    showFailToast(t('toast.operationFailed'))
    return
  }
  try {
    const res = await getAIReportMarkdown()
    markdownContent.value = res.data.content
    markdownFilename.value = res.data.filename
    markdownFileSize.value = res.data.file_size
    markdownVisible.value = true
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

const stream = useReportStream()

// v3: useTaskResume for SSE reconnection on page re-entry
const resumeHandle = useTaskResume('report', {
  onStreamEvent: (event, data) => {
    stream.ingestEvent(event, data)
  },
  onComplete: async () => {
    aiStore.clearBackgroundTask('report')
    // Stream status was restored from sessionStorage as 'streaming' when
    // the user re-entered the page. If resume() found the task already
    // completed, the stream will never receive an end event to transition
    // to 'completed' — manually set it and clear persisted state so the
    // timeline doesn't stay stuck on stale step-progress.
    if (stream.status.value !== 'completed' && stream.status.value !== 'error') {
      stream.status.value = 'completed'
      // SSE end frame never arrived (network close, etc.) so handleEnd()
      // never ran. The backend confirmed success, so all steps finished:
      // mark them explicitly so the timeline reflects reality.
      stream.step1Status.value = 'finish'
      stream.step2Status.value = 'finish'
      stream.step3Status.value = 'finish'
      // Clear sessionStorage so next generation starts with a clean slate.
      // We can't call stream.reset() here because it would wipe the loaded
      // report and step state that the template is currently rendering.
      try { sessionStorage.removeItem('numina:report-stream-state') } catch { /* noop */ }
    }
    await loadExistingReport()
  },
  onError: () => {
    aiStore.clearBackgroundTask('report')
  },
})

// Whether a generation is in flight (streaming or connecting).
const isGenerating = computed(() =>
  stream.status.value === 'connecting' || stream.status.value === 'streaming',
)

// Elastic fallback: step1 markdown 落盘 succeeded (write_file tool_result
// arrived) even if step2/3 later failed — the markdown file exists on disk
// and can be viewed via getAIReportMarkdown().
const hasMarkdownFallback = computed(() =>
  stream.step1Status.value === 'finish' &&
  stream.toolResults.value.some((r) => r.tool_name.includes('write_file')),
)

// Detect which format the report uses
const hasIndicatorsFormat = computed(() => {
  if (!currentReport.value) return false
  // New format has indicators array
  return currentReport.value.indicators != null && currentReport.value.indicators.length > 0
})

// Render indicators with markdown narrative
const renderedIndicators = computed(() => {
  if (!currentReport.value?.indicators) return []
  return currentReport.value.indicators.map((indicator: AIReportIndicator) => ({
    ...indicator,
    label: getIndicatorLabel(indicator.key, t),
    icon: getIndicatorIcon(indicator.key),
    scoreClass: getScoreClass(indicator.score),
    narrativeHtml: sanitizeMarkdown(marked.parse(indicator.narrative, { async: false }) as string),
  }))
})

// Check if markdown preview is available
const hasMarkdownPreview = computed(() => {
  return currentReport.value?.markdown_file_path != null
})

const scoreProgress = computed(() => {
  const score = currentReport.value?.overall_score ?? 0
  // Circle circumference is 2πr = 2 * π * 54 ≈ 339, but we use 324 for smooth animation
  return (score / 100) * 324
})

const renderedSummary = computed(() => {
  if (!currentReport.value?.summary) return ''
  const raw = marked.parse(currentReport.value.summary, { async: false }) as string
  return sanitizeMarkdown(raw)
})

function formatMoney(val: number | null | undefined): string {
  if (val == null) return '-'
  const currency = authStore.user?.default_currency || 'CNY'
  return formatIn(val, currency)
}

function formatValue(key: string, val: number): string {
  // Format based on key hints
  if (key.includes('pct') || key.includes('ratio') || key.includes('percent')) {
    return `${val.toFixed(1)}%`
  }
  if (key.includes('count') || key.includes('number')) {
    return String(val)
  }
  if (key.includes('amount') || key.includes('cost') || key.includes('worth')) {
    return formatMoney(val)
  }
  // Default: format with reasonable precision
  return val >= 1000 ? val.toFixed(0) : val.toFixed(2)
}

// Map LLM-emitted snake_case data keys to localized labels. Unknown keys fall
// back to a humanized form (e.g. "mom_change_pct" → "Mom change pct") instead
// of rendering the raw identifier to the user.
const DATA_LABEL_KEYS = new Set([
  'total_assets', 'total_liabilities', 'net_worth', 'mom_change_pct',
  'liability_ratio', 'count', 'low_usage_count', 'total_daily_cost',
  'real_net_worth',
  // Liability-related
  'mortgage_amount', 'consumer_loan_amount', 'credit_card_debt',
  'monthly_payment', 'interest_rate', 'remaining_term_months',
  'debt_to_income_ratio', 'credit_utilization_ratio',
  // Asset category names (when used as flat key-value pair)
  'real_estate', 'cash', 'liquid_assets', 'financial_assets',
  'investments', 'crypto', 'insurance', 'consumer_goods',
  // Growth / liquidity
  'asset_growth_rate', 'income_growth_rate', 'liquid_asset_ratio',
  'financial_asset_ratio', 'real_estate_concentration',
  'emergency_months', 'liquidity_ratio', 'monthly_expense',
  // Risk / diversification
  'concentration_ratio', 'diversification_score', 'insurance_coverage',
  'insurance_coverage_ratio', 'monthly_payment_ratio',
  'low_yield_asset_ratio', 'non_productive_asset_ratio',
])

function getDataLabel(key: string): string {
  if (DATA_LABEL_KEYS.has(key)) {
    return t(`aiReport.dataLabel_${key}`)
  }
  // Unknown keys: humanize for English locale, keep raw for non-English
  if (locale.value === 'en-US') {
    return key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
  }
  return key
}

/** Extract bilingual data items from indicator.data (new SKILL.md v2 format).
 * Returns null when the data uses the legacy flat key-value format. */
function getIndicatorDataItems(indicator: AIReportIndicator): Array<{ key: string; zh: string; en: string; value: number }> | null {
  const items = indicator.data?.items
  if (!items || !Array.isArray(items)) return null
  if (items.length === 0) return null

  // Standard bilingual format: { key, zh, en, value }
  const first = items[0]
  if (typeof first === 'object' && first !== null && 'zh' in first && 'en' in first) {
    return items as Array<{ key: string; zh: string; en: string; value: number }>
  }

  // Fallback: model emitted { category_name, percentage } or similar flat objects
  // Normalize into bilingual items so the same rendering path works.
  return items.map((item: Record<string, unknown>, idx: number) => {
    const label = String(item.category_name ?? item.name ?? item.label ?? `item_${idx}`)
    return {
      key: String(item.key ?? idx),
      zh: label,
      en: label,
      value: Number(item.percentage ?? item.value ?? item.amount ?? 0),
    }
  })
}

/** Whether an indicator has renderable data. Returns false when data is empty
 *  or only contains an empty items array — prevents a bare "Items" label from
 *  showing when the LLM did not generate any data items. */
function hasIndicatorData(indicator: AIReportIndicator): boolean {
  const data = indicator.data
  if (!data || typeof data !== 'object') return false

  // New format: check items array
  const items = data.items
  if (Array.isArray(items) && items.length > 0) return true

  // Legacy flat format: any non-empty key-value pairs (excluding empty items)
  const keys = Object.keys(data).filter((k) => k !== 'items')
  if (keys.length > 0) return true

  return false
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  const loc = locale.value === 'en-US' ? 'en-US' : 'zh-CN'
  return parseApiDate(iso).toLocaleString(loc, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/**
 * Wait for the server-side report task to reach a terminal state.
 *
 * After the SSE stream ends, the lifecycle consumer still needs to verify
 * the task result and mark it complete. Polling the legacy /ai/tasks/report
 * endpoint ensures we load the new report only after it has been committed
 * to the database, preventing a stale-timestamp display.
 */
async function waitForServerTaskComplete(): Promise<void> {
  const MAX_WAIT = 30_000
  const POLL_INTERVAL = 1_500
  const startTime = Date.now()
  // Brief grace period: lifecycle consumer processes the end event
  // ~simultaneously with the frontend; give it a moment to commit.
  await new Promise(r => setTimeout(r, 1000))
  while (Date.now() - startTime < MAX_WAIT) {
    try {
      const task = await getAITask('report')
      if (task.status === 'idle' || task.status === 'completed' ||
          task.status === 'failed' || task.status === 'cancelled' ||
          task.status === 'timeout') {
        return
      }
    } catch {
      // Network error — keep waiting
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL))
  }
}

/**
 * Register the running report task so the cancel button and background-task
 * tracking survive page navigation. Idempotent for the same task_id — safe
 * to call from both onGenerate and onMounted resume paths.
 */
let registeredTaskId: string | null = null
async function registerRunningTask(): Promise<void> {
  // Already tracking this task — skip the redundant API round-trip.
  if (registeredTaskId && reportTaskId.value === registeredTaskId) return
  try {
    const task = await getAITask('report')
    if (task.task_id && ['running', 'queued', 'post_processing'].includes(task.status)) {
      reportTaskId.value = task.task_id
      registeredTaskId = task.task_id
      aiStore.registerBackgroundTask({
        capability: 'report',
        taskId: task.task_id,
        sessionId: task.session_id || '',
        startedAt: task.started_at || new Date().toISOString(),
        status: task.status,
      })
    }
  } catch {
    // best-effort; polling on return will catch up
  }
}

async function onGenerate(force = false) {
  if (!familyStore.aiEnabled) {
    showToast(t('toast.aiNotEnabled'))
    return
  }
  stream.reset()
  // Fix: stop useTaskPolling from polling the stale task ID.
  // Without this, the 2s-interval poll fires GET /detail/{old_id} → 404,
  // and the global axios interceptor shows a "资源不存在" toast before
  // the polling code can silently handle it.
  resumeHandle.taskId.value = null
  // Reset the registration guard so a fresh task can be tracked.
  registeredTaskId = null

  try {
    const connectPromise = stream.connect(force)
    // Register the background task as soon as possible so navigation away
    // does not lose track of the running run.
    await registerRunningTask()
    if (!reportTaskId.value) {
      // Task may not exist yet (backend race) — retry after a short delay.
      setTimeout(registerRunningTask, 500)
    }
    const started = await connectPromise
    if (!started) {
      showToast({ message: t('aiReport.alreadyGenerating'), icon: 'warning-o' })
      return
    }
    // Cache hit → stream.report holds the cached report.
    if (stream.cached.value && stream.report.value) {
      currentReport.value = stream.report.value as unknown as AIReport
      reportGeneratedAt.value = stream.generatedAt.value
    } else if (stream.status.value === 'completed') {
      // Fresh generation SSE finished. The agent writes the report to DB
      // before the stream ends, but the lifecycle consumer may still be
      // verifying/committing the task result. Poll the legacy endpoint
      // until the task reaches a terminal state to ensure the report is
      // persisted before reloading.
      await waitForServerTaskComplete()
      await loadExistingReport()
    } else if (stream.status.value === 'error') {
      // Generation failed — clear the stale report so the user sees the
      // error state instead of the previous report with an old date.
      currentReport.value = null
      reportGeneratedAt.value = null
    }
    aiStore.clearBackgroundTask('report')
    reportTaskId.value = null
  } catch {
    // Network or connection error — clear stale report so the error state
    // is visible rather than the previous report pretending nothing happened.
    currentReport.value = null
    reportGeneratedAt.value = null
    showFailToast(stream.errorMessage.value || t('toast.aiGenerateFailed'))
  }
}

async function onCancel() {
  if (!reportTaskId.value || cancelling.value) return
  cancelling.value = true
  try {
    await cancelTaskById(reportTaskId.value)
    // Stop the frontend SSE reader (keepRunning=false resets status).
    stream.abort(false)
    aiStore.clearBackgroundTask('report')
    reportTaskId.value = null
    showToast(t('aiTask.cancelled'))
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    cancelling.value = false
  }
}

async function onExportImage() {
  if (!reportContentRef.value) {
    showFailToast(t('aiReport.exportImageFail'))
    return
  }
  isExportingImage.value = true
  showLoadingToast({ message: t('aiReport.exportingImage'), forbidClick: true, duration: 0 })
  try {
    const blob = await generateReportImage(reportContentRef.value)
    closeToast()
    downloadImage(blob, reportImageFilename())
    showSuccessToast(t('aiReport.exportImageSuccess'))
  } catch {
    closeToast()
    showFailToast(t('aiReport.exportImageFail'))
  } finally {
    isExportingImage.value = false
  }
}

async function onExportPdf() {
  if (!reportContentRef.value) {
    showFailToast(t('aiReport.exportPdfFail'))
    return
  }
  isExportingPdf.value = true
  showLoadingToast({ message: t('aiReport.exportingPdf'), forbidClick: true, duration: 0 })
  try {
    const blob = await generateReportPdf(reportContentRef.value)
    closeToast()
    downloadBlob(blob, reportPdfFilename())
    showSuccessToast(t('aiReport.exportPdfSuccess'))
  } catch {
    closeToast()
    showFailToast(t('aiReport.exportPdfFail'))
  } finally {
    isExportingPdf.value = false
  }
}

onMounted(async () => {
  await loadExistingReport()

  // v3: useTaskResume handles running task detection + SSE reconnection
  let resumed = await resumeHandle.resume()
  if (resumed && resumeHandle.task.value) {
    // Set reportTaskId so the cancel button appears (U21).
    // resume() already fetched the task via getAITasks — no need for a
    // redundant API call; just mirror the ID and register the background task.
    reportTaskId.value = resumeHandle.taskId.value
    registeredTaskId = resumeHandle.taskId.value
    stream.markReconnecting()
    aiStore.registerBackgroundTask({
      capability: 'report',
      taskId: resumeHandle.taskId.value!,
      sessionId: resumeHandle.task.value.session_id || '',
      startedAt: resumeHandle.task.value.started_at || new Date().toISOString(),
      status: resumeHandle.task.value.status,
    })
  }

  // Fallback: resume() may have failed (API error, task not yet visible) but
  // the stream was restored from sessionStorage as 'streaming'. Use
  // retryTrigger() which finds the running task AND starts SSE reconnection
  // so steps advance and the cancel button appears.
  if (!resumed && isGenerating.value) {
    const reconnected = await resumeHandle.retryTrigger()
    if (reconnected && resumeHandle.taskId.value && resumeHandle.task.value) {
      reportTaskId.value = resumeHandle.taskId.value
      registeredTaskId = resumeHandle.taskId.value
      stream.markReconnecting()
      aiStore.registerBackgroundTask({
        capability: 'report',
        taskId: resumeHandle.taskId.value,
        sessionId: resumeHandle.task.value.session_id || '',
        startedAt: resumeHandle.task.value.started_at || new Date().toISOString(),
        status: resumeHandle.task.value.status,
      })
    } else {
      // No running task found — generation likely completed or failed while
      // the user was away. Clear stale stream state so the UI doesn't show
      // a frozen "generating" timeline.
      stream.reset()
    }
  }

  // Retry check for previously failed tasks (agent pipeline may still be running)
  if (!currentReport.value && resumeHandle.task.value?.status === 'failed') {
    retryTimer.value = setTimeout(async () => {
      try {
        await loadExistingReport()
      } catch {
        // best-effort; page already shows empty state
      }
    }, 3000)
  }

  // Handle ?regen=1 — auto-trigger regeneration (from AI Hub refresh button)
  if (route.query.regen === '1' && familyStore.aiEnabled) {
    // Clear the query param so a page refresh doesn't re-trigger
    router.replace({ path: '/ai/report' })
    // Wait for DOM to settle, then trigger regeneration
    await nextTick()
    onGenerate(true).catch(() => {
      // onGenerate already shows toast internally; this is a safety net
      // for errors thrown before entering its try block (e.g. stream.reset).
    })
  }

  // Handle hash scroll to indicator section (from AI Hub popover link)
  const hash = route.hash
  if (hash && hash.startsWith('#indicator-')) {
    await nextTick()
    // Wait for report content to render
    await nextTick()
    const el = document.getElementById(hash.slice(1))
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }
})

onUnmounted(() => {
  // Close the frontend SSE reader but keep the agent pipeline running in the
  // background. The user can leave the page and the task will still complete.
  stream.abort(true)
  // v3 fix: use disconnect() (not cleanup()) to preserve step-state so that
  // resume() can restore the timeline when the user navigates back.
  resumeHandle.disconnect()
  // Clear the retry timer to prevent state updates on unmounted component
  if (retryTimer.value) {
    clearTimeout(retryTimer.value)
  }
})
</script>

<style scoped>
.ai-report-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
.console-wrap {
  padding: 0 16px;
}
.empty-state {
  padding: 40px 16px;
}
.empty-actions {
  padding: 0 16px;
}
.empty-tip {
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
}
.overall-section {
  background: var(--bg-primary);
  margin: 12px 16px;
  border-radius: 16px;
  padding: 20px;
  text-align: center;
}
.overall-score-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 12px;
}
.overall-score-circle {
  position: relative;
  width: 120px;
  height: 120px;
  margin-bottom: 8px;
}
.score-ring-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.score-ring-bg {
  stroke: var(--bg-secondary);
  stroke-width: 8;
}
.score-ring-fill {
  stroke-width: 8;
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease;
}
.score-ring-fill { stroke: var(--van-primary-color); }
.score-inner {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.score-number {
  font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.5px;
}
.score-number { color: var(--van-primary-color); }
.score-unit {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: -2px;
}
.overall-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.overall-summary {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  text-align: left;
  margin: 0 0 10px;
  :deep(p) {
    margin: 0 0 6px;
    &:last-child { margin-bottom: 0; }
  }
  :deep(strong) {
    font-weight: 600;
  }
  :deep(ol),
  :deep(ul) {
    margin: 4px 0;
    padding-left: 18px;
  }
  :deep(li) {
    margin: 2px 0;
  }
}
.report-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}
.report-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
}
.cards-section {
  padding: 0 16px;
}
.card-data {
  margin-top: 10px;
  border-top: 1px solid var(--separator);
  padding-top: 8px;
}
.data-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 3px 0;
}
.data-sub-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
  padding: 1px 0 1px 12px;
  opacity: 0.85;
}
.positive { color: #f44336; }
.negative { color: #4caf50; }
.alloc-bars {
  margin-top: 10px;
  border-top: 1px solid var(--separator);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.alloc-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.alloc-name {
  width: 60px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.alloc-bar-bg {
  flex: 1;
  height: 6px;
  background: var(--bg-secondary);
  border-radius: 3px;
  overflow: hidden;
}
.alloc-bar-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 3px;
  transition: width 0.4s ease;
}
.alloc-pct {
  width: 40px;
  text-align: right;
  color: var(--text-secondary);
}
.regen-section {
  padding: 16px;
}
.generating-placeholder,
.failed-placeholder {
  padding: 40px 16px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.generating-icon {
  --icon-size: 32px;
}
.failed-icon {
  color: #dc2626;
}
[data-theme='dark'] .failed-icon {
  color: #f87171;
}
.generating-text {
  font-size: 14px;
  margin: 0;
  color: transparent;
  background: linear-gradient(
    90deg,
    var(--text-secondary) 0%,
    var(--van-primary-color) 50%,
    var(--text-secondary) 100%
  );
  background-clip: text;
  -webkit-background-clip: text;
  background-size: 200% 100%;
  animation: shimmer 2s ease-in-out infinite;
}
.failed-text {
  font-size: 14px;
  margin: 0;
  color: #dc2626;
  line-height: 1.5;
}
[data-theme='dark'] .failed-text {
  color: #f87171;
}

@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  50% {
    background-position: 0 0;
  }
  100% {
    background-position: 100% 0;
  }
}

[data-theme='dark'] .generating-text {
  background: linear-gradient(
    90deg,
    var(--text-secondary) 0%,
    var(--color-coral) 50%,
    var(--text-secondary) 100%
  );
  background-clip: text;
  -webkit-background-clip: text;
  background-size: 200% 100%;
}
.narrative-section {
  background: var(--bg-primary);
  margin: 12px 16px;
  border-radius: 16px;
  padding: 20px;
}
.narrative-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.7;
  :deep(p) {
    margin: 0 0 10px;
    &:last-child { margin-bottom: 0; }
  }
  :deep(strong) {
    font-weight: 600;
  }
  :deep(h1), :deep(h2), :deep(h3) {
    margin: 16px 0 8px;
    font-weight: 600;
    color: var(--text-primary);
  }
  :deep(h1) { font-size: 18px; }
  :deep(h2) { font-size: 16px; }
  :deep(h3) { font-size: 15px; }
  :deep(ol), :deep(ul) {
    margin: 8px 0;
    padding-left: 20px;
  }
  :deep(li) {
    margin: 4px 0;
  }
  :deep(code) {
    background: var(--bg-secondary);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
  }
}
.sections-container {
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-card {
  background: var(--bg-primary);
  border-radius: 16px;
  overflow: hidden;
}
.section-header {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-secondary);
}
.section-content {
  padding: 16px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  :deep(p) {
    margin: 0 0 6px;
    &:last-child { margin-bottom: 0; }
  }
  :deep(ol), :deep(ul) {
    margin: 4px 0;
    padding-left: 18px;
  }
  :deep(li) {
    margin: 2px 0;
  }
}
/* Markdown preview link */
.markdown-link {
  color: var(--color-primary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
[data-theme='dark'] .markdown-link {
  color: var(--color-coral);
}
/* Indicators section */
.indicators-section {
  padding: 0 16px;
}
.indicator-card {
  background: var(--bg-primary);
  margin-bottom: 12px;
  border-radius: 16px;
  padding: 16px;
  scroll-margin-top: 16px;
}
.indicator-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.indicator-icon {
  font-size: 20px;
  color: var(--color-primary);
}
[data-theme='dark'] .indicator-icon {
  color: var(--color-coral);
}
.indicator-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.indicator-score {
  margin-left: auto;
  font-size: 14px;
  font-weight: 600;
}
.indicator-score .score-excellent { color: #2e7d32; }
.indicator-score .score-good      { color: var(--color-primary); }
.indicator-score .score-fair      { color: #f57f17; }
.indicator-score .score-poor      { color: #d32f2f; }
.indicator-score .score-critical  { color: #b71c1c; }
[data-theme='dark'] .indicator-score .score-excellent { color: #81c784; }
[data-theme='dark'] .indicator-score .score-good      { color: var(--color-coral); }
[data-theme='dark'] .indicator-score .score-fair      { color: #ffd54f; }
[data-theme='dark'] .indicator-score .score-poor      { color: #f87171; }
[data-theme='dark'] .indicator-score .score-critical  { color: #ef5350; }
.indicator-narrative {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  :deep(p) {
    margin: 0 0 6px;
    &:last-child { margin-bottom: 0; }
  }
  :deep(strong) {
    font-weight: 600;
  }
  :deep(ol), :deep(ul) {
    margin: 6px 0;
    padding-left: 18px;
  }
  :deep(li) {
    margin: 3px 0;
  }
}
.indicator-suggestions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--separator);
}
.suggestions-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.indicator-data {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--separator);
}
/* Previous report banner while generating */
.previous-report-banner {
  padding: 0 16px;
  margin-top: 12px;
}
.previous-report-banner :deep(.van-notice-bar) {
  border-radius: 8px;
  font-size: 13px;
}
/* Report content container */
.previous-report-content {
  margin-top: 12px;
}
/* Cancel button row when generating (U21) */
.report-cancel-row {
  display: flex;
  justify-content: center;
  padding: 8px 16px;
}
</style>
