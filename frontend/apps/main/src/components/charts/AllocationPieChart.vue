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
import type { CallbackDataParams } from 'echarts/types/dist/shared'
import type { AllocationItem, LiabilityAllocationItem } from '@/types'
import { useCurrency } from '@/composables/useCurrency'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const { format } = useCurrency()

const props = defineProps<{
  data: AllocationItem[] | LiabilityAllocationItem[]
}>()

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params: CallbackDataParams) => {
      return `${params.name}: ${format(Number(params.value))} (${params.percent}%)`
    }
  },
  legend: {
    orient: 'horizontal',
    bottom: 4,
    left: 'center',
    itemWidth: 10,
    itemHeight: 10,
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
      radius: ['38%', '65%'],
      center: ['50%', '38%'],
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
  height: 240px;
  width: 100%;
}

[data-theme='dark'] .chart {
  color-scheme: dark;
}
</style>
