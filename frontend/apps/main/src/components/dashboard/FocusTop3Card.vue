<template>
  <div class="focus-top3-card">
    <van-tabs v-model:active="activeTab" shrink class="top3-tabs">
      <!-- 资产 tab: top 3 by current value -->
      <van-tab :title="t('nav.assets')" name="assets">
        <div class="top3-body">
          <van-skeleton v-if="assetLoading" :row="3" animate data-test="assets-skeleton" />
          <van-empty v-else-if="topAssets.length === 0" :description="t('dashboard.emptyState.noAssets')" image-size="60" />
          <template v-else>
            <AssetListItem
              v-for="asset in topAssets"
              :key="asset.id"
              :asset="asset"
              @click="$router.push(`/assets/${asset.id}`)"
            />
          </template>
          <router-link :to="{ path: '/finance', query: { tab: 'assets' } }" class="top3-view-all" data-test="view-all-assets">
            {{ t('financeHub.viewAll') }} ›
          </router-link>
        </div>
      </van-tab>

      <!-- 负债 tab: top 3 by interest rate -->
      <van-tab :title="t('nav.liabilities')" name="liabilities">
        <div class="top3-body">
          <van-skeleton v-if="liabilityLoading" :row="3" animate data-test="liabilities-skeleton" />
          <button v-else-if="liabilityError" class="top3-retry" data-test="liabilities-retry" @click="retryLiabilities">
            {{ t('financeHub.retry') }}
          </button>
          <van-empty v-else-if="topLiabilities.length === 0" :description="t('focusTop3.noLiabilities')" image-size="60" />
          <template v-else>
            <div
              v-for="liability in topLiabilities"
              :key="liability.id"
              class="top3-liability"
              :class="{ 'top3-liability--highrate': isHighInterest(liability) }"
              role="button"
              tabindex="0"
              :aria-label="liabilityAria(liability)"
              @click="$router.push(`/liabilities/${liability.id}`)"
              @keydown.enter="$router.push(`/liabilities/${liability.id}`)"
            >
              <div class="top3-liability-head">
                <span class="top3-liability-name">{{ liability.name }}</span>
                <span
                  v-if="isHighInterest(liability)"
                  class="top3-liability-tag"
                  :aria-label="t('focusTop3.liabilityHighRate')"
                >
                  <van-icon name="warning-o" />{{ t('focusTop3.liabilityHighRate') }}
                </span>
                <span class="top3-liability-rate">{{ formatRate(liability.interest_rate) }}</span>
              </div>
              <div class="top3-progress-track" :aria-hidden="true">
                <div class="top3-progress-fill top3-progress-fill--debt" :style="{ width: `${liabilityProgress(liability)}%` }" />
              </div>
              <div class="top3-liability-foot">
                <span class="top3-liability-paid">
                  {{ t('focusTop3.liabilityPaid') }}
                  <MoneyDisplay :amount="paidAmount(liability)" />
                </span>
                <MoneyDisplay :amount="Number(liability.remaining_amount ?? 0)" class="top3-liability-amount" />
              </div>
              <div class="top3-liability-meta">
                <span v-if="liabilityProgress(liability) >= 100">{{ t('focusTop3.liabilityCleared') }}</span>
                <span v-else-if="liability.monthly_payment && monthsToClear(liability) > 0">
                  {{ t('focusTop3.liabilityMonthsToClear', { months: monthsToClear(liability) }) }}
                </span>
              </div>
            </div>
          </template>
          <router-link :to="{ path: '/finance', query: { tab: 'liabilities' } }" class="top3-view-all" data-test="view-all-liabilities">
            {{ t('financeHub.viewAll') }} ›
          </router-link>
        </div>
      </van-tab>

      <!-- 心愿 tab: top 3 by nearest target_date (no-target_date excluded) -->
      <van-tab :title="t('nav.wishes')" name="wishes">
        <div class="top3-body">
          <van-skeleton v-if="wishLoading" :row="3" animate data-test="wishes-skeleton" />
          <button v-else-if="wishError" class="top3-retry" data-test="wishes-retry" @click="retryWishes">
            {{ t('financeHub.retry') }}
          </button>
          <van-empty v-else-if="topWishes.length === 0" :description="t('focusTop3.noWishes')" image-size="60" />
          <template v-else>
            <div
              v-for="wish in topWishes"
              :key="wish.id"
              class="top3-wish"
              :class="wishStatusClass(wish)"
              role="button"
              tabindex="0"
              :aria-label="wishAria(wish)"
              @click="$router.push(`/wishes/${wish.id}`)"
              @keydown.enter="$router.push(`/wishes/${wish.id}`)"
            >
              <div class="top3-wish-ring" :aria-hidden="true">
                <svg viewBox="0 0 36 36" class="top3-ring-svg">
                  <circle class="top3-ring-bg" cx="18" cy="18" r="15.9155" />
                  <circle
                    class="top3-ring-fg"
                    :class="`top3-ring-fg--${wishRingTone(wish)}`"
                    cx="18"
                    cy="18"
                    r="15.9155"
                    :stroke-dasharray="`${wishProgress(wish)}, 100`"
                  />
                </svg>
                <span class="top3-ring-label">{{ wishProgress(wish) }}%</span>
              </div>
              <div class="top3-wish-main">
                <div class="top3-wish-head">
                  <span class="top3-wish-name">{{ wish.name }}</span>
                  <span v-if="wishProgress(wish) >= 100" class="top3-wish-status">{{ t('focusTop3.wishAchieved') }}</span>
                  <span v-else-if="isWishOverdue(wish)" class="top3-wish-status top3-wish-status--overdue">{{ t('focusTop3.wishOverdue') }}</span>
                </div>
                <div class="top3-wish-amounts">
                  <MoneyDisplay :amount="Number(wish.saved_amount ?? 0)" class="top3-wish-saved" />
                  <span class="top3-wish-sep">/</span>
                  <MoneyDisplay :amount="Number(wish.expected_price ?? 0)" class="top3-wish-target" />
                </div>
                <div class="top3-progress-track" :aria-hidden="true">
                  <div
                    class="top3-progress-fill"
                    :class="`top3-progress-fill--${wishRingTone(wish)}`"
                    :style="{ width: `${wishProgress(wish)}%` }"
                  />
                </div>
                <div class="top3-wish-foot">
                  <span v-if="wishProgress(wish) < 100" class="top3-wish-remaining">
                    {{ t('focusTop3.wishRemaining') }}
                    <MoneyDisplay :amount="wishRemaining(wish)" />
                  </span>
                  <span class="top3-wish-date">{{ t('focusTop3.wishGoalDate') }} {{ wish.target_date }}</span>
                </div>
                <div v-if="wishProgress(wish) < 100" class="top3-wish-meta">
                  <span v-if="isWishOverdue(wish)">{{ t('focusTop3.wishOverdue') }}</span>
                  <span v-else-if="monthsToGoal(wish) > 0">{{ t('focusTop3.wishMonthsToGoal', { months: monthsToGoal(wish) }) }}</span>
                </div>
              </div>
            </div>
          </template>
          <router-link :to="{ path: '/finance', query: { tab: 'wishes' } }" class="top3-view-all" data-test="view-all-wishes">
            {{ t('financeHub.viewAll') }} ›
          </router-link>
        </div>
      </van-tab>
    </van-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import AssetListItem from '@/components/asset/AssetListItem.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useLiabilityStore } from '@/stores/liability'
