<template>
  <div class="overview-stat-card">
    <!-- Net worth hero -->
    <div class="osc-main">
      <!-- Faded upward-growth arrow watermark on the right — visual beacon for the trend entry -->
      <svg class="trend-watermark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M3 17L9 11L13 15L21 7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M15 7H21V13" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <div class="osc-label">{{ t('dashboard.netWorth') }}</div>
      <div class="osc-amount">
        <MoneyDisplay :amount="overview?.net_worth ?? 0" size="large" />
        <router-link to="/dashboard/analytics" class="trend-entry" data-test="trend-entry" :aria-label="t('analyticsPage.trendEntry')">
          <svg class="trend-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M2 12L5.5 8.5L8 11L14 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M10 4H14V8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="trend-text">{{ t('analyticsPage.trendEntry') }}</span>
        </router-link>
      </div>
      <div class="osc-sub-row">
        <span v-if="(overview?.total_daily_cost ?? 0) > 0" class="osc-daily">
          {{ t('dashboard.dailyCost') }} {{ currency.format(overview?.total_daily_cost ?? 0) }}
        </span>
        <span class="osc-count">{{ t('dashboard.assetCount', { count: overview?.asset_count ?? 0 }) }}</span>
        <span v-if="overview?.month_over_month_change != null" class="osc-change" :class="changeClass">
          {{ changeText }} {{ t('dashboard.monthChange') }}
        </span>
      </div>
    </div>

    <!-- Sub-stat grid (2×2): each drills down into a finance tab -->
    <div class="osc-detail">
      <!-- 总资产 → assets -->
      <router-link :to="{ path: '/finance', query: { tab: 'assets' } }" class="osc-item" data-test="stat-assets" :aria-label="t('dashboard.netWorthDrilldown')">
        <div class="osc-item-label">{{ t('dashboard.totalAssets') }}</div>
        <div class="osc-item-value">
          <MoneyDisplay :amount="overview?.total_assets ?? 0" />
        </div>
      </router-link>

      <!-- 总负债 → liabilities -->
      <router-link :to="{ path: '/finance', query: { tab: 'liabilities' } }" class="osc-item" data-test="stat-liabilities" :aria-label="t('dashboard.totalLiabilitiesDrilldown')">
        <div class="osc-item-label">{{ t('dashboard.totalLiabilities') }}</div>
        <div class="osc-item-value">
          <MoneyDisplay :amount="overview?.total_liabilities ?? 0" />
        </div>
      </router-link>

      <!-- 月还 → liabilities (estimate tag when any active liability lacks monthly_payment) -->
      <router-link :to="{ path: '/finance', query: { tab: 'liabilities' } }" class="osc-item" data-test="stat-monthly" :aria-label="t('financeHub.monthlyPayment')">
        <div class="osc-item-label">
          {{ t('financeHub.monthlyPayment') }}
          <span v-if="!liabilityLoading && !liabilityError && monthlyPaymentIsEstimate" class="osc-estimate-tag" data-test="monthly-estimate">
            {{ t('financeHub.estimate') }}
          </span>
        </div>
        <div class="osc-item-value">
          <van-skeleton v-if="liabilityLoading" :row="1" row-width="60%" animate data-test="monthly-skeleton" />
          <button v-else-if="liabilityError" class="osc-retry" data-test="monthly-retry" @click.prevent="retryLiabilities">
            {{ t('financeHub.retry') }}
          </button>
          <MoneyDisplay v-else :amount="monthlyPaymentTotal" />
        </div>
      </router-link>

      <!-- 心愿进度 → wishes -->
      <router-link :to="{ path: '/finance', query: { tab: 'wishes' } }" class="osc-item" data-test="stat-wishes" :aria-label="t('financeHub.wishProgress')">
        <div class="osc-item-label">{{ t('financeHub.wishProgress') }}</div>
        <div class="osc-item-value">
          <van-skeleton v-if="wishLoading" :row="1" row-width="60%" animate data-test="wish-skeleton" />
          <button v-else-if="wishError" class="osc-retry" data-test="wish-retry" @click.prevent="retryWishes">
            {{ t('financeHub.retry') }}
          </button>
          <div v-else class="wish-progress-wrap">
            <div class="wish-progress-bar">
              <div class="wish-progress-fill" :style="{ width: `${wishProgressPercent}%` }" />
            </div>
            <span class="wish-progress-text">{{ t('financeHub.wishCount', { count: wishCount }) }}</span>
          </div>
        </div>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import { useCurrency } from '@/composables/useCurrency'
