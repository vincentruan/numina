<template>
  <div class="purchasing-power-calc">
    <van-form @submit="calculate">
      <van-cell-group inset>
        <van-field
          v-model.number="form.amount"
          type="number"
          :label="t('timeMachine.amount')"
          placeholder="100000"
          :rules="[{ required: true }]"
        />
        <van-field
          v-model.number="form.fromYear"
          type="number"
          :label="t('timeMachine.fromYear')"
          placeholder="2015"
          :rules="[{ required: true }]"
        />
        <van-field
          v-model.number="form.toYear"
          type="number"
          :label="t('timeMachine.toYear')"
          :placeholder="String(new Date().getFullYear())"
          :rules="[{ required: true }]"
        />
      </van-cell-group>
      <div class="calc-btn-wrap">
        <van-button round block type="primary" native-type="submit" :loading="loading">
          {{ t('timeMachine.calculate') }}
        </van-button>
      </div>
    </van-form>

    <div v-if="result" class="result-card">
      <div class="result-main">
        <span class="result-original">{{ formatMoney(result.original_amount) }}</span>
        <span class="result-arrow">→</span>
        <span class="result-adjusted">{{ formatMoney(result.adjusted_amount) }}</span>
      </div>
      <p class="result-explanation">{{ result.explanation }}</p>
      <div class="result-meta">
        <span>{{ t('timeMachine.cumulativeInflation') }}: {{ result.cumulative_inflation }}%</span>
        <span>{{ t('timeMachine.annualAvg') }}: {{ result.annual_avg_inflation }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { getPurchasingPower, type PurchasingPowerResponse } from '@/api/timeMachine'

const { t } = useI18n()

const form = ref({ amount: 100000, fromYear: 2015, toYear: new Date().getFullYear() })
const loading = ref(false)
const result = ref<PurchasingPowerResponse | null>(null)

function formatMoney(v: number) {
  return `¥${v.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
}

async function calculate() {
  loading.value = true
  try {
    const res = await getPurchasingPower({
      amount: form.value.amount,
      from_year: form.value.fromYear,
      to_year: form.value.toYear,
    })
    result.value = res.data
  } catch {
    showToast(t('toast.timeMachineError'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.calc-btn-wrap {
  padding: 16px;
}
.result-card {
  margin: 16px;
  padding: 20px;
  background: var(--van-background-2);
  border-radius: 12px;
}
.result-main {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
}
.result-arrow {
  color: var(--van-primary-color);
}
.result-adjusted {
  color: var(--van-primary-color);
}
.result-explanation {
  text-align: center;
  color: var(--van-text-color-2);
  margin: 12px 0;
  font-size: 14px;
}
.result-meta {
  display: flex;
  justify-content: space-around;
  font-size: 12px;
  color: var(--van-text-color-3);
}
</style>
