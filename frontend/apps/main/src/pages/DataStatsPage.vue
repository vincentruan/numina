<template>
  <div class="data-stats-page">
    <PageHeader :title="t('dataStats.title')" />

    <!-- Summary Cards -->
    <div class="summary-section">
      <div class="summary-card">
        <div class="summary-label">{{ t('dataStats.totalAssets') }}</div>
        <div class="summary-value primary">{{ formatMoney(overview?.total_assets) }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">{{ t('dataStats.totalLiabilities') }}</div>
        <div class="summary-value danger">{{ formatMoney(overview?.total_liabilities) }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">{{ t('dataStats.netWorth') }}</div>
        <div class="summary-value success">{{ formatMoney(overview?.net_worth) }}</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="charts-section">
      <div class="chart-card">
        <div class="chart-title">{{ t('dataStats.assetTrend') }}</div>
        <TrendLineChart v-if="trend.length" :data="trend" />
        <EmptyState v-else :description="t('dataStats.noData')" />
      </div>

      <div class="chart-card">
        <div class="chart-title">{{ t('dataStats.assetAllocation') }}</div>
        <AllocationPieChart v-if="allocation.length" :data="allocation" />
        <EmptyState v-else :description="t('dataStats.noData')" />
      </div>
    </div>

    <!-- Quick Stats -->
    <van-cell-group inset :title="t('dataStats.quickStats')">
      <van-cell :title="t('dataStats.assetCount')" :value="`${overview?.asset_count ?? 0} 项`" />
      <van-cell :title="t('dataStats.newAssetsThisMonth')" :value="`${recentAssetsCount} 项`" />
      <van-cell :title="t('dataStats.totalDailyCost')" :value="`${formatMoney(overview?.total_daily_cost)}/天`" />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDashboardStore } from '@/stores/dashboard'
import TrendLineChart from '@/components/charts/TrendLineChart.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatCurrency } from '@/utils/format'

const { t } = useI18n()
const dashboardStore = useDashboardStore()

const overview = computed(() => dashboardStore.overview)
const trend = computed(() => dashboardStore.trend)
const allocation = computed(() => dashboardStore.allocation)

const recentAssetsCount = ref(0)

function formatMoney(value: number | string | undefined | null): string {
  if (value === undefined || value === null) return '¥0'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '¥0'
  return formatCurrency(num)
}

onMounted(async () => {
  await dashboardStore.fetchAll()
})
</script>

<style scoped>
.data-stats-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

.summary-section {
  display: flex;
  padding: 12px;
  gap: 8px;
}

.summary-card {
  flex: 1;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.summary-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.summary-value {
  font-size: 14px;
  font-weight: 600;
}

.summary-value.primary {
  color: var(--color-primary);
}

.summary-value.danger {
  color: #ee0a24;
}

.summary-value.success {
  color: #07c160;
}

.charts-section {
  padding: 0 12px;
}

.chart-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

[data-theme='dark'] .chart-card {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-primary);
}
</style>