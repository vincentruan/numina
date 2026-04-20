<template>
  <div class="overview-card">
    <div class="ov-main">
      <div class="ov-label">总资产</div>
      <div class="ov-amount">
        <MoneyDisplay :amount="totalAssets" size="large" />
      </div>
      <div class="ov-sub-row">
        <span v-if="totalDailyCost > 0" class="ov-daily">日均 {{ currency.format(totalDailyCost) }}</span>
        <span class="ov-count">共 {{ assetCount }} 件</span>
        <span v-if="monthOverMonthChange != null" class="ov-change" :class="changeClass">
          {{ changeText }} vs 上月
        </span>
      </div>
    </div>
    <div class="ov-detail">
      <div class="ov-detail-item">
        <div class="ov-detail-label">净资产</div>
        <div class="ov-detail-value">
          <MoneyDisplay :amount="netWorth" />
        </div>
      </div>
      <div class="ov-detail-divider" />
      <div class="ov-detail-item">
        <div class="ov-detail-label">总负债</div>
        <div class="ov-detail-value">
          <MoneyDisplay :amount="totalLiabilities" />
        </div>
      </div>
    </div>

    <!-- Net worth sparkline -->
    <div v-if="sparklineData.length > 1" class="ov-sparkline">
      <v-chart class="sparkline-chart" :option="sparklineOption" autoresize />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import { useCurrency } from '@/composables/useCurrency'
import type { TrendPoint } from '@/types'

use([CanvasRenderer, LineChart, GridComponent])

const props = defineProps<{
  netWorth: number
  totalAssets: number
  totalLiabilities: number
  totalDailyCost: number
  assetCount: number
  monthOverMonthChange?: number | null
  trendPoints?: TrendPoint[]
}>()

const currency = useCurrency()

const changeClass = computed(() => {
  const pct = props.monthOverMonthChange || 0
  return pct >= 0 ? 'positive' : 'negative'
})

const changeText = computed(() => {
  const pct = props.monthOverMonthChange || 0
  const arrow = pct >= 0 ? '↑' : '↓'
  return `${arrow} ${Math.abs(pct).toFixed(1)}%`
})

// Last 30 data points for sparkline
const sparklineData = computed(() => {
  const pts = props.trendPoints ?? []
  return pts.slice(-30).map(p => p.net_worth)
})

const sparklineOption = computed(() => {
  const data = sparklineData.value
  const isUp = data.length < 2 || data[data.length - 1] >= data[0]
  return {
    grid: { top: 2, bottom: 2, left: 2, right: 2 },
    xAxis: { type: 'category', show: false, data: data.map((_, i) => i) },
    yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
    series: [{
      type: 'line',
      data,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: isUp ? '#7dffa8' : '#ffb3b3', width: 1.5 },
      areaStyle: { color: isUp ? 'rgba(125,255,168,0.15)' : 'rgba(255,179,179,0.15)' },
    }],
  }
})
</script>

<style scoped>
.overview-card {
  background: linear-gradient(135deg, #1677ff 0%, #0052d9 50%, #2b3a8e 100%);
  padding: 16px 16px 12px;
  color: #fff;
}
[data-theme='dark'] .overview-card {
  background: linear-gradient(135deg, #0d4a99 0%, #003d8f 50%, #1a2456 100%);
}
.ov-main {
  display: flex;
  flex-direction: column;
}
.ov-label {
  font-size: 12px;
  opacity: 0.85;
}
.ov-amount {
  margin: 2px 0 4px;
}
.ov-amount :deep(.money-display) {
  color: #fff;
}
.ov-sub-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  opacity: 0.9;
}
.ov-daily {
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  backdrop-filter: blur(4px);
}
[data-theme='dark'] .ov-daily {
  background: rgba(255, 255, 255, 0.15);
}
.ov-count {
  font-size: 11px;
}
.ov-change.positive {
  color: #7dffa8;
}
.ov-change.negative {
  color: #ffb3b3;
}
.ov-detail {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 8px 12px;
  margin-top: 8px;
}
[data-theme='dark'] .ov-detail {
  background: rgba(255, 255, 255, 0.08);
}
.ov-detail-item {
  flex: 1;
  text-align: center;
}
.ov-detail-label {
  font-size: 11px;
  opacity: 0.75;
}
.ov-detail-value {
  margin-top: 2px;
}
.ov-detail-value :deep(.money-display) {
  color: #fff;
  font-size: 14px;
  font-weight: 600;
}
.ov-sparkline {
  margin-top: 8px;
  height: 40px;
}
.sparkline-chart {
  width: 100%;
  height: 40px;
}
.ov-detail-divider {
  width: 1px;
  height: 24px;
  background: rgba(255, 255, 255, 0.25);
}
[data-theme='dark'] .ov-detail-divider {
  background: rgba(255, 255, 255, 0.15);
}
</style>
