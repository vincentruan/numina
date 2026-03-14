<template>
  <div class="dashboard-page">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Net Worth Card -->
      <div class="net-worth-card">
        <div class="nw-label">净资产</div>
        <div class="nw-amount">
          <MoneyDisplay :amount="overview?.net_worth || 0" size="large" />
        </div>
        <div class="nw-change" :class="changeClass">
          {{ changeText }} vs 上月
        </div>
        <van-grid :column-num="2" :border="false" class="nw-grid">
          <van-grid-item>
            <div class="grid-label">总资产</div>
            <div class="grid-value positive">
              <MoneyDisplay :amount="overview?.total_assets || 0" />
            </div>
          </van-grid-item>
          <van-grid-item>
            <div class="grid-label">总负债</div>
            <div class="grid-value negative">
              <MoneyDisplay :amount="overview?.total_liabilities || 0" />
            </div>
          </van-grid-item>
        </van-grid>
      </div>

      <!-- Trend Chart -->
      <TrendLineChart :data="dashboardStore.trend" @period-change="onPeriodChange" />

      <!-- Allocation Chart -->
      <AllocationPieChart :data="dashboardStore.allocation" />

      <!-- Top 5 Assets -->
      <van-cell-group v-if="dashboardStore.topAssets.length" inset title="Top 5 资产" class="section">
        <van-cell
          v-for="asset in dashboardStore.topAssets"
          :key="asset.id"
          :title="asset.name"
          :label="asset.category?.name"
          clickable
          @click="$router.push(`/assets/${asset.id}`)"
        >
          <template #value>
            <MoneyDisplay :amount="asset.current_value" />
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Daily Cost Ranking -->
      <van-cell-group v-if="dashboardStore.dailyCostRanking.length" inset title="日耗排行" class="section">
        <van-cell
          v-for="item in dashboardStore.dailyCostRanking"
          :key="item.asset_id"
          :title="`${item.category_icon} ${item.name}`"
          clickable
          @click="$router.push(`/assets/${item.asset_id}`)"
        >
          <template #value>
            <span class="daily-cost-value">¥{{ item.daily_cost.toFixed(2) }}/天</span>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Low Usage Alert -->
      <div v-if="dashboardStore.lowUsageAssets.length" class="section low-usage-section">
        <van-notice-bar left-icon="info-o" :scrollable="false" wrapable>
          <div>低使用率资产提醒</div>
          <div v-for="asset in dashboardStore.lowUsageAssets" :key="asset.id" class="low-usage-item">
            {{ asset.name }} - {{ usageText(asset.usage_frequency) }}
          </div>
        </van-notice-bar>
      </div>

      <!-- Investment Returns -->
      <van-cell-group v-if="dashboardStore.investmentReturns.length" inset title="投资收益排行" class="section">
        <van-cell
          v-for="item in dashboardStore.investmentReturns"
          :key="item.asset_id"
          :title="item.name"
          :label="`本金 ¥${item.purchase_price.toLocaleString()}`"
          clickable
          @click="$router.push(`/assets/${item.asset_id}`)"
        >
          <template #value>
            <div class="return-value">
              <span :class="item.return_rate >= 0 ? 'positive' : 'negative'">
                {{ item.return_rate >= 0 ? '+' : '' }}{{ item.return_rate.toFixed(2) }}%
              </span>
              <span class="return-amount">
                {{ item.return_amount >= 0 ? '+' : '' }}¥{{ item.return_amount.toLocaleString() }}
              </span>
            </div>
          </template>
        </van-cell>
      </van-cell-group>

      <!-- Settings Link -->
      <van-cell-group inset class="section">
        <van-cell title="设置" icon="setting-o" is-link to="/settings" />
      </van-cell-group>

      <div class="bottom-spacer" />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import TrendLineChart from '@/components/charts/TrendLineChart.vue'
import AllocationPieChart from '@/components/charts/AllocationPieChart.vue'

const dashboardStore = useDashboardStore()
const refreshing = ref(false)

const overview = computed(() => dashboardStore.overview)

const changeClass = computed(() => {
  const pct = overview.value?.month_change_percent || 0
  return pct >= 0 ? 'positive' : 'negative'
})

const changeText = computed(() => {
  const pct = overview.value?.month_change_percent || 0
  const arrow = pct >= 0 ? '↑' : '↓'
  return `${arrow} ${Math.abs(pct).toFixed(1)}%`
})

function usageText(freq?: string) {
  const map: Record<string, string> = {
    daily: '每天', weekly: '每周', monthly: '每月', rarely: '很少使用', idle: '闲置'
  }
  return map[freq || ''] || freq || '未知'
}

function onPeriodChange(period: 'month' | 'quarter' | 'year') {
  dashboardStore.fetchTrend(period)
}

async function onRefresh() {
  await dashboardStore.fetchAll()
  refreshing.value = false
}

onMounted(() => {
  dashboardStore.fetchAll()
})
</script>

<style scoped>
.dashboard-page {
  background: #f7f8fa;
  min-height: 100vh;
}
.net-worth-card {
  background: linear-gradient(135deg, #1989fa 0%, #2b5cff 100%);
  padding: 24px 16px 16px;
  color: #fff;
}
.nw-label {
  font-size: 13px;
  opacity: 0.8;
}
.nw-amount {
  margin: 4px 0;
}
.nw-amount :deep(.money-display) {
  color: #fff;
}
.nw-change {
  font-size: 13px;
  margin-bottom: 12px;
}
.nw-change.positive {
  color: #a8f0c6;
}
.nw-change.negative {
  color: #ffb3b3;
}
.nw-grid {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 8px;
}
.nw-grid :deep(.van-grid-item__content) {
  background: transparent;
  padding: 12px;
}
.grid-label {
  font-size: 12px;
  opacity: 0.8;
  color: #fff;
}
.grid-value {
  margin-top: 4px;
}
.grid-value :deep(.money-display) {
  color: #fff;
  font-size: 16px;
  font-weight: 500;
}
.section {
  margin-top: 12px;
}
.daily-cost-value {
  color: #ff976a;
  font-size: 13px;
}
.low-usage-section {
  padding: 0 12px;
}
.low-usage-item {
  font-size: 12px;
  margin-top: 4px;
}
.return-value {
  text-align: right;
}
.return-value .positive {
  color: #07c160;
  font-weight: 500;
}
.return-value .negative {
  color: #ee0a24;
  font-weight: 500;
}
.return-amount {
  display: block;
  font-size: 11px;
  color: #969799;
}
.positive {
  color: #07c160;
}
.negative {
  color: #ee0a24;
}
.bottom-spacer {
  height: 20px;
}
</style>
