<template>
  <div class="trend-chart-simple">
    <v-chart class="chart" :option="chartOption" autoresize />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { CallbackDataParams } from 'echarts/types/dist/shared'
import type { TrendPoint } from '@/types'
import { useCurrency } from '@/composables/useCurrency'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const { t } = useI18n()
const { format } = useCurrency()

const props = defineProps<{
  data: TrendPoint[]
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

const chartOption = computed(() => {
  const textColor = isDark.value ? '#e8e8f0' : '#17171c'
  const gridColor = isDark.value ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'
  const netWorthColor = isDark.value ? '#bdbbff' : '#17171c'
  const assetColor = '#07c160'
  const liabilityColor = '#ee0a24'
  const areaGradient = isDark.value
    ? [
        { offset: 0, color: 'rgba(189, 187, 255, 0.15)' },
        { offset: 1, color: 'rgba(189, 187, 255, 0.02)' }
      ]
    : [
        { offset: 0, color: 'rgba(23, 23, 28, 0.18)' },
        { offset: 1, color: 'rgba(23, 23, 28, 0.02)' }
      ]

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: isDark.value ? '#1a1a2e' : '#fff',
      borderColor: isDark.value ? '#2a2a4a' : '#e0e0e0',
      textStyle: { color: isDark.value ? '#d0d0e8' : '#333', fontSize: 12 },
      formatter: (params: CallbackDataParams[]) => {
        let html = `${(params[0] as CallbackDataParams & { axisValue: string }).axisValue}<br/>`
        params.forEach((p: CallbackDataParams) => {
          html += `${p.marker} ${p.seriesName}: ${format(Number(p.value))}<br/>`
        })
        return html
      }
    },
    legend: {
      data: [t('common.netWorth'), t('common.totalAssets'), t('common.totalLiabilities')],
      bottom: 0,
      textStyle: { fontSize: 11, color: textColor }
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
      axisLabel: { fontSize: 10, color: textColor },
      axisLine: { lineStyle: { color: gridColor } }
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        fontSize: 10,
        color: textColor,
        formatter: (val: number) => {
          if (val >= 10000) return `${(val / 10000).toFixed(0)}${t('common.unitTenThousand')}`
          return val.toString()
        }
      },
      splitLine: { lineStyle: { type: 'dashed', color: gridColor } }
    },
    series: [
      {
        name: t('common.netWorth'),
        type: 'line',
        data: props.data.map(d => d.net_worth),
        smooth: true,
        lineStyle: { width: 2 },
        itemStyle: { color: netWorthColor },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: areaGradient
          }
        }
      },
      {
        name: t('common.totalAssets'),
        type: 'line',
        data: props.data.map(d => d.total_assets),
        smooth: true,
        lineStyle: { width: 1.5, type: 'dashed' },
        itemStyle: { color: assetColor }
      },
      {
        name: t('common.totalLiabilities'),
        type: 'line',
        data: props.data.map(d => d.total_liabilities),
        smooth: true,
        lineStyle: { width: 1.5, type: 'dashed' },
        itemStyle: { color: liabilityColor }
      }
    ]
  }
})
</script>

<style scoped>
.trend-chart-simple {
  width: 100%;
}

.chart {
  height: 200px;
  width: 100%;
}
</style>