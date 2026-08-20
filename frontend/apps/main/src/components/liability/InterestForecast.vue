<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { simulateLiability } from '@/api/liabilities'
import type { Liability, LiabilitySimResult } from '@/types'
import { INFINITE_DATE_SENTINEL } from '@/constants/dates'
import SimulateExtraDialog from './SimulateExtraDialog.vue'

const props = defineProps<{ liability: Liability }>()
const { t } = useI18n()
const { format } = useCurrency()

// spec §6.1 adversarial: hide entirely when interest_rate is null/0.
const shouldRender = () => (props.liability.interest_rate ?? 0) > 0

const repaymentMethod = computed(() => props.liability.repayment_method ?? 'equal_payment')
// Derive total_periods from start_date and end_date (months between them)
const derivedTotalPeriods = computed(() => {
  const start = props.liability.start_date
  const end = props.liability.end_date
  if (!start || !end || end === INFINITE_DATE_SENTINEL) return null
  const startDate = new Date(start)
  const endDate = new Date(end)
  if (isNaN(startDate.getTime()) || isNaN(endDate.getTime()) || endDate <= startDate) return null
  const months = (endDate.getFullYear() - startDate.getFullYear()) * 12 + (endDate.getMonth() - startDate.getMonth())
  return months > 0 ? months : null
})
// Extra-payment scenarios only apply to equal_payment and minimum_payment
const showExtraScenarios = computed(() =>
  repaymentMethod.value === 'equal_payment' || repaymentMethod.value === 'minimum_payment'
)

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
      repayment_method: repaymentMethod.value,
      total_periods: derivedTotalPeriods.value,
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
      baseline.value = await runSim('0')
      if (showExtraScenarios.value) {
        ;[extra500.value, extra1000.value] = await Promise.all([
          runSim('500'),
          runSim('1000'),
        ])
      } else {
        extra500.value = null
        extra1000.value = null
      }
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

// U5: helpers for non-standard repayment methods
const firstScheduleRow = computed(() => baseline.value?.schedule?.[0] ?? null)
const lastScheduleRow = computed(() => {
  const s = baseline.value?.schedule
  return s && s.length > 0 ? s[s.length - 1] : null
})
</script>

<template>
  <div v-if="shouldRender()" class="interest-forecast">
    <div class="if-title">{{ t('liability.interest.title') }}</div>
    <van-loading v-if="loading" />
    <template v-else-if="baseline">
      <!-- equal_payment / minimum_payment: existing 3-scenario display -->
      <template v-if="showExtraScenarios">
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.totalInterest') }}</span>
          <span class="if-value">{{ format(Number(baseline.total_interest)) }}</span>
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

      <!-- equal_principal: first/last monthly payment range + total interest -->
      <template v-else-if="repaymentMethod === 'equal_principal'">
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.totalInterest') }}</span>
          <span class="if-value">{{ format(Number(baseline.total_interest)) }}</span>
        </div>
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.monthsLeft') }}</span>
          <span class="if-value">{{ baseline.months }} {{ t('liability.interest.monthsUnit') }}</span>
        </div>
        <div v-if="firstScheduleRow && lastScheduleRow" class="if-range-row">
          <span class="if-label">{{ t('liability.interest.paymentRange') }}</span>
          <span class="if-value">
            {{ format(Number(firstScheduleRow.payment)) }} → {{ format(Number(lastScheduleRow.payment)) }}
          </span>
        </div>
      </template>

      <!-- interest_only: monthly interest + bullet principal -->
      <template v-else-if="repaymentMethod === 'interest_only'">
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.totalInterest') }}</span>
          <span class="if-value">{{ format(Number(baseline.total_interest)) }}</span>
        </div>
        <div v-if="firstScheduleRow" class="if-row">
          <span class="if-label">{{ t('liability.interest.monthlyInterest') }}</span>
          <span class="if-value">{{ format(Number(firstScheduleRow.interest)) }}</span>
        </div>
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.bulletPrincipal') }}</span>
          <span class="if-value">{{ format(Number(liability.remaining_amount)) }}</span>
        </div>
      </template>

      <!-- bullet: single lump sum at maturity -->
      <template v-else-if="repaymentMethod === 'bullet'">
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.totalInterest') }}</span>
          <span class="if-value">{{ format(Number(baseline.total_interest)) }}</span>
        </div>
        <div v-if="lastScheduleRow" class="if-row">
          <span class="if-label">{{ t('liability.interest.bulletTotal') }}</span>
          <span class="if-value">{{ format(Number(lastScheduleRow.payment)) }}</span>
        </div>
      </template>

      <!-- fallback: other methods (e.g. minimum_payment already handled above) -->
      <template v-else>
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.totalInterest') }}</span>
          <span class="if-value">{{ format(Number(baseline.total_interest)) }}</span>
        </div>
        <div class="if-row">
          <span class="if-label">{{ t('liability.interest.monthsLeft') }}</span>
          <span class="if-value">{{ baseline.months }} {{ t('liability.interest.monthsUnit') }}</span>
        </div>
      </template>
    </template>
    <SimulateExtraDialog v-if="showExtraScenarios" v-model:show="showSimulate" :liability="liability" :baseline="baseline" />
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
.if-range-row {
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