import { useWishStore } from '@/stores/wish'
import { useCurrency } from '@/composables/useCurrency'
import { parseLocalDate } from '@/utils/format'
import type { Liability, Wish } from '@/types'
import { wishProgress } from '@/utils/wishProgress'

const { t } = useI18n()
const dashboardStore = useDashboardStore()
const liabilityStore = useLiabilityStore()
const wishStore = useWishStore()
const currency = useCurrency()

// High-interest thresholds mirror useDebtWarning defaults (W5 spec §5). Kept local
// to avoid wiring a full useDebtWarning instance (which needs loadThresholds) into a
// glance widget; threshold overrides are applied at the FinanceHub hint, not here.
const HIGH_INTEREST_THRESHOLDS: Record<string, number> = {
  credit_card: 12,
  personal_loan: 10,
  mortgage: 6,
  car_loan: 10,
  other: 10,
}

const activeTab = ref<'assets' | 'liabilities' | 'wishes'>('assets')

// Per-domain loading / error. Liability/wish stores expose only `loading` (fetch
// throws on failure), so their error is tracked here. Assets read the dashboard
// store's `homeAssets` (populated by DashboardPage.fetchAll -> fetchHomeAssets),
// so the assets tab binds to the store's overall loading state and has no
// independent fetch/error.
const liabilityLoading = ref(false)
const wishLoading = ref(false)
const liabilityError = ref(false)
const wishError = ref(false)
const assetLoading = computed(() => dashboardStore.loading)

// --- Top 3 selections (R13) ---
// Assets: by current value desc, from the dashboard's already-loaded homeAssets
// (full Asset objects suitable for AssetListItem). DashboardPage.fetchAll
// populates homeAssets (status-keyed); `in_use` is the primary bucket users care
// about. NOTE: homeAssets is capped at 5 per status by fetchHomeAssets, so "top 3"
// ranks within that limited set — acceptable for a dashboard glance widget.
const topAssets = computed(() =>
  [...(dashboardStore.homeAssets?.['in_use'] || [])]
    .sort((a, b) => Number(b.current_value ?? 0) - Number(a.current_value ?? 0))
    .slice(0, 3),
)

