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
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { MCPToolBreakdown } from '@/api/mcp-token'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const { t } = useI18n()

const props = defineProps<{
  data: MCPToolBreakdown[]
}>()

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 90, right: 16, top: 16, bottom: 24 },
  xAxis: { type: 'value', minInterval: 1 },
  yAxis: {
    type: 'category',
    data: props.data.map(d => d.tool_name),
    axisLabel: { fontSize: 10 },
  },
  series: [
    {
      type: 'bar',
      data: props.data.map(d => d.count),
      itemStyle: { borderRadius: [0, 4, 4, 0] },
    },
  ],
}))
</script>

<style scoped>
.mcp-chart {
  width: 100%;
  height: 220px;
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
