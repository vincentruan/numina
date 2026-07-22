<template>
  <div class="ai-report-page">
    <PageHeader :title="t('aiReport.title')" />

    <!-- Three-step timeline (shown when streaming or cache hit) -->
    <ReportStepTimeline
      v-if="isGenerating || stream.cached.value || stream.status.value === 'completed'"
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

    <!-- Failed state (show regardless of whether there's an existing report) -->
    <div v-if="stream.status.value === 'error'" class="failed-placeholder">
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
      <van-button plain size="small" :loading="false" @click="onGenerate()" style="margin-top: 8px">
        {{ t('aiTask.retryBtn') }}
      </van-button>
    </div>

    <!-- No report yet (only show when not failed/generating) -->
    <div v-else-if="!currentReport && !isGenerating" class="empty-state">
      <EmptyState image="search" :description="t('aiReport.noReport')" />
      <div class="empty-actions">
        <van-button type="primary" block :loading="isGenerating" @click="onGenerate()">
          {{ t('aiTask.startBtn') }}
        </van-button>
        <p class="empty-tip">{{ t('aiReport.startAnalyze') }}</p>
      </div>
    </div>

    <!-- Report content (show when report exists and not generating) -->
    <template v-else-if="currentReport && !isGenerating">
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
                :class="overallScoreClass"
                :stroke-dasharray="`${scoreProgress} ${324 - scoreProgress}`"
                stroke-dashoffset="81"
              />
            </svg>
            <div class="score-inner">
              <span class="score-number" :class="overallScoreClass">{{ currentReport.overall_score ?? 0 }}</span>
              <span class="score-unit">{{ t('aiReport.scoreUnit') }}</span>
            </div>
          </div>
          <div class="overall-label">{{ t('aiReport.overallScore') }}</div>
        </div>
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
      </div>

      <!-- New format: Indicators array (dynamic rendering) -->
      <template v-if="hasIndicatorsFormat">
        <div class="indicators-section">
          <div v-for="indicator in renderedIndicators" :key="indicator.key" class="indicator-card">
            <!-- Header with icon + label + score -->
            <div class="indicator-header">
              <van-icon :name="indicator.icon" class="indicator-icon" />
              <span class="indicator-label">{{ indicator.label }}</span>
              <div class="indicator-score">
                <span :class="indicator.scoreClass">{{ indicator.score }}/5</span>
              </div>
            </div>
            <!-- Narrative markdown -->
            <div class="indicator-narrative" v-html="indicator.narrativeHtml" />
            <!-- Suggestions list -->
            <div v-if="indicator.suggestions?.length" class="indicator-suggestions">
              <div class="suggestions-title">{{ t('aiReport.suggestions') }}</div>
              <div v-for="(s, idx) in indicator.suggestions" :key="idx" class="suggestion-item">
                <van-icon name="info-o" /> {{ s }}
              </div>
            </div>
            <!-- Dynamic data visualization -->
            <div v-if="indicator.data && Object.keys(indicator.data).length > 0" class="indicator-data">
              <!-- Allocation items -->
              <div v-if="indicator.data.items && Array.isArray(indicator.data.items)" class="alloc-bars">
                <div v-for="item in indicator.data.items" :key="item.category_name" class="alloc-bar-row">
                  <span class="alloc-name">{{ item.category_name }}</span>
                  <div class="alloc-bar-bg">
                    <div class="alloc-bar-fill" :style="{ width: `${item.percentage}%` }" />
                  </div>
                  <span class="alloc-pct">{{ item.percentage.toFixed(1) }}%</span>
                </div>
              </div>
              <!-- Generic data rows -->
              <template v-else>
                <div v-for="(value, key) in indicator.data" :key="key" class="data-row">
                  <span>{{ key }}</span>
                  <span v-if="typeof value === 'number'">{{ formatValue(key, value) }}</span>
                  <span v-else>{{ value }}</span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </template>

      <!-- Regenerate -->
      <div class="regen-section">
        <van-button plain block :loading="isGenerating" @click="onGenerate()">
          {{ t('aiTask.regenBtn') }}
        </van-button>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { showToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useAIStore } from '@/stores/ai'
import { getAIReport, getAIReportMarkdown } from '@/api/ai'
import type { AIReport, AIReportIndicator } from '@/types'
import { useReportStream } from '@/composables/useReportStream'
import PageHeader from '@/components/common/PageHeader.vue'
import ReportStepTimeline from '@/components/ai/ReportStepTimeline.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import ReportMarkdownPreview from '@/components/ai/ReportMarkdownPreview.vue'

const SUMMARY_PURIFY_CONFIG = {
  USE_PROFILES: { html: true },
  ALLOW_DATA_ATTR: false,
} as const

const { t } = useI18n()

const aiStore = useAIStore()

const currentReport = ref<AIReport | null>(null)
const reportGeneratedAt = ref<string | null>(null)

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
    showFailToast(t('toast.operationFailed'))
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
    icon: getIndicatorIcon(indicator.key),
    scoreClass: getScoreClass(indicator.score),
    narrativeHtml: DOMPurify.sanitize(marked.parse(indicator.narrative, { async: false }) as string, SUMMARY_PURIFY_CONFIG),
  }))
})

