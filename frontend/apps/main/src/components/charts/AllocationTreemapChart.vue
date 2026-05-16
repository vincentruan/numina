<template>
  <div class="allocation-treemap">
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
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

const isDark = ref(document.documentElement.getAttribute('data-theme') === 'dark')

let observer: MutationObserver | null = null
onMounted(() => {
  observer = new MutationObserver(() => {
    isDark.value = document.documentElement.getAttribute('data-theme') === 'dark'
  })
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
})
onUnmounted(() => observer?.disconnect())

// Dynamic chart height: at least 200px, grows with data count, capped at 320px
const chartHeight = computed(() => {
  const count = props.data.length
  if (count <= 4) return 200
  if (count <= 8) return 260
  return 320
})

const chartOption = computed(() => {
  const borderColor = isDark.value ? '#1a1a2e' : '#fff'
  const labelColor = isDark.value ? '#f0f0f0' : '#fff'
  const tooltipBg = isDark.value ? '#1e1e3a' : '#fff'
  const tooltipText = isDark.value ? '#e0e0e0' : '#333'

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: tooltipBg,
      borderColor: isDark.value ? '#333' : '#e0e0e0',
      textStyle: { color: tooltipText, fontSize: 12 },
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
          color: labelColor,
          overflow: 'truncate',
        },
        upperLabel: { show: false },
        itemStyle: {
          borderWidth: 2,
          borderColor,
          borderColorSaturation: 0,
          gapWidth: 2,
        },
        visibleMin: 200,
        data: props.data.map(item => ({
          name: item.category_name,
          value: item.amount,
          itemStyle: { color: item.color },
        })),
      },
    ],
  }
})
</script>

<style scoped>
.allocation-treemap {
  width: 100%;
}

.chart {
  width: 100%;
  height: v-bind('chartHeight + "px"');
}
</style>