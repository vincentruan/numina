<template>
  <div class="data-stats-page">
    <van-nav-bar title="数据统计" />

    <!-- Summary Cards -->
    <div class="summary-section">
      <div class="summary-card">
        <div class="summary-label">总资产</div>
        <div class="summary-value primary">¥{{ formatMoney(overview?.total_assets) }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">总负债</div>
        <div class="summary-value danger">¥{{ formatMoney(overview?.total_liabilities) }}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">净资产</div>
        <div class="summary-value success">¥{{ formatMoney(overview?.net_worth) }}</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="charts-section">
      <div class="chart-card">
        <div class="chart-title">资产趋势</div>
        <TrendLineChart v-if="trend.length" :data="trend" />
        <van-empty v-else description="暂无数据" />
      </div>

      <div class="chart-card">
        <div class="chart-title">资产分布</div>
        <AllocationPieChart v-if="allocation.length" :data="allocation" />
        <van-empty v-else description="暂无数据" />
      </div>
    </div>

    <!-- Quick Stats -->
    <van-cell-group inset title="快速统计">
      <van-cell title="资产数量" :value="`${overview?.asset_count ?? 0} 项`" />
      <van-cell title="本月新增资产" :value="`${recentAssetsCount} 项`" />
      <van-cell title="日均成本总计" :value="`¥${formatMoney(overview?.total_daily_cost)}/天`" />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import TrendLineChart from '@/components/charts/TrendLineChart.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'

const dashboardStore = useDashboardStore()

const overview = computed(() => dashboardStore.overview)
const trend = computed(() => dashboardStore.trend)
const allocation = computed(() => dashboardStore.allocation)

const recentAssetsCount = ref(0)

function formatMoney(value: number | string | undefined | null): string {
  if (value === undefined || value === null) return '0'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '0'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}

onMounted(async () => {
  await dashboardStore.fetchAll()
})
</script>

<style scoped>
.data-stats-page {
  background: #f7f8fa;
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
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.summary-label {
  font-size: 12px;
  color: #969799;
  margin-bottom: 4px;
}

.summary-value {
  font-size: 14px;
  font-weight: 600;
}

.summary-value.primary {
  color: #1989fa;
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
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  color: #323233;
}
</style>