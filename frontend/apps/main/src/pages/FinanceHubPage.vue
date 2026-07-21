<template>
  <div class="finance-hub-page" role="main" :aria-label="t('financeHub.aria.pageTitle')" :data-active-tab="activeTab">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Skeleton: while overview not yet loaded and no asset_count baseline -->
      <DashboardSkeleton v-if="hubLoading && !overview" />

      <!-- Error state: critical fetch (overview) failed → show retry, never silent 0 -->
      <div v-else-if="overviewError" class="hub-error">
        <van-empty :description="t('financeHub.loadFailed')">
          <van-button type="primary" size="small" @click="loadHubData">
            {{ t('financeHub.retry') }}
          </van-button>
        </van-empty>
      </div>

      <template v-else>
        <!-- Overview card: 净资产 + 总负债 + 月还 + 心愿进度 (+ W5 联动提示) -->
        <div class="finance-overview-card">
          <div class="ov-row ov-main">
            <div class="ov-label">{{ t('financeHub.netWorth') }}</div>
            <div class="ov-value">
              <MoneyDisplay :amount="overview?.net_worth ?? 0" size="large" />
            </div>
          </div>
          <div class="ov-divider" />
          <div class="ov-row">
            <div class="ov-label">{{ t('financeHub.totalLiabilities') }}</div>
            <div class="ov-value">
              <MoneyDisplay :amount="overview?.total_liabilities ?? 0" />
            </div>
          </div>
          <div class="ov-divider" />
          <div class="ov-row">
            <div class="ov-label">
              {{ t('financeHub.monthlyPayment') }}
              <span v-if="monthlyPaymentIsEstimate" class="ov-estimate-tag">{{ t('financeHub.estimate') }}</span>
            </div>
            <div class="ov-value">
              <MoneyDisplay :amount="monthlyPaymentTotal" />
            </div>
          </div>
          <div class="ov-divider" />
          <div class="ov-row">
            <div class="ov-label">{{ t('financeHub.wishProgress') }}</div>
            <div class="ov-value">
              <div class="wish-progress-wrap">
                <div class="wish-progress-bar">
                  <div class="wish-progress-fill" :style="{ width: `${wishProgressPercent}%` }" />
                </div>
                <span class="wish-progress-text">
                  {{ t('financeHub.wishCount', { count: wishCount }) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- W5 cross-module decision-chain hint (useDebtWarning) -->
        <div v-if="debtWishHint" class="debt-wish-hint">
          <van-icon name="warning-o" />
          <span>{{ debtWishHint }}</span>
        </div>

        <!-- Three sub-tabs: 资产 / 负债 / 心愿 -->
        <van-tabs v-model:active="activeTab" shrink>
          <van-tab :title="t('nav.assets')" name="assets">
            <div class="sub-tab-summary">
              <span>{{ t('financeHub.assetSummary', { count: assetCount, total: formattedTotalAssets }) }}</span>
              <van-button size="small" plain type="primary" data-test="view-all-assets" @click="goList('/assets')">
                {{ t('financeHub.viewAll') }}
              </van-button>
            </div>
          </van-tab>
          <van-tab :title="t('nav.liabilities')" name="liabilities">
            <div class="sub-tab-summary">
              <span>{{ t('financeHub.liabilitySummary', { count: liabilityCount, monthly: formattedMonthlyPayment }) }}</span>
              <van-button size="small" plain type="primary" data-test="view-all-liabilities" @click="goList('/liabilities')">
                {{ t('financeHub.viewAll') }}
              </van-button>
            </div>
          </van-tab>
          <van-tab :title="t('nav.wishes')" name="wishes">
            <div class="sub-tab-summary">
              <span>{{ t('financeHub.wishSummary', { count: wishCount, active: activeWishCount }) }}</span>
              <van-button size="small" plain type="primary" data-test="view-all-wishes" @click="goList('/wishes')">
                {{ t('financeHub.viewAll') }}
              </van-button>
            </div>
          </van-tab>
        </van-tabs>
      </template>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useLiabilityStore } from '@/stores/liability'
import { useWishStore } from '@/stores/wish'
import { useCurrency } from '@/composables/useCurrency'
import { useDebtWarning } from '@/composables/useDebtWarning'

defineOptions({ name: 'FinanceHub' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const dashboardStore = useDashboardStore()
const liabilityStore = useLiabilityStore()
const wishStore = useWishStore()
const currency = useCurrency()

const overview = computed(() => dashboardStore.overview)
const liabilities = computed(() => liabilityStore.liabilities)
const wishes = computed(() => wishStore.wishes)

// Loading: hub critical phase (overview + states). overview null + loading means first paint.
const hubLoading = computed(() => dashboardStore.loading && !overview.value)
const overviewError = ref(false)
const refreshing = ref(false)

const activeTab = ref<'assets' | 'liabilities' | 'wishes'>('assets')

// --- Month payment total (KTD-3: real monthly_payment preferred, null → interest estimate tagged) ---
const activeLiabilities = computed(() => (liabilities.value || []).filter((l) => l.is_active))

const monthlyPaymentTotal = computed(() => {
  // Sum non-null monthly_payment (real scheduled payment). Null items fall back to
  // interest-only estimate (remaining × rate/12) — flagged as "估算" in UI so the
  // headline is not mistaken for true monthly installment.
  return activeLiabilities.value.reduce((sum, l) => {
    const mp = Number(l.monthly_payment ?? 0)
    if (mp > 0) return sum + mp
    const rate = (l.interest_rate ?? 0) / 100 / 12
    return sum + Number(l.remaining_amount ?? 0) * rate
  }, 0)
})

const monthlyPaymentIsEstimate = computed(() =>
  // Tag when ANY active liability lacks a monthly_payment (estimate used for it).
  activeLiabilities.value.some((l) => !l.monthly_payment || Number(l.monthly_payment) === 0),
)

// --- Wish progress aggregation (KTD-3: sum(saved)/sum(expected) + count subtitle) ---
const wishCount = computed(() => (wishes.value || []).length)
const activeWishCount = computed(
  () => (wishes.value || []).filter((w) => w.status === 'active' || w.status === 'in_progress').length,
)

const wishProgressPercent = computed(() => {
  const expected = (wishes.value || []).reduce((sum, w) => sum + (Number(w.expected_price ?? 0) || 0), 0)
  if (expected <= 0) return 0
  const saved = (wishes.value || []).reduce((sum, w) => sum + (Number(w.saved_amount ?? 0) || 0), 0)
  return Math.min(100, Math.round((saved / expected) * 100))
})

const assetCount = computed(() => overview.value?.asset_count ?? 0)

// --- Formatted strings for sub-tab summaries ---
const formattedTotalAssets = computed(() => currency.format(overview.value?.total_assets ?? 0))
const formattedMonthlyPayment = computed(() => currency.format(monthlyPaymentTotal.value))
const liabilityCount = computed(() => activeLiabilities.value.length)

// --- W5 cross-module hint (useDebtWarning): high-interest debt delays nearest wish ---
// ComputedRef<T[]> is assignable to Ref<T[]> — no cast needed.
const liabilitiesRef = computed(() => liabilities.value)
const wishesRef = computed(() => wishes.value)
const { highInterestLiabilities, loadThresholds } = useDebtWarning(liabilitiesRef, wishesRef)

const debtWishHint = computed(() => {
  if (highInterestLiabilities.value.length === 0) return ''
  const totalMonthlyInterest = highInterestLiabilities.value.reduce(
    (sum, l) => sum + (l.monthly_interest ?? 0),
    0,
  )
  if (totalMonthlyInterest <= 0) return ''

  // Nearest target_date wish with monthly_saving>0 and not ignoring debt warning.
  const candidate = (wishes.value || [])
    .filter((w) => Number(w.monthly_saving ?? 0) > 0 && !w.ignore_debt_warning && w.target_date)
    .sort((a, b) => (a.target_date! < b.target_date! ? -1 : 1))[0]
  if (!candidate) return ''

  const monthlySaving = Number(candidate.monthly_saving ?? 0)
  if (monthlySaving <= 0) return ''
  const delayedMonths = Math.ceil(totalMonthlyInterest / monthlySaving)
  return t('financeHub.debtWishHint', {
    interest: currency.format(totalMonthlyInterest),
    wish: candidate.name,
    months: delayedMonths,
  })
})

// --- ?tab= contract (KTD-1/U3): honor deep-link tab selection ---
function applyQueryTab() {
  const q = route.query.tab
  if (q === 'assets' || q === 'liabilities' || q === 'wishes') {
    activeTab.value = q
  } else {
    activeTab.value = 'assets'
  }
}

function goList(path: string) {
  router.push(path)
}

async function loadHubData() {
  overviewError.value = false
  try {
    await Promise.all([
      dashboardStore.fetchAll(),
      liabilityStore.fetchLiabilities(),
      wishStore.fetchWishes(),
      loadThresholds(),
    ])
  } catch {
    // Critical fetch (overview) rejected → surface retry, never silent 0.
    if (!overview.value) overviewError.value = true
  }
}

async function onRefresh() {
  refreshing.value = true
  dashboardStore.invalidateDashboard()
  try {
    await loadHubData()
  } finally {
    refreshing.value = false
  }
}

onMounted(() => {
  applyQueryTab()
  loadHubData()
})
</script>

<style scoped>
.finance-hub-page {
  min-height: 100vh;
  background-color: var(--bg-secondary);
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
}

.finance-overview-card {
  margin: 12px;
  padding: 16px;
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.ov-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}

.ov-main .ov-label {
  font-size: 13px;
  color: var(--text-secondary, #969799);
}

.ov-main .ov-value {
  font-weight: 600;
}

.ov-label {
  font-size: 13px;
  color: var(--text-secondary, #969799);
  display: flex;
  align-items: center;
  gap: 6px;
}

.ov-estimate-tag {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--color-warning-light, #fff7e6);
  color: var(--color-warning, #ff976a);
}

.ov-divider {
  height: 1px;
  background: var(--border-color, #ebedf0);
  margin: 0;
}

.wish-progress-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wish-progress-bar {
  width: 100px;
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

.debt-wish-hint {
  margin: 0 12px 12px;
  padding: 10px 12px;
  background: var(--color-warning-light, #fff7e6);
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-warning, #ff976a);
  line-height: 1.5;
}

.debt-wish-hint .van-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.sub-tab-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  font-size: 13px;
  color: var(--text-primary, #323233);
}

.hub-error {
  padding: 40px 0;
}
</style>
