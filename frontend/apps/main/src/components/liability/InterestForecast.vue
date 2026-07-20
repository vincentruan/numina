<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { simulateLiability } from '@/api/liabilities'
import type { Liability, LiabilitySimResult } from '@/types'
import SimulateExtraDialog from './SimulateExtraDialog.vue'

const props = defineProps<{ liability: Liability }>()
const { t } = useI18n()
const { format } = useCurrency()

// spec §6.1 adversarial: hide entirely when interest_rate is null/0.
const shouldRender = () => (props.liability.interest_rate ?? 0) > 0

const baseline = ref<LiabilitySimResult | null>(null) // extra=0
const extra500 = ref<LiabilitySimResult | null>(null)
const extra1000 = ref<LiabilitySimResult | null>(null)
const loading = ref(false)
const showSimulate = ref(false)

async function runSim(extra: string): Promise<LiabilitySimResult | null> {
  try {
    const r = await simulateLiability({
      remaining: String(props.liability.remaining_amount),
      annual_rate: String(props.liability.interest_rate),
      monthly_payment: props.liability.monthly_payment ? String(props.liability.monthly_payment) : undefined,
      extra_monthly: extra,
    })
    return r.data
  } catch {
    return null
  }
}

watch(
  () => props.liability?.id,
  async () => {
    if (!shouldRender()) return
    loading.value = true
    try {
      ;[baseline.value, extra500.value, extra1000.value] = await Promise.all([
        runSim('0'),
        runSim('500'),
        runSim('1000'),
      ])
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)
</script>

<template>
  <div v-if="shouldRender()" class="interest-forecast">
    <div class="if-title">{{ t('liability.interest.title') }}</div>
    <van-loading v-if="loading" />
    <template v-else-if="baseline">
      <div class="if-row">
        <span class="if-label">{{ t('liability.interest.totalInterest') }}</span>
        <span class="if-value">¥{{ format(Number(baseline.total_interest)) }}</span>
      </div>
      <div class="if-row">
        <span class="if-label">{{ t('liability.interest.monthsLeft') }}</span>
        <span class="if-value">{{ baseline.months }} {{ t('liability.interest.monthsUnit') }}</span>
      </div>
      <div v-if="baseline.warning" class="if-warning">{{ baseline.warning }}</div>

      <div class="if-extra-scenarios">
        <div class="if-scenario">
          <div class="if-scenario-title">{{ t('liability.interest.extraScenario', { amount: 500 }) }}</div>
          <div v-if="extra500 && extra500.savings_vs_baseline">
            {{ t('liability.interest.savings', { amount: format(Number(extra500.savings_vs_baseline)) }) }}
            <span v-if="extra500.months_saved"> · {{ t('liability.interest.monthsSaved', { n: extra500.months_saved }) }}</span>
          </div>
          <div v-else class="if-na">—</div>
        </div>
        <div class="if-scenario">
          <div class="if-scenario-title">{{ t('liability.interest.extraScenario', { amount: 1000 }) }}</div>
          <div v-if="extra1000 && extra1000.savings_vs_baseline">
            {{ t('liability.interest.savings', { amount: format(Number(extra1000.savings_vs_baseline)) }) }}
            <span v-if="extra1000.months_saved"> · {{ t('liability.interest.monthsSaved', { n: extra1000.months_saved }) }}</span>
          </div>
          <div v-else class="if-na">—</div>
        </div>
      </div>

      <van-button size="small" plain class="if-simulate-btn" @click="showSimulate = true">
        {{ t('liability.interest.simulate') }}
      </van-button>
    </template>
    <SimulateExtraDialog v-model:show="showSimulate" :liability="liability" :baseline="baseline" />
  </div>
</template>

<style scoped>
.interest-forecast {
  margin: 8px 16px;
  padding: 12px;
  background: var(--card-bg, #fff);
  border-radius: 10px;
}
.if-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
}
.if-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin: 4px 0;
}
.if-label {
  color: var(--text-secondary, #969799);
}
.if-value {
  font-weight: 500;
}
.if-warning {
  font-size: 12px;
  color: #ee0a24;
  margin: 4px 0;
}
.if-extra-scenarios {
  display: flex;
  gap: 8px;
  margin: 8px 0;
}
.if-scenario {
  flex: 1;
  padding: 8px;
  background: var(--bg-secondary, #f7f8fa);
  border-radius: 8px;
  font-size: 12px;
}
.if-scenario-title {
  font-weight: 500;
  margin-bottom: 2px;
}
.if-na {
  color: var(--van-text-color-3, #c8c9cc);
}
.if-simulate-btn {
  margin-top: 4px;
}
</style>
