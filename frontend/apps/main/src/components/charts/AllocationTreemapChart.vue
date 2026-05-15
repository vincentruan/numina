<template>
  <div class="allocation-treemap">
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { TreemapChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { CallbackDataParams } from 'echarts/types/dist/shared'
import type { AllocationItem } from '@/types'

use([CanvasRenderer, TreemapChart, TooltipComponent])

const props = defineProps<{
  data: AllocationItem[]
}>()

const chartOption = computed(() => ({
  tooltip: {
    trigger: 'item',
    formatter: (params: CallbackDataParams) => {
      const item = props.data.find(d => d.category_name === params.name)
      if (item) {
        return `${params.name}: ¥${Number(params.value).toLocaleString()} (${item.percentage.toFixed(1)}%)`
      }
      return `${params.name}: ¥${Number(params.value).toLocaleString()}`
    }
  },
  series: [
    {
      type: 'treemap',
      width: '100%',
      height: '100%',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: (params: CallbackDataParams) => {
          const item = props.data.find(d => d.category_name === params.name)
          if (item) {
            return `${params.name}\n${item.percentage.toFixed(1)}%`
          }
          return params.name
        },
        fontSize: 12,
        color: '#fff'
      },
      upperLabel: { show: false },
      itemStyle: {
        borderWidth: 2,
        borderColor: '#fff',
        borderColorSaturation: 0,
        gapWidth: 2
      },
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
.allocation-treemap {
  background: var(--card-bg);
  border-radius: 8px;
  padding: 12px;
  margin: 0;
}

.chart {
  height: 220px;
  width: 100%;
}

[data-theme='dark'] .chart {
  color-scheme: dark;
}
</style>