import { useMonthlyPaymentTotal } from '@/composables/useMonthlyPaymentTotal'
import { useDashboardStore } from '@/stores/dashboard'
import { useLiabilityStore } from '@/stores/liability'
import { useWishStore } from '@/stores/wish'

const { t } = useI18n()
const currency = useCurrency()
const dashboardStore = useDashboardStore()
const liabilityStore = useLiabilityStore()
const wishStore = useWishStore()

const overview = computed(() => dashboardStore.overview)
const liabilities = computed(() => liabilityStore.liabilities)
const wishes = computed(() => wishStore.wishes)

// Per-domain loading / error. Stores expose only `loading` (fetch throws on failure),
// so error is tracked here by catching the fetch rejection.
const liabilityLoading = ref(false)
const wishLoading = ref(false)
const liabilityError = ref(false)
const wishError = ref(false)

// --- Net worth change badge (mirrors NetWorthCard) ---
const changeClass = computed(() => ((overview.value?.month_over_month_change || 0) >= 0 ? 'positive' : 'negative'))
const changeText = computed(() => {
  const pct = overview.value?.month_over_month_change || 0
  const arrow = pct >= 0 ? '↑' : '↓'
  let text = `${arrow} ${Math.abs(pct).toFixed(1)}%`
  const amt = overview.value?.month_over_month_change_amount
  if (amt != null && amt !== 0) {
    const sign = amt > 0 ? '+' : '-'
    text += ` ${sign}${currency.format(Math.abs(amt))}`
  }
  return text
})

// --- Monthly payment total + estimate tag ---
const { activeLiabilities, monthlyPaymentTotal, monthlyPaymentIsEstimate } = useMonthlyPaymentTotal(() => liabilities.value)

// --- Wish progress (ported from FinanceHubPage): sum(saved)/sum(expected), cap 100 ---
const wishCount = computed(() => (wishes.value || []).length)
const wishProgressPercent = computed(() => {
  const expected = (wishes.value || []).reduce((sum, w) => sum + (Number(w.expected_price ?? 0) || 0), 0)
  if (expected <= 0) return 0
  const saved = (wishes.value || []).reduce((sum, w) => sum + (Number(w.saved_amount ?? 0) || 0), 0)
  return Math.min(100, Math.round((saved / expected) * 100))
})

async function loadLiabilities() {
  liabilityLoading.value = true
  liabilityError.value = false
  try {
    await liabilityStore.fetchLiabilities()
  } catch {
    liabilityError.value = true
  } finally {
    liabilityLoading.value = false
  }
}

async function loadWishes() {
  wishLoading.value = true
  wishError.value = false
  try {
    await wishStore.fetchWishes()
  } catch {
    wishError.value = true
  } finally {
    wishLoading.value = false
  }
}

function retryLiabilities() {
  loadLiabilities()
}
function retryWishes() {
  loadWishes()
}

onMounted(() => {
  // This card is the first to bring liability/wish data onto the overview page;
  // fetch each domain independently so a single failure degrades only its own stat.
  loadLiabilities()
  loadWishes()
})
</script>

<style scoped>
.overview-stat-card {
  background: var(--card-bg);
  padding: 20px 16px 16px;
  color: var(--text-primary);
  position: relative;
  overflow: hidden;
}

