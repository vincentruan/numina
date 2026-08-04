<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { useFamilyStore } from '@/stores/family'
import type { Liability } from '@/types'

const props = defineProps<{ liabilities: Liability[] }>()
const emit = defineEmits<{ (e: 'adopt', strategy: 'avalanche' | 'snowball' | null): void }>()
const router = useRouter()
const { t } = useI18n()
const { format } = useCurrency()
const familyStore = useFamilyStore()

// spec §6.2: only render when ≥2 active liabilities.
const activeLiabilities = computed(() => (props.liabilities || []).filter((l) => l.is_active))
const shouldRender = computed(() => activeLiabilities.value.length >= 2)

// Client-side monthly-interest sum (remaining × monthly_rate) for the two
// payoff strategies. This is an approximation of total interest — keep the UI
// honest ("估算"). Avoids N /liabilities/simulate calls.
function monthlyInterest(l: Liability): number {
  const rate = (l.interest_rate ?? 0) / 100 / 12
  return Number(l.remaining_amount ?? 0) * rate
}

// 雪崩法 (avalanche): rate desc — pay highest-rate first.
const avalancheOrder = computed(() =>
  [...activeLiabilities.value].sort((a, b) => (b.interest_rate ?? 0) - (a.interest_rate ?? 0)),
)
// 雪球法 (snowball): remaining asc — pay smallest balance first.
const snowballOrder = computed(() =>
  [...activeLiabilities.value].sort((a, b) => Number(a.remaining_amount ?? 0) - Number(b.remaining_amount ?? 0)),
)

// Estimated total interest over the payoff period (sum of per-liability monthly
// interest × approximate months). Approximation only — the real payoff schedule
// shrinks balance each month; this is an upper-bound estimate for comparison.
function estimateTotalInterest(order: Liability[]): number {
  return order.reduce((sum, l) => {
    const mi = monthlyInterest(l)
    const mp = Number(l.monthly_payment ?? 0)
    const months = mp && mp > mi
      ? Math.ceil(Number(l.remaining_amount ?? 0) / (mp - mi))
      : 0
    return sum + mi * months
  }, 0)
}

const avalancheInterest = computed(() => estimateTotalInterest(avalancheOrder.value))
const snowballInterest = computed(() => estimateTotalInterest(snowballOrder.value))
// Avalanche is the recommended method; savings shown relative to snowball.
const savedByAvalanche = computed(() => Math.max(0, snowballInterest.value - avalancheInterest.value))

// --- Adoption state (persisted in localStorage) ---
const ADOPT_KEY = 'liability_strategy_adopted'
const OLD_ADOPT_KEY = 'liability_strategy_adopted_avalanche' // Legacy key for migration
const adoptedStrategy = ref<'avalanche' | 'snowball' | null>(null)

onMounted(() => {
  // Migrate from old key (avalanche-only) to new key (avalanche/snowball)
  const oldStored = localStorage.getItem(OLD_ADOPT_KEY)
  if (oldStored === '1') {
    localStorage.setItem(ADOPT_KEY, 'avalanche')
    localStorage.removeItem(OLD_ADOPT_KEY)
  }

  const stored = localStorage.getItem(ADOPT_KEY)
  if (stored === 'avalanche' || stored === 'snowball') {
    adoptedStrategy.value = stored
    nextTick(() => emit('adopt', stored))
  }
})

function adoptStrategy(strategy: 'avalanche' | 'snowball') {
  localStorage.setItem(ADOPT_KEY, strategy)
  adoptedStrategy.value = strategy
  emit('adopt', strategy)
  showSuccessToast(t('liability.strategy.adopted'))
}

function resetStrategy() {
  localStorage.removeItem(ADOPT_KEY)
  adoptedStrategy.value = null
  emit('adopt', null)
}

function askAi() {
  if (!familyStore.aiEnabled) return
  router.push({ name: 'AIChat', query: { source: 'liability_strategy' } })
}
</script>

