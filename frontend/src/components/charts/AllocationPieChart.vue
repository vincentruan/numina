<template>
  <div class="allocation-chart">
    <div class="chart-title">资产配置</div>
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { AllocationItem } from '@/types'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const props = defineProps<{
  data: AllocationItem[]
}>()

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params: any) => {
      return `${params.name}: ¥${Number(params.value).toLocaleString()} (${params.percent}%)`
    }
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    textStyle: { fontSize: 11 },
    formatter: (name: string) => {
      const item = props.data.find(d => d.category_name === name)
      if (item) return `${name} ${item.percentage.toFixed(1)}%`
      return name
    }
  },
  series: [
    {
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' }
      },
      labelLine: { show: false },
      data: props.data.map(item => ({
        name: item.category_name,
        value: item.amount,
        itemStyle: { color: item.color }
      }))
    }
  ]
}))
</script>

<style scoped>
.allocation-chart {
  background: var(--card-bg);
  border-radius: 8px;
  padding: 12px;
  margin: 0 12px 12px;
}
.chart-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.chart {
  height: 200px;
  width: 100%;
}

[data-theme='dark'] .chart {
  color-scheme: dark;
}
</style>