// Check if markdown preview is available
const hasMarkdownPreview = computed(() => {
  return currentReport.value?.markdown_file_path != null
})

const overallScoreClass = computed(() => {
  const s = currentReport.value?.overall_score ?? 0
  if (s >= 80) return 'score-excellent'
  if (s >= 60) return 'score-good'
  if (s >= 40) return 'score-fair'
  return 'score-poor'
})

const scoreProgress = computed(() => {
  const score = currentReport.value?.overall_score ?? 0
  // Circle circumference is 2πr = 2 * π * 54 ≈ 339, but we use 324 for smooth animation
  return (score / 100) * 324
})

const renderedSummary = computed(() => {
  if (!currentReport.value?.summary) return ''
  const raw = marked.parse(currentReport.value.summary, { async: false }) as string
  return DOMPurify.sanitize(raw, SUMMARY_PURIFY_CONFIG)
})

function formatMoney(val: number | null | undefined): string {
  if (val == null) return '-'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(val)
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

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function onGenerate(force = false) {
  if (!aiStore.config?.ai_enabled) {
    showToast(t('toast.aiNotEnabled'))
    return
  }
  stream.reset()
  try {
    await stream.connect(force)
    // Cache hit → stream.report holds the cached report.
    if (stream.cached.value && stream.report.value) {
      currentReport.value = stream.report.value as unknown as AIReport
      reportGeneratedAt.value = stream.generatedAt.value
    } else if (stream.status.value === 'completed') {
      // Fresh generation finished → reload the persisted report (step 7 落库).
      await loadExistingReport()
    }
    aiStore.clearBackgroundTask('report')
  } catch {
    showFailToast(stream.errorMessage.value || t('toast.aiGenerateFailed'))
  }
}

onMounted(async () => {
  await aiStore.fetchConfig()
  await loadExistingReport()
})

onUnmounted(() => {
  // Abort any in-flight stream when leaving the page.
  stream.abort()
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
.score-ring-fill.score-excellent { stroke: #2e7d32; }
.score-ring-fill.score-good      { stroke: var(--color-primary); }
.score-ring-fill.score-fair      { stroke: #f57f17; }
.score-ring-fill.score-poor      { stroke: #dc2626; }
[data-theme='dark'] .score-ring-fill.score-excellent { stroke: #81c784; }
[data-theme='dark'] .score-ring-fill.score-good      { stroke: var(--color-coral); }
[data-theme='dark'] .score-ring-fill.score-fair      { stroke: #ffd54f; }
[data-theme='dark'] .score-ring-fill.score-poor      { stroke: #f87171; }
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
.score-number.score-excellent { color: #2e7d32; }
.score-number.score-good      { color: var(--color-primary); }
.score-number.score-fair      { color: #f57f17; }
.score-number.score-poor      { color: #dc2626; }
[data-theme='dark'] .score-number.score-excellent { color: #81c784; }
[data-theme='dark'] .score-number.score-good      { color: var(--color-coral); }
[data-theme='dark'] .score-number.score-fair      { color: #ffd54f; }
[data-theme='dark'] .score-number.score-poor      { color: #f87171; }
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
</style>