// Liabilities: active only, by interest rate desc (null rate → 0).
const topLiabilities = computed(() =>
  [...(liabilityStore.liabilities || [])]
    .filter((l) => l.is_active)
    .sort((a, b) => (b.interest_rate ?? 0) - (a.interest_rate ?? 0))
    .slice(0, 3),
)

// Wishes: only those with a target_date can be "most behind"; sort by nearest date.
const topWishes = computed(() =>
  [...(wishStore.wishes || [])]
    .filter((w) => w.target_date)
    .sort((a, b) => (a.target_date! < b.target_date! ? -1 : 1))
    .slice(0, 3),
)

function formatRate(rate: number | null): string {
  return rate == null ? '—' : `${rate}%`
}

// Locale-aware list formatter for aria-labels (replaces hardcoded '，')
const listFormatter = new Intl.ListFormat(undefined, { style: 'short', type: 'conjunction' })

function wishRemaining(wish: Wish): number {
  const expected = Number(wish.expected_price ?? 0) || 0
  const saved = Number(wish.saved_amount ?? 0) || 0
  return Math.max(0, expected - saved)
}

function isWishOverdue(wish: Wish): boolean {
  if (!wish.target_date) return false
  return parseLocalDate(wish.target_date).getTime() < Date.now()
}

// Months to reach goal = remaining / monthly_saving. Pure estimate; no date math so it
// stays meaningful even when target_date is far but saving rate is the real constraint.
function monthsToGoal(wish: Wish): number {
  const monthly = Number(wish.monthly_saving ?? 0) || 0
  if (monthly <= 0) return 0
  return Math.ceil(wishRemaining(wish) / monthly)
}

// Visual tone: achieved → success, overdue → danger, near (>=60%) → primary, else neutral.
function wishRingTone(wish: Wish): 'success' | 'danger' | 'primary' | 'neutral' {
  if (wishProgress(wish) >= 100) return 'success'
  if (isWishOverdue(wish)) return 'danger'
  if (wishProgress(wish) >= 60) return 'primary'
  return 'neutral'
}

function wishStatusClass(wish: Wish): string {
  if (wishProgress(wish) >= 100) return 'top3-wish--achieved'
  if (isWishOverdue(wish)) return 'top3-wish--overdue'
  return ''
}

function wishAria(wish: Wish): string {
  const parts = [wish.name, `${wishProgress(wish)}%`]
  const remaining = wishRemaining(wish)
  if (wishProgress(wish) < 100) parts.push(`${t('focusTop3.wishRemaining')} ${currency.format(remaining)}`)
  if (wish.target_date) parts.push(`${t('focusTop3.wishGoalDate')} ${wish.target_date}`)
  return listFormatter.format(parts)
}

// --- Liability compute ---

function paidAmount(liability: Liability): number {
  const original = Number(liability.original_amount ?? 0) || 0
  const remaining = Number(liability.remaining_amount ?? 0) || 0
  return Math.max(0, original - remaining)
}

function liabilityProgress(liability: Liability): number {
  const original = Number(liability.original_amount ?? 0) || 0
  if (original <= 0) return 0
  const remaining = Number(liability.remaining_amount ?? 0) || 0
  return Math.min(100, Math.max(0, Math.round(((original - remaining) / original) * 100)))
}

function isHighInterest(liability: Liability): boolean {
  const rate = liability.interest_rate ?? 0
  const threshold = HIGH_INTEREST_THRESHOLDS[liability.category] ?? HIGH_INTEREST_THRESHOLDS.other
  return liability.is_active && rate >= threshold
}

// Months to clear = remaining / monthly_payment. End-date is the amortization horizon
// but monthly_payment is the more honest predictor when it is set.
function monthsToClear(liability: Liability): number {
  const remaining = Number(liability.remaining_amount ?? 0) || 0
  const monthly = Number(liability.monthly_payment ?? 0) || 0
  if (monthly <= 0 || remaining <= 0) return 0
  return Math.ceil(remaining / monthly)
}

function liabilityAria(liability: Liability): string {
  const parts = [liability.name, formatRate(liability.interest_rate)]
  parts.push(`${t('focusTop3.liabilityPaid')} ${currency.format(paidAmount(liability))}`)
  parts.push(`${t('focusTop3.liabilityRemaining')} ${currency.format(Number(liability.remaining_amount ?? 0))}`)
  if (liabilityProgress(liability) < 100 && monthsToClear(liability) > 0) {
    parts.push(t('focusTop3.liabilityMonthsToClear', { months: monthsToClear(liability) }))
  }
  return listFormatter.format(parts)
}

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
  // Liability/wish load independently so a single failure degrades only its own tab.
  // Assets read from the dashboard store's homeAssets (fetched by DashboardPage.fetchAll).
  loadLiabilities()
  loadWishes()
})
</script>

