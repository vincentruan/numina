<template>
  <div class="projection-chart">
    <van-cell-group inset class="params">
      <van-field
        v-model.number="projectionYears"
        type="number"
        :label="t('timeMachine.projectionYears')"
      />
      <van-field
        v-model.number="inflationRate"
        type="number"
        :label="t('timeMachine.inflationRate')"
        placeholder="0.03"
      />
    </van-cell-group>

    <div class="calc-btn-wrap">
      <van-button round block type="primary" :loading="loading" @click="calculate">
        {{ t('timeMachine.calculate') }}
      </van-button>
    </div>

    <div v-if="hasData" ref="chartRef" class="chart-container" />

    <div v-if="result?.summary" class="summary-card">
      <p>{{ result.summary }}</p>
    </div>

    <van-cell-group v-if="result" inset class="assumptions">
      <van-cell :title="t('timeMachine.assetCount')" :value="String(result.assumptions.asset_count ?? '-')" />
      <van-cell :title="t('timeMachine.liabilityCount')" :value="String(result.assumptions.liability_count ?? '-')" />
      <van-cell :title="t('timeMachine.inflationRate')" :value="`${(inflationRate * 100).toFixed(1)}%`" />
    </van-cell-group>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { postProjection, type ProjectionResponse } from '@/api/timeMachine'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer])

const { t } = useI18n()

const projectionYears = ref(5)
const inflationRate = ref(0.03)
const loading = ref(false)
const result = ref<ProjectionResponse | null>(null)
const hasData = ref(false)
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

onUnmounted(() => {
  chartInstance?.dispose()
  chartInstance = null
})

async function calculate() {
  loading.value = true
  try {
    const res = await postProjection({
      projection_years: projectionYears.value,
      inflation_rate: inflationRate.value,
    })
    result.value = res.data
    hasData.value = true
    await nextTick()
    renderChart(res.data)
  } catch {
    showToast(t('toast.timeMachineError'))
  } finally {
    loading.value = false
  }
}

function renderChart(data: ProjectionResponse) {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)

  const allPoints = [...data.history, ...data.forecast]
  const years = allPoints.map((p) => `${p.year}`)
  const nominal = allPoints.map((p) => p.net_worth)
  const real = allPoints.map((p) => p.real_net_worth)
  const historyLen = data.history.length

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('timeMachine.nominal'), t('timeMachine.realValue')] },
    grid: { left: 60, right: 20, bottom: 30 },
    xAxis: { type: 'category', data: years },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => `${(v / 10000).toFixed(0)}${t('common.unitTenThousand')}` },
    },
    series: [
      {
        name: t('timeMachine.nominal'),
        type: 'line',
        data: nominal,
        smooth: true,
        areaStyle: { opacity: 0.1 },
        markLine:
          historyLen > 0
            ? { data: [{ xAxis: historyLen - 1 }], label: { formatter: t('timeMachine.today') } }
            : undefined,
      },
      {
        name: t('timeMachine.realValue'),
        type: 'line',
        data: real,
        smooth: true,
        lineStyle: { type: 'dashed' },
      },
    ],
  })
}
</script>

<style scoped>
.params {
  margin-bottom: 12px;
}
.calc-btn-wrap {
  padding: 0 16px 16px;
}
.chart-container {
  width: 100%;
  height: 300px;
  margin: 16px 0;
}
.summary-card {
  margin: 0 16px 16px;
  padding: 16px;
  background: var(--van-background-2);
  border-radius: 12px;
  font-size: 14px;
  color: var(--van-text-color-2);
}
.assumptions {
  margin-top: 12px;
}
</style>
