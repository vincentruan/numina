<template>
  <div v-if="overview" class="finance-summary-bar" role="group" :aria-label="t('financeHub.summaryBarAria')">
    <!-- Net worth → assets tab -->
    <div
      class="summary-item"
      role="button"
      tabindex="0"
      :aria-label="t('financeHub.summaryNetWorthAria', { value: currency.format(overview.net_worth) })"
      data-test="summary-net-worth"
      @click="emit('navigate', 'assets')"
      @keydown.enter.prevent="emit('navigate', 'assets')"
      @keydown.space.prevent="emit('navigate', 'assets')"
    >
      <span class="summary-label">{{ t('financeHub.netWorth') }}</span>
      <span class="summary-value summary-value--primary">
        <MoneyDisplay :amount="overview.net_worth" />
      </span>
    </div>

    <!-- Liability ratio → liabilities tab -->
    <div
      class="summary-item"
      role="button"
      tabindex="0"
      :aria-label="t('financeHub.summaryLiabilityRatioAria', { value: liabilityRatioDisplay })"
      data-test="summary-liability-ratio"
      @click="emit('navigate', 'liabilities')"
      @keydown.enter.prevent="emit('navigate', 'liabilities')"
      @keydown.space.prevent="emit('navigate', 'liabilities')"
    >
      <span class="summary-label">{{ t('financeHub.liabilityRatio') }}</span>
      <span class="summary-value">{{ liabilityRatioDisplay }}</span>
    </div>

    <!-- Monthly payment → liabilities tab -->
    <div
      class="summary-item"
      role="button"
      tabindex="0"
      :aria-label="t('financeHub.summaryMonthlyPaymentAria', { value: currency.format(monthlyPaymentTotal) })"
      data-test="summary-monthly-payment"
      @click="emit('navigate', 'liabilities')"
      @keydown.enter.prevent="emit('navigate', 'liabilities')"
      @keydown.space.prevent="emit('navigate', 'liabilities')"
    >
      <span class="summary-label">{{ t('financeHub.monthlyPayment') }}</span>
      <span class="summary-value">
        <MoneyDisplay :amount="monthlyPaymentTotal" />
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useLiabilityStore } from '@/stores/liability'
import { useCurrency } from '@/composables/useCurrency'

defineOptions({ name: 'FinanceSummaryBar' })

const emit = defineEmits<{
  navigate: [tab: 'assets' | 'liabilities']
}>()

const { t } = useI18n()
const dashboardStore = useDashboardStore()
const liabilityStore = useLiabilityStore()
const currency = useCurrency()

const overview = computed(() => dashboardStore.overview)

// Liability ratio: total_liabilities / total_assets * 100. Zero-division protection:
// when total_assets is 0 (or negative edge), show '-' instead of NaN/Infinity.
const liabilityRatioDisplay = computed(() => {
  const o = overview.value
  if (!o) return '-'
  const totalAssets = Number(o.total_assets ?? 0)
  if (totalAssets <= 0) return '-'
  const totalLiabilities = Number(o.total_liabilities ?? 0)
  const ratio = (totalLiabilities / totalAssets) * 100
  if (!Number.isFinite(ratio)) return '-'
  return `${ratio.toFixed(1)}%`
})

// Monthly payment total: sum of active liabilities' monthly_payment.
// For liabilities without monthly_payment, estimate from remaining * monthly rate.
// Mirrors OverviewStatCard pattern.
const monthlyPaymentTotal = computed(() => {
  const activeLiabilities = (liabilityStore.liabilities || []).filter((l) => l.is_active)
  return activeLiabilities.reduce((sum, l) => {
    const mp = Number(l.monthly_payment ?? 0)
    if (mp > 0) return sum + mp
    const rate = (l.interest_rate ?? 0) / 100 / 12
    return sum + Number(l.remaining_amount ?? 0) * rate
  }, 0)
})
</script>

<style scoped>
.finance-summary-bar {
  display: flex;
  align-items: stretch;
  height: 60px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--separator);
}

.summary-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  min-width: 44px;
  min-height: 44px;
  cursor: pointer;
  user-select: none;
  transition: background 150ms ease-out;
}

.summary-item:active {
  background: var(--bg-secondary);
}

.summary-item:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.summary-label {
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.2;
}

.summary-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.summary-value--primary {
  color: var(--color-primary);
}
</style>