<style scoped>
.focus-top3-card {
  margin: 12px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.top3-tabs :deep(.van-tabs__line) {
  background: var(--color-coral);
  height: 2px;
  border-radius: var(--radius-full);
}
.top3-tabs :deep(.van-tab--active) {
  color: var(--color-primary);
  font-weight: 600;
}
[data-theme='dark'] .top3-tabs :deep(.van-tab--active) {
  color: var(--color-coral);
}

.top3-body {
  padding: 8px 12px 4px;
  min-height: 80px;
}

.top3-retry {
  display: block;
  margin: 16px auto;
  background: none;
  border: 1px solid currentColor;
  border-radius: 4px;
  color: var(--color-primary);
  font-size: 13px;
  padding: 6px 16px;
  cursor: pointer;
}

.top3-view-all {
  display: block;
  text-align: center;
  padding: 10px 0;
  font-size: 13px;
  color: var(--color-primary);
  text-decoration: none;
}

/* Shared progress track (wish + liability) */
.top3-progress-track {
  height: 4px;
  background: var(--separator);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin: 6px 0;
}
.top3-progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  transition: width 300ms ease-out;
}
.top3-progress-fill--neutral { background: var(--color-primary); }
.top3-progress-fill--primary { background: var(--color-primary); }
.top3-progress-fill--success { background: var(--color-success, #07c160); }
.top3-progress-fill--danger  { background: var(--color-danger, #ee0a24); }
.top3-progress-fill--debt    { background: var(--color-primary); }

/* Liability row */
.top3-liability {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 4px 10px 8px;
  border-bottom: 1px solid var(--separator);
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 150ms ease-out;
}
.top3-liability:active { background: var(--bg-secondary); }
.top3-liability--highrate { border-left-color: var(--color-danger, #ee0a24); }
.top3-liability:last-of-type { border-bottom: none; }
.top3-liability-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.top3-liability-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top3-liability-tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: var(--color-danger, #ee0a24);
  font-weight: 600;
}
.top3-liability-tag .van-icon { font-size: 13px; }
.top3-liability-rate {
  font-size: 12px;
  color: var(--color-warning, #ff976a);
  font-weight: 600;
}
.top3-liability-foot {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.top3-liability-paid {
  font-size: 12px;
  color: var(--text-secondary);
}
.top3-liability-amount {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}
.top3-liability-meta {
  font-size: 11px;
  color: var(--text-secondary);
}

/* Wish row */
.top3-wish {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 4px 10px 8px;
  border-bottom: 1px solid var(--separator);
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 150ms ease-out;
}
.top3-wish:active { background: var(--bg-secondary); }
.top3-wish--overdue { border-left-color: var(--color-danger, #ee0a24); }
.top3-wish--achieved { border-left-color: var(--color-success, #07c160); }
.top3-wish:last-of-type { border-bottom: none; }

/* SVG progress ring */
.top3-wish-ring {
  position: relative;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
}
.top3-ring-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.top3-ring-bg {
  fill: none;
  stroke: var(--separator);
  stroke-width: 3.5;
}
.top3-ring-fg {
  fill: none;
  stroke-width: 3.5;
  stroke-linecap: round;
  transition: stroke-dasharray 400ms ease-out;
}
.top3-ring-fg--neutral { stroke: var(--color-primary); }
.top3-ring-fg--primary { stroke: var(--color-primary); }
.top3-ring-fg--success { stroke: var(--color-success, #07c160); }
.top3-ring-fg--danger  { stroke: var(--color-danger, #ee0a24); }
.top3-ring-label {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.top3-wish-main {
  flex: 1;
  min-width: 0;
}
.top3-wish-head {
  display: flex;
  align-items: center;
  gap: 6px;
}
.top3-wish-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top3-wish-status {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-success, #07c160);
}
.top3-wish-status--overdue { color: var(--color-danger, #ee0a24); }
.top3-wish-amounts {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-top: 2px;
}
.top3-wish-saved {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.top3-wish-sep {
  font-size: 12px;
  color: var(--text-secondary);
}
.top3-wish-target {
  font-size: 12px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
.top3-wish-foot {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.top3-wish-remaining {
  font-size: 12px;
  color: var(--text-secondary);
}
.top3-wish-date {
  font-size: 11px;
  color: var(--text-secondary);
}
.top3-wish-meta {
  font-size: 11px;
  color: var(--text-secondary);
}
.top3-wish--overdue .top3-wish-meta { color: var(--color-danger, #ee0a24); font-weight: 600; }
.top3-wish--achieved .top3-wish-meta { color: var(--color-success, #07c160); font-weight: 600; }
</style>
