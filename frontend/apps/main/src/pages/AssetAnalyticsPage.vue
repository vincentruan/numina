<template>
  <div class="analytics-page">
    <PageHeader :title="t('analyticsPage.title')" />

    <van-tabs
      v-model:active="activeTab"
      type="line"
      class="page-tabs"
      :color="tabActiveColor"
      title-active-color="var(--text-primary)"
      title-inactive-color="var(--text-secondary)"
    >
      <!-- ── 趋势 tab ── -->
      <van-tab :title="t('analyticsPage.tabTrend')" name="trend">
        <div class="tab-content">

          <!-- Section 1: 资产总值 -->
          <div class="section-card">
            <div class="card-header">
              <span class="card-title">{{ t('analyticsPage.totalAssetsSection') }}</span>
              <van-tabs
                v-model:active="trendPeriod"
                type="card"
                shrink
                @change="onPeriodChange"
              >
                <van-tab :title="t('analyticsPage.periodMonth')" name="month" />
                <van-tab :title="t('analyticsPage.periodQuarter')" name="quarter" />
                <van-tab :title="t('analyticsPage.periodYear')" name="year" />
              </van-tabs>
            </div>
            <div class="net-worth-value">
              {{ format(dashboardStore.overview?.net_worth ?? 0) }}
            </div>
            <div
              v-if="monthOverMonthChange !== null"
              class="change-badge"
              :class="changeClass"
            >
              {{ changeArrow }} {{ Math.abs(monthOverMonthChange).toFixed(1) }}%
              {{ changeLabel }}
            </div>
            <div class="chart-area">
              <TrendLineChartSimple
                v-if="dashboardStore.trend.length"
                :data="dashboardStore.trend"
              />
              <van-empty v-else :description="t('common.noData')" image-size="60" />
            </div>
          </div>

          <!-- Section 2: 资产状态 -->
          <div class="section-card">
            <div class="card-header">
              <span class="card-title">{{ t('analyticsPage.assetStatusSection') }}</span>
            </div>
            <div v-if="dashboardStore.statesSummary" class="status-grid">
              <div class="status-tile status-tile--in-use">
                <div class="status-count">
                  {{ dashboardStore.statesSummary.states['in_use']?.count ?? 0 }}
                </div>
                <div class="status-label">{{ t('statusGrid.inUse') }}</div>
              </div>
              <div class="status-tile status-tile--idle">
                <div class="status-count">
                  {{ dashboardStore.statesSummary.states['idle']?.count ?? 0 }}
                </div>
                <div class="status-label">{{ t('statusGrid.idle') }}</div>
              </div>
              <div class="status-tile status-tile--sold">
                <div class="status-count">
                  {{ dashboardStore.statesSummary.states['sold']?.count ?? 0 }}
                </div>
                <div class="status-label">{{ t('statusGrid.sold') }}</div>
              </div>
              <div class="status-tile status-tile--retired">
                <div class="status-count">
                  {{ dashboardStore.statesSummary.states['retired']?.count ?? 0 }}
                </div>
                <div class="status-label">{{ t('statusGrid.retired') }}</div>
              </div>
            </div>
            <van-empty v-else :description="t('common.noData')" image-size="60" />
          </div>

          <!-- Section 3: 新增资产 -->
          <div class="section-card">
            <div class="card-header">
              <span class="card-title">{{ t('analyticsPage.newAssetsSection') }}</span>
            </div>
            <div class="new-assets-count">
              <span class="count-number">{{ dashboardStore.newAssets?.count ?? 0 }}</span>
              <span class="count-unit">{{ t('analyticsPage.newAssetsUnit') }}</span>
            </div>
            <template v-if="dashboardStore.newAssets && dashboardStore.newAssets.items.length">
              <div
                v-for="item in dashboardStore.newAssets.items.slice(0, 3)"
                :key="item.id"
                class="new-asset-row"
              >
                <div class="new-asset-left">
                  <span class="new-asset-icon">
                    <svg v-if="item.icon?.startsWith('icon-')" class="icon-svg" aria-hidden="true">
                      <use :href="`#${getIconId(item.icon)}`" />
                    </svg>
                    <span v-else>{{ item.icon?.trim() || '📦' }}</span>
                  </span>
                  <div class="new-asset-info">
                    <div class="new-asset-name">{{ item.name }}</div>
                    <div class="new-asset-date">{{ daysAgo(item.created_at) }}</div>
                  </div>
                </div>
                <div class="new-asset-value">{{ format(item.current_value) }}</div>
              </div>
            </template>
            <van-empty
              v-else-if="dashboardStore.newAssets?.count === 0"
              :description="t('common.noData')"
              image-size="60"
            />
          </div>

          <!-- Section 4: 日均成本 -->
          <div class="section-card">
            <div class="card-header">
              <span class="card-title">{{ t('analyticsPage.dailyCostCard') }}</span>
            </div>
            <template v-if="dashboardStore.dailyCostRanking.length">
              <div
                v-for="(item, index) in dashboardStore.dailyCostRanking.slice(0, 5)"
                :key="item.id"
                class="cost-row"
                @click="router.push(`/assets/${item.id}`)"
              >
                <div class="cost-row-left">
                  <span class="rank-badge" :class="rankClass(index)">{{ index + 1 }}</span>
                  <span class="cost-icon">
                    <svg v-if="item.icon?.startsWith('icon-')" class="icon-svg" aria-hidden="true">
                      <use :href="`#${getIconId(item.icon)}`" />
                    </svg>
                    <span v-else>{{ item.icon?.trim() || '📦' }}</span>
                  </span>
                  <span class="cost-name">{{ item.name }}</span>
                </div>
                <span class="cost-value">{{ format(item.daily_cost) }}{{ t('analyticsPage.perDay') }}</span>
              </div>
            </template>
            <van-empty v-else :description="t('common.noData')" image-size="60" />
          </div>

          <!-- Section 5: 分类占比 -->
          <div class="section-card">
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
          </div>

          <!-- Section 7: 低使用率资产 (kept — unique content) -->
          <div class="section-card section-card--compact">
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
          </div>

        </div>
      </van-tab>

      <!-- ── 洞悉 tab ── -->
      <van-tab :title="t('analyticsPage.tabInsight')" name="insight">
        <InsightsTab />
      </van-tab>
    </van-tabs>

    <div class="bottom-spacer" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import PageHeader from '@/components/common/PageHeader.vue'
