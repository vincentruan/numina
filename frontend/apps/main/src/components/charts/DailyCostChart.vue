<template>
  <div class="daily-cost-chart">
    <div class="chart-header">
      <span class="chart-title">日均成本趋势</span>
      <span class="chart-current">当前 {{ currency.format(currentDailyCost) }}/天</span>
    </div>
    <div v-if="hasData" class="chart-wrapper">
      <v-chart class="chart" :option="chartOption" autoresize />
    </div>
    <div v-else class="chart-empty">暂无趋势数据</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { CallbackDataParams } from 'echarts/types/dist/shared'
import { useCurrency } from '@/composables/useCurrency'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkLineComponent])

const { t } = useI18n()
const currency = useCurrency()

const props = defineProps<{
  purchasePrice: number
  purchaseDate: string
  targetDailyCost?: number | null
}>()

const hasData = computed(() => {
  if (!props.purchasePrice || !props.purchaseDate) return false
  const purchase = new Date(props.purchaseDate)
  const now = new Date()
  const days = Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
  return days > 0
})

const currentDailyCost = computed(() => {
  if (!props.purchasePrice || !props.purchaseDate) return 0
  const purchase = new Date(props.purchaseDate)
  const now = new Date()
  const days = Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
  return days > 0 ? props.purchasePrice / days : props.purchasePrice
})

const chartOption = computed(() => {
  if (!props.purchasePrice || !props.purchaseDate) return {}

  const purchase = new Date(props.purchaseDate)
  const now = new Date()
  const totalDays = Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))

  // Generate data points — one per month from purchase to now, plus future projection
  const points: { date: string; cost: number }[] = []
  const cursor = new Date(purchase)
  cursor.setDate(1) // Start from first of month

  // Move to next month after purchase
  cursor.setMonth(cursor.getMonth() + 1)

  while (cursor <= now) {
    const days = Math.floor((cursor.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
    if (days > 0) {
      points.push({
        date: `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}`,
        cost: Math.round((props.purchasePrice / days) * 100) / 100
      })
    }
    cursor.setMonth(cursor.getMonth() + 1)
  }

  // Add current point
  if (totalDays > 0) {
    points.push({
      date: t('common.today'),
      cost: Math.round((props.purchasePrice / totalDays) * 100) / 100
    })
  }

  // Fallback: if no monthly points (asset used < 1 month), add purchase day as first point
  if (points.length <= 1) {
    const purchaseDateStr = `${purchase.getFullYear()}-${String(purchase.getMonth() + 1).padStart(2, '0')}-${String(purchase.getDate()).padStart(2, '0')}`
    points.unshift({
      date: purchaseDateStr,
      cost: props.purchasePrice
    })
  }

  // Add future projection points (3, 6, 12 months)
  const futureMonths = [3, 6, 12]
  for (const m of futureMonths) {
    const futureDate = new Date(now)
    futureDate.setMonth(futureDate.getMonth() + m)
    const futureDays = Math.floor((futureDate.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
    if (futureDays > 0) {
      points.push({
        date: t('common.monthsSuffix', { months: m }),
        cost: Math.round((props.purchasePrice / futureDays) * 100) / 100
      })
    }
  }

  const markLines: { yAxis: number; label: object; lineStyle: object }[] = []
  if (props.targetDailyCost) {
    const target = props.targetDailyCost
    markLines.push({
      yAxis: target,
      label: { formatter: () => `目标 ${currency.format(target)}`, position: 'end', fontSize: 10 },
      lineStyle: { color: '#07c160', type: 'dashed' }
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params: CallbackDataParams[]) => {
        const p = params[0] as CallbackDataParams & { axisValue: string }
        return `${p.axisValue}<br/>日均 ${currency.format(Number(p.value))}`
      }
    },
    grid: {
      left: 10,
      right: 10,
      top: 10,
      bottom: 5,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: points.map(p => p.date),
      axisLabel: { fontSize: 10, rotate: 30 },
      boundaryGap: false
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 10,
        formatter: (val: number) => currency.format(val)
      },
      splitLine: { lineStyle: { type: 'dashed' } }
    },
    series: [
      {
        type: 'line',
        data: points.map(p => p.cost),
        smooth: true,
        lineStyle: { width: 2, color: '#ff976a' },
        itemStyle: { color: '#ff976a' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(255,151,106,0.25)' },
              { offset: 1, color: 'rgba(255,151,106,0.02)' }
            ]
          }
        },
        markLine: markLines.length ? { data: markLines, silent: true } : undefined
      }
    ]
  }
})
</script>

<style scoped>
.daily-cost-chart {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 14px;
  margin: 12px 16px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.chart-current {
  font-size: 12px;
  color: #ff976a;
  font-weight: 500;
}
.chart-empty {
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  color: var(--text-tertiary);
}
.chart {
  height: 200px;
  width: 100%;
}

[data-theme='dark'] .chart {
  color-scheme: dark;
}
</style>
