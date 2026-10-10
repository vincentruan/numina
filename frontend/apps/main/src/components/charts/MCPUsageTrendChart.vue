<template>
  <div class="mcp-chart">
    <v-chart v-if="data.length > 0" class="chart" :option="chartOption" autoresize />
    <div v-else class="chart-empty">{{ t('mcp.stats.empty') }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { MCPHourlyBucket } from '@/api/mcp-token'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const { t } = useI18n()

const props = defineProps<{
  data: MCPHourlyBucket[]
}>()

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 16, top: 16, bottom: 40 },
  xAxis: {
    type: 'category',
    data: props.data.map(d => d.hour),
    axisLabel: { fontSize: 10, rotate: 45 },
  },
  yAxis: { type: 'value', minInterval: 1 },
  series: [
    {
      type: 'line',
      smooth: true,
      data: props.data.map(d => d.count),
      areaStyle: { opacity: 0.15 },
    },
  ],
}))
</script>

<style scoped>
.mcp-chart {
  width: 100%;
  height: 200px;
}
.chart {
  width: 100%;
  height: 100%;
}
.chart-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
