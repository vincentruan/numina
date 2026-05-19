<template>
  <div class="analytics-page">
    <PageHeader :title="t('analyticsPage.title')" />

    <!-- Card Container -->
    <div class="analytics-detail-cards">
      <!-- Trend Card -->
      <van-cell-group inset class="analytics-detail-card">
        <div class="card-header">
          <span class="card-title">{{ t('analyticsPage.trendCard') }}</span>
          <van-tabs v-model:active="trendPeriod" type="card" shrink @change="onTrendPeriodChange">
            <van-tab title="月" name="month" />
            <van-tab title="季" name="quarter" />
            <van-tab title="年" name="year" />
          </van-tabs>
        </div>
        <div class="card-content">
          <TrendLineChartSimple
            v-if="dashboardStore.trend.length"
            :data="dashboardStore.trend"
          />
          <van-empty v-else :description="t('common.noData')" image-size="60" />
        </div>
      </van-cell-group>

      <!-- Treemap Card -->
      <van-cell-group inset class="analytics-detail-card">
        <div class="card-header">
          <span class="card-title">{{ t('analyticsPage.allocationCard') }}</span>
        </div>
        <div class="card-content">
          <AllocationTreemapChart
            v-if="dashboardStore.allocation.length"
            :data="dashboardStore.allocation"
          />
          <van-empty v-else :description="t('common.noData')" image-size="60" />
        </div>
      </van-cell-group>

      <!-- Pie Card -->
      <van-cell-group inset class="analytics-detail-card">
        <div class="card-header">
          <span class="card-title">{{ t('analyticsPage.pieCard') }}</span>
        </div>
        <div class="card-content pie-content">
          <AllocationPieChart
            v-if="dashboardStore.allocation.length"
            :data="dashboardStore.allocation"
            class="pie-chart-embedded"
          />
          <van-empty v-else :description="t('common.noData')" image-size="60" />
        </div>
      </van-cell-group>

      <!-- Daily Cost Card -->
      <van-cell-group inset class="analytics-detail-card analytics-detail-card--compact">
        <div class="card-header">
          <span class="card-title">{{ t('analyticsPage.dailyCostCard') }}</span>
        </div>
        <div class="card-content">
          <template v-if="dailyCostRanking.length">
            <van-cell
              v-for="item in dailyCostRanking.slice(0, 5)"
              :key="item.id"
              :title="item.name"
              :value="formatMoney(item.daily_cost)"
              :icon="item.icon || 'gold-coin-o'"
              is-link
              @click="router.push(`/assets/${item.id}`)"
            >
              <template v-if="item.category_name" #label>
                <span class="item-category">{{ item.category_name }}</span>
              </template>
            </van-cell>
          </template>
          <van-empty v-else :description="t('common.noData')" image-size="60" />
        </div>
      </van-cell-group>

      <!-- Low Usage Card -->
      <van-cell-group inset class="analytics-detail-card analytics-detail-card--compact">
        <div class="card-header">
          <span class="card-title">{{ t('analyticsPage.lowUsageCard') }}</span>
        </div>
        <div class="card-content">
          <template v-if="lowUsageAssets.length">
            <van-cell
              v-for="item in lowUsageAssets.slice(0, 5)"
              :key="item.id"
              :title="item.name"
              is-link
              @click="router.push(`/assets/${item.id}`)"
            >
              <template #value>
                <van-tag type="warning" size="medium">{{ usageLabel(item.usage_frequency) }}</van-tag>
              </template>
            </van-cell>
          </template>
          <van-empty v-else :description="t('common.noData')" image-size="60" />
        </div>
      </van-cell-group>

      <!-- Net Worth Change Card -->
      <van-cell-group inset class="analytics-detail-card analytics-detail-card--compact">
        <div class="card-header">
          <span class="card-title">{{ t('analyticsPage.netWorthChangeCard') }}</span>
        </div>
        <div class="card-content net-worth-change">
          <div v-if="monthOverMonthChange !== null" class="change-indicator" :class="changeClass">
            <span class="change-arrow">{{ changeArrow }}</span>
            <span class="change-value">{{ Math.abs(monthOverMonthChange).toFixed(1) }}%</span>
            <span class="change-label">{{ changeLabel }}</span>
          </div>
          <van-empty v-else :description="t('analyticsPage.noChange')" image-size="60" />
        </div>
      </van-cell-group>
    </div>

    <div class="bottom-spacer" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import PageHeader from '@/components/common/PageHeader.vue'
