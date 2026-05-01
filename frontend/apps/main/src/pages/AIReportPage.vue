<template>
  <div class="ai-report-page">
    <PageHeader title="家庭资产体检" />

    <!-- Loading / Generating state -->
    <div v-if="ws.status.value === 'connecting' || ws.status.value === 'analyzing'" class="generating-state">
      <van-loading size="40" type="spinner" color="var(--van-primary-color)" />
      <p class="generating-msg">{{ ws.progressMessage.value }}</p>
    </div>

    <!-- Error state -->
    <div v-else-if="ws.status.value === 'error'" class="error-state">
      <van-empty image="error" :description="ws.errorMessage.value || '生成失败，请重试'" />
      <van-button type="primary" block @click="onGenerate">重新生成</van-button>
    </div>

    <!-- No report yet -->
    <div v-else-if="!currentReport" class="empty-state">
      <van-empty image="search" description="暂无体检报告" />
      <div class="empty-actions">
        <van-button type="primary" block :loading="generating" @click="onGenerate">
          立即生成体检报告
        </van-button>
        <p class="empty-tip">AI 将综合分析您的资产配置、负债压力和资产效率</p>
      </div>
    </div>

    <!-- Report content -->
    <template v-else>
      <!-- Overall score -->
      <div class="overall-section">
        <div class="overall-score-wrap">
          <div class="overall-score" :class="overallScoreClass">
            {{ currentReport.overall_score }}
          </div>
          <div class="overall-label">综合健康评分</div>
        </div>
        <p class="overall-summary">{{ currentReport.summary }}</p>
        <div class="report-meta">
          <span>生成时间：{{ formatDate(reportGeneratedAt) }}</span>
          <span v-if="currentReport.data_completeness_score != null">
            数据完整度：{{ currentReport.data_completeness_score.toFixed(0) }}%
          </span>
        </div>
      </div>

      <!-- Report cards -->
      <div class="cards-section">
        <ReportCard
          icon="balance-o"
          title="净资产健康"
          :score="currentReport.net_worth_health?.score ?? 0"
          :narrative="currentReport.net_worth_health?.narrative ?? ''"
        >
          <div v-if="currentReport.net_worth_health?.data" class="card-data">
            <div class="data-row">
              <span>净资产</span>
              <span>{{ formatMoney(currentReport.net_worth_health.data.net_worth) }}</span>
            </div>
            <div class="data-row">
              <span>月环比</span>
              <span :class="currentReport.net_worth_health.data.mom_change_pct >= 0 ? 'positive' : 'negative'">
                {{ currentReport.net_worth_health.data.mom_change_pct >= 0 ? '+' : '' }}{{ currentReport.net_worth_health.data.mom_change_pct?.toFixed(1) }}%
              </span>
            </div>
          </div>
        </ReportCard>

        <ReportCard
          icon="bar-chart-o"
          title="资产配置"
          :score="currentReport.allocation_analysis?.score ?? 0"
          :narrative="currentReport.allocation_analysis?.narrative ?? ''"
        >
          <div v-if="currentReport.allocation_analysis?.data?.items?.length" class="alloc-bars">
            <div
              v-for="item in currentReport.allocation_analysis.data.items"
              :key="item.category_name || item.name"
              class="alloc-bar-row"
            >
              <span class="alloc-name">{{ item.category_name || item.name }}</span>
              <div class="alloc-bar-bg">
                <div class="alloc-bar-fill" :style="{ width: `${item.percentage}%` }" />
              </div>
              <span class="alloc-pct">{{ item.percentage?.toFixed(1) }}%</span>
            </div>
          </div>
        </ReportCard>

        <ReportCard
          icon="bill-o"
          title="负债压力"
          :score="currentReport.liability_pressure?.score ?? 0"
          :narrative="currentReport.liability_pressure?.narrative ?? ''"
        >
          <div v-if="currentReport.liability_pressure?.data" class="card-data">
            <div class="data-row">
              <span>活跃负债</span>
              <span>{{ currentReport.liability_pressure.data.count }} 笔</span>
            </div>
          </div>
        </ReportCard>

        <ReportCard
          icon="chart-trending-o"
          title="资产效率"
          :score="currentReport.asset_efficiency?.score ?? 0"
          :narrative="currentReport.asset_efficiency?.narrative ?? ''"
        >
          <div v-if="currentReport.asset_efficiency?.data" class="card-data">
            <div class="data-row">
              <span>低效资产</span>
              <span>{{ currentReport.asset_efficiency.data.low_usage_count }} 项</span>
            </div>
            <div class="data-row">
              <span>日均成本</span>
              <span>{{ formatMoney(currentReport.asset_efficiency.data.total_daily_cost) }}</span>
            </div>
          </div>
        </ReportCard>
      </div>

      <!-- Regenerate -->
      <div class="regen-section">
        <van-button plain block :loading="generating" @click="onGenerate">重新生成报告</van-button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAIStore } from '@/stores/ai'
import { getAIReport } from '@/api/ai'
import { useAIReportWS } from '@/composables/useAIReportWS'
import PageHeader from '@/components/common/PageHeader.vue'
import ReportCard from '@/components/ai/ReportCard.vue'

const { t } = useI18n()

const aiStore = useAIStore()
const ws = useAIReportWS()

const currentReport = ref<Record<string, any> | null>(null)
const reportGeneratedAt = ref<string | null>(null)
const generating = ref(false)

const overallScoreClass = computed(() => {
  const s = currentReport.value?.overall_score ?? 0
  if (s >= 80) return 'score-excellent'
  if (s >= 60) return 'score-good'
  if (s >= 40) return 'score-fair'
  return 'score-poor'
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
  generating.value = true
  ws.reset()
  try {
    await ws.connect()
    if (ws.report.value) {
      currentReport.value = ws.report.value
      reportGeneratedAt.value = ws.generatedAt.value
    }
  } catch {
    showToast(ws.errorMessage.value || '生成失败，请重试')
  } finally {
    generating.value = false
  }
}

onMounted(async () => {
  await aiStore.fetchConfig()
  await loadExistingReport()
})

onUnmounted(() => {
  ws.disconnect()
})
</script>

<style scoped>
.ai-report-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 24px;
}
.generating-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 24px;
  gap: 16px;
}
.generating-msg {
  color: var(--text-secondary);
  font-size: 14px;
}
.error-state, .empty-state {
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
.overall-score {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 6px;
}
.score-excellent { background: #e8f5e9; color: #2e7d32; }
.score-good      { background: var(--color-soft-stone); color: var(--color-primary); }
.score-fair      { background: #fff8e1; color: #f57f17; }
.score-poor      { background: #fce4ec; color: #c62828; }
[data-theme='dark'] .score-excellent { background: #1b3a1f; color: #81c784; }
[data-theme='dark'] .score-good      { background: #1e1e24; color: var(--color-coral); }
[data-theme='dark'] .score-fair      { background: #2e2200; color: #ffd54f; }
[data-theme='dark'] .score-poor      { background: #3b0a14; color: #ef9a9a; }
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