.osc-main {
  display: flex;
  flex-direction: column;
}
.osc-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: var(--text-tertiary);
  font-family: 'Georgia', monospace;
}
.osc-amount {
  margin: 6px 0 8px;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.osc-amount :deep(.money-display) {
  color: var(--text-primary);
  font-size: clamp(28px, 8vw, 36px);
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1.05;
}

/* Faded upward-growth arrow on the right — beckons the eye toward the trend entry */
.trend-watermark {
  position: absolute;
  top: -16px;
  right: -8px;
  width: 108px;
  height: 108px;
  color: var(--color-primary);
  opacity: 0.07;
  z-index: 0;
  pointer-events: none;
}
[data-theme='dark'] .trend-watermark {
  color: var(--color-lavender);
  opacity: 0.12;
}

/* Trend entry: icon + text, flex item aligned right */
.trend-entry {
  display: flex;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  transition: background 0.15s ease;
  position: relative;
  overflow: hidden;
}
.trend-entry:active {
  transform: scale(0.95);
}

/* Icon + text sit above the sweeping highlight */
.trend-entry > * {
  position: relative;
  z-index: 1;
}

/* Shimmer — shadow sweep in light mode, highlight sweep in dark mode */
.trend-entry::after {
  content: '';
  position: absolute;
  top: 0;
  left: -150%;
  width: 80%;
  height: 100%;
  background: linear-gradient(
    100deg,
    transparent 0%,
    rgba(0, 0, 0, 0.06) 30%,
    rgba(0, 0, 0, 0.15) 50%,
    rgba(0, 0, 0, 0.06) 70%,
    transparent 100%
  );
  transform: skewX(-20deg);
  animation: trend-entry-shimmer 3.6s ease-in-out infinite;
  pointer-events: none;
  z-index: 0;
}
[data-theme='dark'] .trend-entry::after {
  background: linear-gradient(
    100deg,
    transparent 0%,
    rgba(255, 255, 255, 0.1) 30%,
    rgba(255, 255, 255, 0.32) 50%,
    rgba(255, 255, 255, 0.1) 70%,
    transparent 100%
  );
}

@keyframes trend-entry-shimmer {
  0% {
    left: -150%;
  }
  50% {
    left: 180%;
  }
  100% {
    left: 180%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .trend-entry::after {
    animation: none;
  }
}

.trend-icon {
  width: 16px;
  height: 16px;
  color: var(--text-secondary);
}

.trend-text {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

/* Responsive fallback: stack on very narrow screens */
@media (max-width: 320px) {
  .osc-amount {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .trend-entry {
    align-self: flex-end;
  }
}

.osc-sub-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.osc-daily {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--color-card-border);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
.osc-count {
  font-size: 13px;
  color: var(--text-tertiary);
}
.osc-change.positive {
  color: #059669;
  font-weight: 500;
}
[data-theme='dark'] .osc-change.positive {
  color: var(--color-trend-down);
}
.osc-change.negative {
  color: #dc2626;
  font-weight: 500;
}
[data-theme='dark'] .osc-change.negative {
  color: var(--color-trend-up);
}

/* Sub-stat grid: 2×2 on mobile so each metric gets a comfortable cell width. */
.osc-detail {
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  border-radius: 8px;
  margin-top: 12px;
  overflow: hidden;
}

.osc-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 64px;
  padding: 12px 8px;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.15s ease;
}
.osc-item:active {
  transform: scale(0.97);
}
/* Hairline separators between the 2×2 cells (right column + bottom row). */
.osc-item:nth-child(odd) {
  border-right: 1px solid var(--separator);
}
.osc-item:nth-child(-n + 2) {
  border-bottom: 1px solid var(--separator);
}

.osc-item-label {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  flex-wrap: wrap;
}
.osc-item-value {
  min-height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.osc-item-value :deep(.money-display) {
  color: var(--text-primary);
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.16px;
}

.osc-estimate-tag {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--color-warning-light, #fff7e6);
  color: var(--color-warning, #ff976a);
  text-transform: none;
}

.osc-retry {
  background: none;
  border: 1px solid currentColor;
  border-radius: 4px;
  color: var(--color-primary);
  font-size: 12px;
  padding: 2px 10px;
  cursor: pointer;
}

.wish-progress-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 100%;
}
.wish-progress-bar {
  width: 80%;
  max-width: 120px;
  height: 6px;
  background: var(--bg-secondary, #f7f8fa);
  border-radius: 3px;
  overflow: hidden;
}
.wish-progress-fill {
  height: 100%;
  background: var(--color-primary, #1989fa);
  transition: width 0.3s ease;
}
.wish-progress-text {
  font-size: 12px;
  color: var(--text-secondary, #969799);
  white-space: nowrap;
}
</style>
