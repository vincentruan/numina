<template>
  <div class="finance-hub-page" role="main" :aria-label="t('financeHub.aria.pageTitle')" :data-active-tab="activeTab">
    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <!-- Skeleton: tab-specific layout matching the actual content structure -->
      <div v-if="hubLoading && !overview" class="hub-skeleton-wrapper">
        <!-- Tab bar skeleton (4 tabs) -->
        <div class="skeleton-tab-bar">
          <div v-for="i in 4" :key="i" class="skeleton-tab-item">
            <van-skeleton-avatar avatar-size="18px" avatar-shape="square" animate />
            <van-skeleton :row="1" row-width="32px" animate />
          </div>
        </div>
        <!-- Tab-specific skeleton content -->
        <AssetListSkeleton v-if="activeTab === 'assets'" />
        <LiabilityListSkeleton v-else-if="activeTab === 'liabilities'" />
        <RentalListSkeleton v-else-if="activeTab === 'rentals'" />
        <WishListSkeleton v-else />
      </div>

      <!-- Error state: critical fetch (overview) failed → show retry, never silent 0 -->
      <div v-else-if="overviewError" class="hub-error">
        <van-empty :description="t('financeHub.loadFailed')">
          <van-button type="primary" size="small" @click="loadHubData">
            {{ t('financeHub.retry') }}
          </van-button>
        </van-empty>
      </div>

      <template v-else>
        <!-- W5 cross-module decision-chain hint (useDebtWarning) -->
        <div v-if="debtWishHint" class="debt-wish-hint">
          <van-icon name="warning-o" />
          <span>{{ debtWishHint }}</span>
        </div>

        <!-- Three sub-tabs: 资产 / 负债 / 心愿 -->
        <van-tabs v-model:active="activeTab" shrink class="finance-tabs">
          <van-tab name="assets">
            <template #title>
              <div class="tab-title">
                <van-icon name="gold-coin-o" />
                <span>{{ t('nav.assets') }}</span>
              </div>
            </template>
            <!-- Full asset list panel (status/category/type filters + search/sort + pagination + selection) -->
            <AssetListPanel />
          </van-tab>
          <van-tab name="liabilities">
            <template #title>
              <div class="tab-title">
                <van-icon name="bill-o" />
                <span>{{ t('nav.liabilities') }}</span>
              </div>
            </template>
            <!-- Full liability list panel (active/inactive tabs + strategy card + filters + selection) -->
            <LiabilityListPanel />
          </van-tab>
          <van-tab name="wishes">
            <template #title>
              <div class="tab-title">
                <van-icon name="gift-o" />
                <span>{{ t('nav.wishes') }}</span>
              </div>
            </template>
            <!-- Full wish list panel (pending/realized/cancelled tabs + advice card + sort) -->
            <WishListPanel />
          </van-tab>
          <van-tab name="rentals">
            <template #title>
              <div class="tab-title">
                <van-icon name="shop-o" />
                <span>{{ t('rental.tab') }}</span>
              </div>
            </template>
            <!-- Rental contracts panel (landlord/tenant + active/history tabs + summary) -->
            <RentalListPanel />
          </van-tab>
        </van-tabs>
      </template>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onActivated, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AssetListSkeleton from '@/components/asset/AssetListSkeleton.vue'
import LiabilityListSkeleton from '@/components/liability/LiabilityListSkeleton.vue'
import WishListSkeleton from '@/components/wishes/WishListSkeleton.vue'
import RentalListSkeleton from '@/components/rental/RentalListSkeleton.vue'
import AssetListPanel from '@/components/asset/AssetListPanel.vue'
import LiabilityListPanel from '@/components/liability/LiabilityListPanel.vue'
import WishListPanel from '@/components/wishes/WishListPanel.vue'
import RentalListPanel from '@/components/rental/RentalListPanel.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useLiabilityStore } from '@/stores/liability'
import { useWishStore } from '@/stores/wish'
import { useCurrency } from '@/composables/useCurrency'
import { useDebtWarning } from '@/composables/useDebtWarning'
import { usePageLoading } from '@/composables/usePageLoading'
import { useGestureHint } from '@/composables/useGestureHint'

defineOptions({ name: 'FinanceHub' })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const dashboardStore = useDashboardStore()
const liabilityStore = useLiabilityStore()
const wishStore = useWishStore()
const currency = useCurrency()
const { increment, decrement } = usePageLoading()
const assetGesture = useGestureHint('asset-longpress')
const liabilityGesture = useGestureHint('liability-swipe')
// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first
// mount inside <KeepAlive>; onMounted handles initial load.
let hasActivated = false

const overview = computed(() => dashboardStore.overview)
const liabilities = computed(() => liabilityStore.liabilities)
const wishes = computed(() => wishStore.wishes)

// Loading: hub critical phase (overview + states). overview null + loading means first paint.
const hubLoading = computed(() => dashboardStore.loading && !overview.value)
const overviewError = ref(false)
const refreshing = ref(false)

const activeTab = ref<'assets' | 'liabilities' | 'wishes' | 'rentals'>('assets')

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
    interest: currency.formatConverted(totalMonthlyInterest, 'CNY'),
    wish: candidate.name,
    months: delayedMonths,
  })
})

// --- Gesture hints: trigger when respective tabs become active ---
watch(activeTab, (tab) => {
  if (tab === 'assets' && overview.value?.asset_count) assetGesture.trigger()
  if (tab === 'liabilities') liabilityGesture.trigger()
})

// --- ?tab= contract (KTD-1/U3): honor deep-link tab selection ---
// Watch route changes so dashboard drill-down links switch tabs without remounting.
watch(
  () => route.query.tab,
  (q) => {
    if (q === 'assets' || q === 'liabilities' || q === 'wishes' || q === 'rentals') {
      activeTab.value = q
    }
  },
)
// Sync user-initiated tab switches back to the URL (router.replace, no new history
// entry). Without this, router.back() from a detail page restores the stale URL
// (usually ?tab=assets), so applyQueryTab() on onActivated resets to the wrong tab.
watch(activeTab, (tab) => {
  if (route.query.tab !== tab) {
    router.replace({ query: { ...route.query, tab } })
  }
})
function applyQueryTab() {
  const q = route.query.tab
  if (q === 'assets' || q === 'liabilities' || q === 'wishes' || q === 'rentals') {
    activeTab.value = q
  } else {
    activeTab.value = 'assets'
  }
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

onMounted(async () => {
  applyQueryTab()
  increment()
  try {
    await loadHubData()
  } finally {
    decrement()
  }
})

// KeepAlive 缓存页面：返回时触发 onActivated 而非 onMounted
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  applyQueryTab()
  increment()
  try {
    await loadHubData()
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.finance-hub-page {
  min-height: 100vh;
  background-color: var(--bg-secondary);
  padding-bottom: calc(50px + env(safe-area-inset-bottom));
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

.hub-error {
  padding: 40px 0;
}

.tab-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.finance-tabs :deep(.van-tab) .tab-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.finance-tabs :deep(.van-tab) .van-icon {
  font-size: 18px;
  flex-shrink: 0;
}

/* ── Skeleton wrapper ── */
.hub-skeleton-wrapper {
  background: var(--bg-secondary);
}

/* Skeleton tab bar — mirrors van-tabs shrink layout (icon + label per tab) */
.skeleton-tab-bar {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 12px 16px 10px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--separator, rgba(0, 0, 0, 0.04));
}
.skeleton-tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.skeleton-tab-item :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-tab-item :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
</style>
