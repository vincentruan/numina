<template>
  <div class="ai-report-page">
    <PageHeader :title="t('aiReport.title')" />

    <!-- Task console (streaming progress) -->
    <div class="console-wrap">
      <TaskConsole
        v-model="isConsoleOpen"
        :status="taskStatus"
        :think-content="taskChunks"
        :elapsed-seconds="taskElapsed"
      />
    </div>

    <!-- No report yet -->
    <div v-if="!currentReport" class="empty-state">
      <van-empty image="search" :description="t('aiReport.noReport')" />
      <div class="empty-actions">
        <van-button type="primary" block :loading="taskStatus === 'running'" @click="onGenerate">
          {{ t('aiTask.startBtn') }}
        </van-button>
        <p class="empty-tip">{{ t('aiReport.startAnalyze') }}</p>
      </div>
    </div>

    <!-- Report content -->
    <template v-else-if="currentReport">
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
        <p class="overall-summary">{{ currentReport.summary }}</p>
        <div class="report-meta">
          <span>{{ t('aiReport.generatedAt', { time: formatDate(reportGeneratedAt) }) }}</span>
          <span v-if="currentReport.data_completeness_score != null">
            {{ t('aiReport.dataCompleteness', { score: currentReport.data_completeness_score.toFixed(0) }) }}
          </span>
        </div>
      </div>

      <!-- Report cards -->
      <div class="cards-section">
        <ReportCard
          icon="balance-o"
          :title="t('aiReport.netWorthHealth')"
          :score="currentReport.net_worth_health?.score ?? 0"
          :narrative="currentReport.net_worth_health?.narrative ?? ''"
        >
          <div v-if="currentReport.net_worth_health?.data?.net_worth != null" class="card-data">
            <div class="data-row">
              <span>{{ t('aiReport.netWorthLabel') }}</span>
              <span>{{ formatMoney(currentReport.net_worth_health.data.net_worth) }}</span>
            </div>
            <div v-if="currentReport.net_worth_health.data.mom_change_pct != null" class="data-row">
              <span>{{ t('aiReport.momChange') }}</span>
              <span :class="currentReport.net_worth_health.data.mom_change_pct >= 0 ? 'positive' : 'negative'">
                {{ currentReport.net_worth_health.data.mom_change_pct >= 0 ? '+' : '' }}{{ currentReport.net_worth_health.data.mom_change_pct.toFixed(1) }}%
              </span>
            </div>
          </div>
        </ReportCard>

        <ReportCard
          icon="bar-chart-o"
          :title="t('aiReport.allocationAnalysis')"
          :score="currentReport.allocation_analysis?.score ?? 0"
          :narrative="currentReport.allocation_analysis?.narrative ?? ''"
        >
          <div v-if="currentReport.allocation_analysis?.data?.items?.length" class="alloc-bars">
            <div
              v-for="item in currentReport.allocation_analysis.data.items"
              :key="item.category_id"
              class="alloc-bar-row"
            >
              <span class="alloc-name">{{ item.category_name }}</span>
              <div class="alloc-bar-bg">
                <div class="alloc-bar-fill" :style="{ width: `${item.percentage}%` }" />
              </div>
              <span class="alloc-pct">{{ item.percentage.toFixed(1) }}%</span>
            </div>
          </div>
        </ReportCard>

        <ReportCard
          icon="bill-o"
          :title="t('aiReport.liabilityPressure')"
          :score="currentReport.liability_pressure?.score ?? 0"
          :narrative="currentReport.liability_pressure?.narrative ?? ''"
        >
          <div v-if="currentReport.liability_pressure?.data" class="card-data">
            <div class="data-row">
              <span>{{ t('aiReport.activeLiabilities') }}</span>
              <span>{{ t('aiReport.liabilityCount', { count: currentReport.liability_pressure.data.count }) }}</span>
            </div>
          </div>
        </ReportCard>

        <ReportCard
          icon="chart-trending-o"
          :title="t('aiReport.assetEfficiency')"
          :score="currentReport.asset_efficiency?.score ?? 0"
          :narrative="currentReport.asset_efficiency?.narrative ?? ''"
        >
          <div v-if="currentReport.asset_efficiency?.data" class="card-data">
            <div class="data-row">
              <span>{{ t('aiReport.lowUsageAssets') }}</span>
              <span>{{ t('aiReport.assetCountUnit', { count: currentReport.asset_efficiency.data.low_usage_count }) }}</span>
            </div>
            <div class="data-row">
              <span>{{ t('aiReport.dailyCostLabel') }}</span>
              <span>{{ formatMoney(currentReport.asset_efficiency.data.total_daily_cost) }}</span>
            </div>
          </div>
        </ReportCard>
      </div>

      <!-- Regenerate -->
      <div class="regen-section">
        <van-button plain block :loading="taskStatus === 'running'" @click="onGenerate">
          {{ t('aiTask.regenBtn') }}
        </van-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAIStore } from '@/stores/ai'
import { getAIReport } from '@/api/ai'
import type { AIReport } from '@/types'
import { useAITask } from '@/composables/useAITask'
import PageHeader from '@/components/common/PageHeader.vue'
import ReportCard from '@/components/ai/ReportCard.vue'
import TaskConsole from '@/components/ai/TaskConsole.vue'

const { t } = useI18n()

const aiStore = useAIStore()

const {
  status: taskStatus,
  thinkContent: taskChunks,
  elapsedSeconds: taskElapsed,
  isConsoleOpen,
  startStream,
} = useAITask('report', '/ai/report/generate/events')

const currentReport = ref<AIReport | null>(null)
const reportGeneratedAt = ref<string | null>(null)

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

function formatMoney(val: number | null | undefined): string {
  if (val == null) return '-'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(val)
}

function formatDate(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function loadExistingReport() {
  try {
    const res = await getAIReport()
    if (res.data.report) {
      currentReport.value = res.data.report
      reportGeneratedAt.value = res.data.generated_at ?? null
    }
  } catch {
    // no report yet, that's fine
  }
}

async function onGenerate() {
  if (!aiStore.config?.ai_enabled) {
    showToast(t('toast.aiNotEnabled'))
    return
  }
  await startStream()
  // Reload report data after streaming completes
  await loadExistingReport()
}

onMounted(async () => {
  await aiStore.fetchConfig()
  await loadExistingReport()
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
.score-ring-fill.score-poor      { stroke: #4caf50; }
[data-theme='dark'] .score-ring-fill.score-excellent { stroke: #81c784; }
[data-theme='dark'] .score-ring-fill.score-good      { stroke: var(--color-coral); }
[data-theme='dark'] .score-ring-fill.score-fair      { stroke: #ffd54f; }
[data-theme='dark'] .score-ring-fill.score-poor      { stroke: #81c784; }
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
.score-number.score-poor      { color: #4caf50; }
[data-theme='dark'] .score-number.score-excellent { color: #81c784; }
[data-theme='dark'] .score-number.score-good      { color: var(--color-coral); }
[data-theme='dark'] .score-number.score-fair      { color: #ffd54f; }
[data-theme='dark'] .score-number.score-poor      { color: #81c784; }
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
</style>
