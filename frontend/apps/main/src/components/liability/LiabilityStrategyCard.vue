<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import type { Liability } from '@/types'

const props = defineProps<{ liabilities: Liability[] }>()
const router = useRouter()
const { t } = useI18n()
const { format } = useCurrency()

// spec §6.2: only render when ≥2 active liabilities.
const activeLiabilities = computed(() => (props.liabilities || []).filter((l) => l.is_active))
const shouldRender = computed(() => activeLiabilities.value.length >= 2)

// Client-side monthly-interest sum (remaining × monthly_rate) for the two
// payoff strategies. This is an approximation of total interest — keep the UI
// honest ("估算"). Avoids N /liabilities/simulate calls.
function monthlyInterest(l: Liability): number {
  const rate = (l.interest_rate ?? 0) / 100 / 12
  return (l.remaining_amount ?? 0) * rate
}

// 雪崩法 (avalanche): rate desc — pay highest-rate first.
const avalancheOrder = computed(() =>
  [...activeLiabilities.value].sort((a, b) => (b.interest_rate ?? 0) - (a.interest_rate ?? 0)),
)
// 雪球法 (snowball): remaining asc — pay smallest balance first.
const snowballOrder = computed(() =>
  [...activeLiabilities.value].sort((a, b) => (a.remaining_amount ?? 0) - (b.remaining_amount ?? 0)),
)

// Estimated total interest over the payoff period (sum of per-liability monthly
// interest × approximate months). Approximation only — the real payoff schedule
// shrinks balance each month; this is an upper-bound estimate for comparison.
function estimateTotalInterest(order: Liability[]): number {
  return order.reduce((sum, l) => {
    const mi = monthlyInterest(l)
    const months = l.monthly_payment && l.monthly_payment > mi
      ? Math.ceil((l.remaining_amount ?? 0) / (l.monthly_payment - mi))
      : 0
    return sum + mi * months
  }, 0)
}

const avalancheInterest = computed(() => estimateTotalInterest(avalancheOrder.value))
const snowballInterest = computed(() => estimateTotalInterest(snowballOrder.value))
const savedByAvalanche = computed(() => Math.max(0, snowballInterest.value - avalancheInterest.value))

const adopted = ref(false)
const ADOPT_KEY = 'liability_strategy_adopted_avalanche'

function adoptAvalanche() {
  localStorage.setItem(ADOPT_KEY, '1')
  adopted.value = true
  showSuccessToast(t('liability.strategy.adopted'))
}

function askAi() {
  router.push({ name: 'AIChat', query: { source: 'liability_strategy' } })
}
</script>

<template>
  <div v-if="shouldRender" class="liability-strategy-card strategy-card">
    <div class="strat-header">
      <span class="strat-title">{{ t('liability.strategy.title') }}</span>
    </div>
    <div class="strat-row">
      <div class="strat-method">
        <div class="strat-method-name">{{ t('liability.strategy.avalanche') }}</div>
        <div class="strat-method-desc">{{ t('liability.strategy.avalancheDesc') }}</div>
        <div class="strat-interest">≈ ¥{{ format(avalancheInterest) }}</div>
      </div>
      <div class="strat-method">
        <div class="strat-method-name">{{ t('liability.strategy.snowball') }}</div>
        <div class="strat-method-desc">{{ t('liability.strategy.snowballDesc') }}</div>
        <div class="strat-interest">≈ ¥{{ format(snowballInterest) }}</div>
      </div>
    </div>
    <div v-if="savedByAvalanche > 0" class="strat-save">
      {{ t('liability.strategy.saveEstimate', { amount: format(savedByAvalanche) }) }}
    </div>
    <div class="strat-actions">
      <van-button size="small" type="primary" :disabled="adopted" @click="adoptAvalanche">
        {{ adopted ? t('liability.strategy.adopted') : t('liability.strategy.adopt') }}
      </van-button>
      <van-button size="small" plain @click="askAi">{{ t('liability.strategy.askAi') }}</van-button>
    </div>
  </div>
</template>

<style scoped>
.strategy-card {
  margin: 8px 16px;
  padding: 12px;
  background: var(--card-bg, #fff);
  border-radius: 10px;
}
.strat-header {
  margin-bottom: 8px;
}
.strat-title {
  font-weight: 600;
  font-size: 14px;
}
.strat-row {
  display: flex;
  gap: 8px;
}
.strat-method {
  flex: 1;
  padding: 8px;
  background: var(--bg-secondary, #f7f8fa);
  border-radius: 8px;
}
.strat-method-name {
  font-size: 13px;
  font-weight: 600;
}
.strat-method-desc {
  font-size: 11px;
  color: var(--text-secondary, #969799);
  margin: 2px 0 4px;
}
.strat-interest {
  font-size: 13px;
  color: var(--color-primary, #6366f1);
  font-weight: 500;
}
.strat-save {
  font-size: 12px;
  color: #07c160;
  margin-top: 6px;
}
.strat-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