import TrendLineChartSimple from '@/components/charts/TrendLineChartSimple.vue'
import AllocationTreemapChart from '@/components/charts/AllocationTreemapChart.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'
import { formatCurrency } from '@/utils/format'

const { t } = useI18n()
const router = useRouter()

const dashboardStore = useDashboardStore()

const trendPeriod = ref<'month' | 'quarter' | 'year'>('month')

const dailyCostRanking = computed(() => dashboardStore.dailyCostRanking)
const lowUsageAssets = computed(
  () => dashboardStore.lowUsageAssets.filter((a) => a.usage_frequency === 'idle'),
)
const monthOverMonthChange = computed(() => dashboardStore.overview?.month_over_month_change ?? null)

function formatMoney(value: number | string | undefined | null): string {
  if (value === undefined || value === null) return '¥0'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '¥0'
  return formatCurrency(num)
}

function usageLabel(frequency: string): string {
  return frequency === 'idle' ? t('statusGrid.idle') : frequency
}

const changeClass = computed(() => {
  const val = monthOverMonthChange.value
  if (val === null) return ''
  return val >= 0 ? 'change-up' : 'change-down'
})

const changeArrow = computed(() => {
  const val = monthOverMonthChange.value
  if (val === null) return ''
  return val >= 0 ? '↑' : '↓'
})

const changeLabel = computed(() => {
  const val = monthOverMonthChange.value
  if (val === null) return ''
  return val >= 0 ? t('analyticsPage.changeUp') : t('analyticsPage.changeDown')
})

function onTrendPeriodChange(period: 'month' | 'quarter' | 'year') {
  trendPeriod.value = period
  dashboardStore.fetchTrend(period)
}

onMounted(async () => {
  await dashboardStore.fetchAll()
  dashboardStore.fetchDailyCostRanking()
  dashboardStore.fetchTrend(trendPeriod.value)
})
</script>

<style scoped>
.analytics-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

.analytics-detail-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.analytics-detail-card {
  background: var(--card-bg);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(1, 1, 32, 0.08);
}

[data-theme='dark'] .analytics-detail-card {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
}

.analytics-detail-card :deep(.van-cell-group__inset) {
  margin: 0;
  border-radius: 16px;
}

.analytics-detail-card--compact :deep(.van-cell-group__inset) {
  border-radius: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px 10px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-content {
  padding: 0 12px 12px;
}

/* Pie chart embedded: hide built-in title */
.pie-content .pie-chart-embedded :deep(.chart-title) {
  display: none;
}
.pie-content .pie-chart-embedded :deep(.allocation-chart) {
  padding: 0;
  margin: 0;
}

/* Period tabs inside card header */
.card-header :deep(.van-tabs--card) {
  .van-tabs__nav {
    height: 26px;
    background: var(--van-background-2);
    border-radius: 4px;
  }
  .van-tab {
    font-size: 11px;
    padding: 0 8px;
    line-height: 26px;
    border-radius: 4px;
  }
  .van-tab--active {
    background: var(--van-primary-color);
    color: var(--color-on-primary);
  }
}

[data-theme='dark'] .card-header :deep(.van-tabs--card) {
  .van-tabs__nav {
    background: rgba(255, 255, 255, 0.08);
  }
  .van-tab--active {
    background: var(--color-lavender);
    color: #010120;
  }
}

/* Item category label */
.item-category {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* Net worth change indicator */
.net-worth-change {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px 12px;
}

.change-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-radius: 12px;
}

.change-indicator.change-up {
  background: rgba(5, 150, 105, 0.1);
  color: #059669;
}

[data-theme='dark'] .change-indicator.change-up {
  background: rgba(110, 231, 160, 0.15);
  color: #6ee7a0;
}

.change-indicator.change-down {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

[data-theme='dark'] .change-indicator.change-down {
  background: rgba(252, 165, 165, 0.15);
  color: #fca5a5;
}

.change-arrow {
  font-size: 24px;
  font-weight: 600;
}

.change-value {
  font-size: 18px;
  font-weight: 600;
}

.change-label {
  font-size: 13px;
}

/* Responsive layout */
@media (min-width: 768px) {
  .analytics-detail-cards {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .analytics-detail-card {
    grid-column: span 2;
  }

  .analytics-detail-card--compact {
    grid-column: span 1;
  }
}

.bottom-spacer {
  height: 60px;
}
</style>