<template>
  <div class="whatif-simulator">
    <div class="action-list">
      <div v-for="(action, idx) in actions" :key="idx" class="action-item">
        <van-cell-group inset>
          <van-field
            :model-value="actionTypeLabel(action.action_type)"
            is-link
            readonly
            :label="t('timeMachine.actionType')"
            @click="showActionTypePicker(idx)"
          />
          <van-field
            v-if="action.action_type === 'invest' || action.action_type === 'buy'"
            v-model.number="action.amount"
            type="number"
            :label="t('timeMachine.amountYuan')"
          />
          <van-field
            v-if="action.action_type === 'invest'"
            v-model.number="action.annual_return_rate"
            type="number"
            :label="t('timeMachine.annualReturnRate')"
            placeholder="0.08"
          />
        </van-cell-group>
        <div class="action-delete-wrap">
          <van-button
            v-if="actions.length > 1"
            size="small"
            plain
            type="danger"
            @click="actions.splice(idx, 1)"
          >
            {{ t('common.delete') }}
          </van-button>
        </div>
      </div>
      <van-button
        v-if="actions.length < 5"
        block
        plain
        type="primary"
        size="small"
        class="add-btn"
        @click="addAction"
      >
        {{ t('timeMachine.addAction') }}
      </van-button>
    </div>

    <van-cell-group inset class="params">
      <van-field
        v-model.number="projectionYears"
        type="number"
        :label="t('timeMachine.projectionYears')"
      />
    </van-cell-group>

    <div class="calc-btn-wrap">
      <van-button round block type="primary" :loading="loading" @click="calculate">
        {{ t('timeMachine.calculate') }}
      </van-button>
    </div>

    <div v-if="chartReady" ref="chartRef" class="whatif-chart" />

    <div v-if="result" class="result-summary">
      <van-cell
        :title="t('timeMachine.totalDifference')"
        :value="formatDiff(result.total_difference)"
        :value-class="result.total_difference >= 0 ? 'positive' : 'negative'"
      />
      <van-cell
        v-if="result.breakeven_year !== null"
        :title="t('timeMachine.breakeven')"
        :value="t('timeMachine.breakevenYear', { year: result.breakeven_year })"
      />
    </div>

    <div v-if="result?.summary" class="summary-card">
      <p>{{ result.summary }}</p>
    </div>

    <!-- Action type picker -->
    <van-action-sheet
      v-model:show="pickerVisible"
      :actions="actionTypeOptions"
      :cancel-text="t('common.cancel')"
      @select="onActionTypeSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showFailToast } from 'vant'
import { postWhatIf, type WhatIfAction, type WhatIfResponse } from '@/api/timeMachine'
import { useCurrency } from '@/composables/useCurrency'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const { t } = useI18n()
const currency = useCurrency()

const actions = ref<WhatIfAction[]>([{ action_type: 'invest', annual_return_rate: 0.06 }])
const projectionYears = ref(10)
const loading = ref(false)
const result = ref<WhatIfResponse | null>(null)
const chartReady = ref(false)
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

onUnmounted(() => {
  chartInstance?.dispose()
  chartInstance = null
})

const pickerVisible = ref(false)
const pickerTargetIdx = ref(0)

const actionTypeOptions = computed(() => [
  { name: t('timeMachine.sell'), value: 'sell' },
  { name: t('timeMachine.buy'), value: 'buy' },
  { name: t('timeMachine.invest'), value: 'invest' },
  { name: t('timeMachine.stopExpense'), value: 'stop_expense' },
])

function actionTypeLabel(type: string) {
  return actionTypeOptions.value.find((o: { name: string; value: string }) => o.value === type)?.name ?? type
}

function addAction() {
  if (actions.value.length < 5) {
    actions.value.push({ action_type: 'invest', annual_return_rate: 0.06 })
  }
}

function showActionTypePicker(idx: number) {
  pickerTargetIdx.value = idx
  pickerVisible.value = true
}

function onActionTypeSelect(item: { name: string; value: string }) {
  actions.value[pickerTargetIdx.value] = { action_type: item.value as WhatIfAction['action_type'] }
  pickerVisible.value = false
}

function formatDiff(v: number) {
  const sign = v >= 0 ? '+' : '-'
  return `${sign}${currency.format(Math.abs(v))}`
}

async function calculate() {
  loading.value = true
  try {
    const res = await postWhatIf({
      actions: actions.value,
      projection_years: projectionYears.value,
    })
    result.value = res.data
    chartReady.value = true
    await nextTick()
    renderChart(res.data)
  } catch {
    showFailToast(t('toast.timeMachineError'))
  } finally {
    loading.value = false
  }
}

function renderChart(data: WhatIfResponse) {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('timeMachine.baseline'), t('timeMachine.scenario')] },
    grid: { left: 60, right: 20, bottom: 30 },
    xAxis: { type: 'category', data: data.projection.map((p) => t('timeMachine.yearUnit', { year: p.year })) },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: (v: number) => `${(v / 10000).toFixed(0)}${t('common.unitTenThousand')}` },
    },
    series: [
      {
        name: t('timeMachine.baseline'),
        type: 'line',
        data: data.projection.map((p) => p.baseline_net_worth),
        smooth: true,
      },
      {
        name: t('timeMachine.scenario'),
        type: 'line',
        data: data.projection.map((p) => p.scenario_net_worth),
        smooth: true,
        lineStyle: { type: 'dashed' },
      },
    ],
  })
}
</script>

<style scoped>
.action-item {
  margin-bottom: 8px;
}
.action-delete-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 4px 16px 0;
}
.add-btn {
  margin: 8px 16px;
  width: calc(100% - 32px);
}
.params {
  margin-top: 12px;
}
.calc-btn-wrap {
  padding: 16px;
}
.whatif-chart {
  width: 100%;
  height: 300px;
  margin: 16px 0;
}
.result-summary {
  margin: 0 16px;
}
:deep(.positive) {
  color: #10b981;
  font-weight: 600;
}
:deep(.negative) {
  color: #ef4444;
  font-weight: 600;
}
.summary-card {
  margin: 12px 16px 16px;
  padding: 16px;
  background: var(--van-background-2);
  border-radius: 12px;
  font-size: 14px;
  color: var(--van-text-color-2);
}
</style>