<template>
  <div v-if="shouldRender" class="liability-strategy-card strategy-card">
    <div class="strat-header">
      <span class="strat-title">{{ t('liability.strategy.title') }}</span>
      <span class="strat-subtitle">{{ t('liability.strategy.subtitle', { count: activeLiabilities.length }) }}</span>
    </div>

    <!-- Adopted state: single-line summary + change link -->
    <div v-if="adoptedStrategy" class="strat-adopted">
      <span class="strat-adopted-text">
        {{ t('liability.strategy.currentStrategy') }}:
        <strong>{{ adoptedStrategy === 'avalanche' ? t('liability.strategy.avalanche') : t('liability.strategy.snowball') }}</strong>
        <van-icon name="success" class="strat-adopted-check" />
      </span>
      <a class="strat-change-link" role="button" tabindex="0" @click="resetStrategy" @keydown.enter.prevent="resetStrategy">
        {{ t('liability.strategy.changeStrategy') }}
      </a>
    </div>

    <!-- Comparison state: two methods stacked, recommended highlighted -->
    <template v-else>
      <div class="strat-row">
        <div class="strat-method strat-method--recommended">
          <div class="strat-method-header">
            <span class="strat-method-name">{{ t('liability.strategy.avalanche') }}</span>
            <span class="strat-badge">{{ t('liability.strategy.recommended') }}</span>
          </div>
          <div class="strat-method-desc">{{ t('liability.strategy.avalancheDesc') }}</div>
          <div class="strat-interest">≈ {{ format(avalancheInterest) }}</div>
        </div>
        <div class="strat-method">
          <div class="strat-method-name">{{ t('liability.strategy.snowball') }}</div>
          <div class="strat-method-desc">{{ t('liability.strategy.snowballDesc') }}</div>
          <div class="strat-interest">≈ {{ format(snowballInterest) }}</div>
        </div>
      </div>
      <div v-if="savedByAvalanche > 0" class="strat-save">
        {{ t('liability.strategy.saveByAvalanche', { amount: format(savedByAvalanche) }) }}
      </div>
      <div class="strat-actions">
        <van-button size="small" type="primary" @click="adoptStrategy('avalanche')">
          {{ t('liability.strategy.adoptBySort') }}
        </van-button>
        <van-button size="small" plain @click="adoptStrategy('snowball')">
          {{ t('liability.strategy.adoptSnowball') }}
        </van-button>
        <van-button
          size="small"
          plain
          :disabled="!familyStore.aiEnabled"
          @click="askAi"
        >
          {{ t('liability.strategy.askAi') }}
        </van-button>
        <span
          v-if="!familyStore.aiEnabled"
          class="strat-ai-disabled-hint"
          role="note"
          aria-label="AI 助手未启用"
        >
          {{ t('liability.strategy.askAiDisabledHint') }}
        </span>
      </div>
    </template>
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
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.strat-title {
  font-weight: 600;
  font-size: 14px;
}
.strat-subtitle {
  font-size: 12px;
  color: var(--text-secondary, #969799);
}
.strat-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.strat-method {
  padding: 8px 10px;
  background: var(--bg-secondary, #f7f8fa);
  border-radius: 8px;
}
.strat-method--recommended {
  border-left: 3px solid var(--color-coral, #ff6b6b);
}
.strat-method-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.strat-method-name {
  font-size: 13px;
  font-weight: 600;
}
.strat-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--color-coral, #ff6b6b);
  color: #fff;
  font-weight: 500;
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
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.strat-ai-disabled-hint {
  font-size: 11px;
  color: var(--text-tertiary, #c8c9cc);
}
.strat-adopted {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
}
.strat-adopted-text {
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.strat-adopted-check {
  color: #07c160;
}
.strat-change-link {
  font-size: 12px;
  color: var(--color-primary, #6366f1);
  cursor: pointer;
}
</style>
