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
        <!-- W5 cross-module decision-chain hint (useDebtWarning) -->
        <div v-if="debtWishHint" class="debt-wish-hint">
          <van-icon name="warning-o" />
          <span>{{ debtWishHint }}</span>
        </div>

        <!-- Three sub-tabs: 资产 / 负债 / 心愿 -->
        <van-tabs v-model:active="activeTab" shrink>
          <van-tab :title="t('nav.assets')" name="assets">
            <!-- Full asset list panel (status/category/type filters + search/sort + pagination + selection) -->
            <AssetListPanel />
          </van-tab>
          <van-tab :title="t('nav.liabilities')" name="liabilities">
            <!-- Full liability list panel (active/inactive tabs + strategy card + filters + selection) -->
            <LiabilityListPanel />
          </van-tab>
          <van-tab :title="t('nav.wishes')" name="wishes">
            <!-- Full wish list panel (pending/realized/cancelled tabs + advice card + sort) -->
            <WishListPanel />
          </van-tab>
        </van-tabs>
      </template>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import DashboardSkeleton from '@/components/dashboard/DashboardSkeleton.vue'
import AssetListPanel from '@/components/asset/AssetListPanel.vue'
import LiabilityListPanel from '@/components/liability/LiabilityListPanel.vue'
import WishListPanel from '@/components/wishes/WishListPanel.vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useLiabilityStore } from '@/stores/liability'
import { useWishStore } from '@/stores/wish'
import { useCurrency } from '@/composables/useCurrency'
import { useDebtWarning } from '@/composables/useDebtWarning'

defineOptions({ name: 'FinanceHub' })

const { t } = useI18n()
const route = useRoute()
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

async function loadHubData() {  overviewError.value = false
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
</style>