import TrendLineChartSimple from '@/components/charts/TrendLineChartSimple.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'
import InsightsTab from '@/components/insights/InsightsTab.vue'
import { useCurrency } from '@/composables/useCurrency'
import { getIconId } from '@/utils/icon'

const { t } = useI18n()
const router = useRouter()
const dashboardStore = useDashboardStore()
const { format } = useCurrency()

const activeTab = ref<'trend' | 'insight'>('trend')
const trendPeriod = ref<'month' | 'quarter' | 'year'>('month')

const isDarkMode = ref(document.documentElement.getAttribute('data-theme') === 'dark')

let _themeObserver: MutationObserver | null = null

const monthOverMonthChange = computed(() => dashboardStore.overview?.month_over_month_change ?? null)
const lowUsageAssets = computed(() =>
  dashboardStore.lowUsageAssets.filter((a) => a.usage_frequency === 'idle'),
)

const changeClass = computed(() => {
  const val = monthOverMonthChange.value
  if (val === null) return ''
  return val >= 0 ? 'change-up' : 'change-down'
})

const changeArrow = computed(() => {
  const val = monthOverMonthChange.value
  if (val === null) return ''
  return val >= 0 ? '▲' : '▼'
})

const changeLabel = computed(() => {
  const val = monthOverMonthChange.value
  if (val === null) return ''
  return val >= 0 ? t('analyticsPage.changeUp') : t('analyticsPage.changeDown')
})

function daysAgo(isoDate: string): string {
  if (!isoDate) return ''
  const days = Math.floor((Date.now() - new Date(isoDate).getTime()) / 86400000)
  return t('analyticsPage.daysAgo', { n: days })
}

function usageLabel(frequency: string): string {
  return frequency === 'idle' ? t('statusGrid.idle') : frequency
}

function rankClass(index: number): string {
  if (index === 0) return 'rank-badge--first'
  if (index === 1) return 'rank-badge--second'
  if (index === 2) return 'rank-badge--third'
  return 'rank-badge--rest'
}

function onPeriodChange(period: 'month' | 'quarter' | 'year') {
  trendPeriod.value = period
  dashboardStore.fetchTrend(period)
  dashboardStore.fetchNewAssets(period)
}

onMounted(async () => {
  _themeObserver = new MutationObserver(() => {
    isDarkMode.value = document.documentElement.getAttribute('data-theme') === 'dark'
  })
  _themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

  await dashboardStore.fetchAll()
  dashboardStore.fetchDailyCostRanking()
  dashboardStore.fetchNewAssets(trendPeriod.value)
})

onUnmounted(() => {
  _themeObserver?.disconnect()
})

const tabActiveColor = computed(() =>
  isDarkMode.value ? 'var(--color-lavender)' : 'var(--van-primary-color)'
)
</script>

<style scoped>
.analytics-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}

