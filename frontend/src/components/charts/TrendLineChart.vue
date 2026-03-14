<template>
  <div class="trend-chart">
    <div class="chart-header">
      <span class="chart-title">净资产趋势</span>
      <van-tabs v-model:active="activePeriod" type="card" @change="onPeriodChange">
        <van-tab title="月" name="month" />
        <van-tab title="季" name="quarter" />
        <van-tab title="年" name="year" />
      </van-tabs>
    </div>
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { TrendPoint } from '@/types'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps<{
  data: TrendPoint[]
}>()

const emit = defineEmits<{
  periodChange: [period: 'month' | 'quarter' | 'year']
}>()

const activePeriod = ref('month')

function onPeriodChange(period: string) {
  emit('periodChange', period as 'month' | 'quarter' | 'year')
}

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'axis',
    formatter: (params: any[]) => {
      let html = `${params[0].axisValue}<br/>`
      params.forEach((p: any) => {
        html += `${p.marker} ${p.seriesName}: ¥${Number(p.value).toLocaleString()}<br/>`
      })
      return html
    }
  },
  legend: {
    data: ['净资产', '总资产', '总负债'],
    bottom: 0,
    textStyle: { fontSize: 11 }
  },
  grid: {
    left: 10,
    right: 10,
    top: 10,
    bottom: 30,
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.date),
    axisLabel: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      fontSize: 10,
      formatter: (val: number) => {
        if (val >= 10000) return `${(val / 10000).toFixed(0)}万`
        return val.toString()
      }
    },
    splitLine: { lineStyle: { type: 'dashed' } }
  },
  series: [
    {
      name: '净资产',
      type: 'line',
      data: props.data.map(d => d.net_worth),
      smooth: true,
      lineStyle: { width: 2 },
      itemStyle: { color: '#1989fa' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(25,137,250,0.25)' },
            { offset: 1, color: 'rgba(25,137,250,0.02)' }
          ]
        }
      }
    },
    {
      name: '总资产',
      type: 'line',
      data: props.data.map(d => d.total_assets),
      smooth: true,
      lineStyle: { width: 1.5, type: 'dashed' },
      itemStyle: { color: '#07c160' }
    },
    {
      name: '总负债',
      type: 'line',
      data: props.data.map(d => d.total_liabilities),
      smooth: true,
      lineStyle: { width: 1.5, type: 'dashed' },
      itemStyle: { color: '#ee0a24' }
    }
  ]
}))
</script>

<style scoped>
.trend-chart {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin: 12px;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.chart-title {
  font-size: 14px;
  font-weight: 500;
  color: #323233;
}
.chart {
  height: 220px;
  width: 100%;
}
:deep(.van-tabs--card) {
  .van-tabs__nav {
    height: 26px;
  }
  .van-tab {
    font-size: 11px;
    padding: 0 8px;
    line-height: 26px;
  }
}
</style>
