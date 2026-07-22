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
            <div v-for="liability in topLiabilities" :key="liability.id" class="top3-liability" @click="$router.push(`/liabilities/${liability.id}`)">
              <span class="top3-liability-name">{{ liability.name }}</span>
              <span class="top3-liability-rate">{{ formatRate(liability.interest_rate) }}</span>
              <MoneyDisplay :amount="Number(liability.remaining_amount ?? 0)" class="top3-liability-amount" />
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
            <div v-for="wish in topWishes" :key="wish.id" class="top3-wish" @click="$router.push(`/wishes/${wish.id}`)">
              <span class="top3-wish-name">{{ wish.name }}</span>
              <span class="top3-wish-date">{{ wish.target_date }}</span>
              <span class="top3-wish-progress">{{ wishProgress(wish) }}%</span>
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
import type { Wish } from '@/types'

const { t } = useI18n()
const dashboardStore = useDashboardStore()
const liabilityStore = useLiabilityStore()
const wishStore = useWishStore()

const activeTab = ref<'assets' | 'liabilities' | 'wishes'>('assets')

// Per-domain loading / error. Liability/wish stores expose only `loading` (fetch
// throws on failure), so their error is tracked here. Assets reuse the dashboard
// store's already-driven pagination fetch (owned by DashboardPage), so the assets
// tab binds to the store's loading state and has no independent fetch/error.
const liabilityLoading = ref(false)
const wishLoading = ref(false)
const liabilityError = ref(false)
const wishError = ref(false)
const assetLoading = computed(() => dashboardStore.assetListLoading)

// --- Top 3 selections (R13) ---
// Assets: by current value desc, from the dashboard's already-loaded displayedAssets
// (full Asset objects suitable for AssetListItem). DashboardPage fetches page 1 on mount.
const topAssets = computed(() =>
  [...(dashboardStore.displayedAssets || [])]
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

function wishProgress(wish: Wish): number {
  const expected = Number(wish.expected_price ?? 0) || 0
  if (expected <= 0) return 0
  const saved = Number(wish.saved_amount ?? 0) || 0
  return Math.min(100, Math.round((saved / expected) * 100))
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
  // Assets read from the dashboard store's displayedAssets (fetched by DashboardPage).
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

/* Liability row */
.top3-liability {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 4px;
  border-bottom: 1px solid var(--separator);
  cursor: pointer;
}
.top3-liability:last-of-type {
  border-bottom: none;
}
.top3-liability-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top3-liability-rate {
  font-size: 12px;
  color: var(--color-warning, #ff976a);
  font-weight: 600;
}
.top3-liability-amount {
  font-size: 13px;
  color: var(--text-secondary);
}

/* Wish row */
.top3-wish {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 4px;
  border-bottom: 1px solid var(--separator);
  cursor: pointer;
}
.top3-wish:last-of-type {
  border-bottom: none;
}
.top3-wish-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top3-wish-date {
  font-size: 12px;
  color: var(--text-secondary);
}
.top3-wish-progress {
  font-size: 12px;
  color: var(--color-primary);
  font-weight: 600;
}
</style>