/* ── Page-level tab bar ── */
.page-tabs :deep(.van-tabs__wrap) {
  background: var(--card-bg);
  border-bottom: 1px solid var(--separator);
}

.page-tabs :deep(.van-tab) {
  font-size: 15px;
  font-weight: 500;
}

.page-tabs :deep(.van-tab--active) {
  font-weight: 600;
}

/* ── Shared card container ── */
.tab-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.section-card {
  background: var(--card-bg);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(1, 1, 32, 0.08);
  padding: 0 0 12px;
}

[data-theme='dark'] .section-card {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
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
  padding: 0 12px;
}

.pie-content .pie-chart-embedded :deep(.chart-title) {
  display: none;
}
.pie-content .pie-chart-embedded :deep(.allocation-chart) {
  padding: 0;
  margin: 0;
}

/* Period card-tabs inside card header */
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
  .van-tab {
    color: rgba(255, 255, 255, 0.7);
  }
  .van-tab--active {
    background: var(--color-lavender);
    color: #010120;
  }
}

/* ── Section 1: 资产总值 ── */
.net-worth-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  padding: 0 16px 4px;
  letter-spacing: -0.5px;
}

.change-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
  margin: 0 16px 10px;
}

.change-badge.change-up {
  background: rgba(5, 150, 105, 0.08);
  color: #059669;
}

[data-theme='dark'] .change-badge.change-up {
  background: rgba(110, 231, 160, 0.12);
  color: #6ee7a0;
}

.change-badge.change-down {
  background: rgba(220, 38, 38, 0.08);
  color: #dc2626;
}

[data-theme='dark'] .change-badge.change-down {
  background: rgba(252, 165, 165, 0.12);
  color: #fca5a5;
}

.chart-area {
  padding: 0 12px;
}

/* ── Section 2: 资产状态 ── */
.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding: 0 12px;
}

.status-tile {
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}

.status-count {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.status-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.status-tile--in-use {
  background: rgba(5, 150, 105, 0.08);
}
.status-tile--in-use .status-count { color: #059669; }

[data-theme='dark'] .status-tile--in-use {
  background: rgba(110, 231, 160, 0.12);
}
[data-theme='dark'] .status-tile--in-use .status-count { color: var(--color-trend-down); }

.status-tile--idle {
  background: rgba(250, 140, 22, 0.08);
}
.status-tile--idle .status-count { color: #fa8c16; }

[data-theme='dark'] .status-tile--idle {
  background: rgba(251, 191, 36, 0.12);
}
[data-theme='dark'] .status-tile--idle .status-count { color: var(--color-trend-warn); }

.status-tile--sold {
  background: rgba(59, 130, 246, 0.08);
}
.status-tile--sold .status-count { color: #3b82f6; }

[data-theme='dark'] .status-tile--sold {
  background: rgba(147, 197, 253, 0.12);
}
[data-theme='dark'] .status-tile--sold .status-count { color: #93c5fd; }

.status-tile--retired {
  background: var(--bg-secondary);
}
.status-tile--retired .status-count { color: var(--text-secondary); }

/* ── Section 3: 新增资产 ── */
.new-assets-count {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 0 16px 10px;
}

.count-number {
  font-size: 30px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -1px;
}

.count-unit {
  font-size: 13px;
  color: var(--text-secondary);
}

.new-asset-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  margin: 0 4px 4px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.new-asset-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.new-asset-icon {
  font-size: 18px;
  line-height: 1;
}

.new-asset-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.new-asset-date {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.new-asset-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

/* ── Section 4: 日均成本 ── */
.cost-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  cursor: pointer;
}

.cost-row:active {
  background: var(--bg-secondary);
}

.cost-row-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.rank-badge {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.rank-badge--first  { background: #ff4d4f; }
.rank-badge--second { background: #fa8c16; }
.rank-badge--third  { background: #fadb14; color: #333; }
.rank-badge--rest   { background: var(--text-secondary); }

.cost-icon {
  font-size: 18px;
  line-height: 1;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cost-icon .icon-svg,
.new-asset-icon .icon-svg {
  width: 20px;
  height: 20px;
  color: var(--text-primary);
}

[data-theme='dark'] .cost-icon .icon-svg,
[data-theme='dark'] .new-asset-icon .icon-svg {
  color: var(--text-primary);
}

.cost-name {
  font-size: 13px;
  color: var(--text-primary);
}

.cost-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Bottom spacer ── */
.bottom-spacer {
  height: 60px;
}

/* ── Tablet 2-col layout ── */
@media (min-width: 768px) {
  .tab-content {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .section-card:first-child {
    grid-column: span 2;
  }
}
</style>