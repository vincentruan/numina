<template>
  <div class="wish-list-panel">
    <van-tabs v-model:active="activeTab">
      <van-tab :title="t('wish.tabs.pending')" name="pending" />
      <van-tab :title="t('wish.tabs.realized')" name="realized" />
      <van-tab :title="t('wish.tabs.cancelled')" name="cancelled" />
    </van-tabs>

    <!-- Sort bar -->
    <div class="sort-bar" role="toolbar" :aria-label="t('wish.aria.sortBar')">
      <button
        v-for="opt in sortOptions"
        :key="opt.value"
        class="sort-btn"
        :class="{ active: sortBy === opt.value }"
        :aria-label="t('wish.sortBar.ariaLabel', { label: opt.label })"
        :aria-pressed="sortBy === opt.value"
        @click="toggleSort(opt.value)"
      >
        {{ opt.label }}
        <span v-if="sortBy === opt.value" class="sort-dir" aria-hidden="true">
          {{ sortDir === 'asc' ? '↑' : '↓' }}
        </span>
      </button>
    </div>

    <div class="list-content">
      <!-- W5 (Plan B T8): high-interest-debt hint bar (spec §5.4: 先止血再储蓄,
           rendered ABOVE the W4 advice card). -->
      <div
        v-if="debtWarning.hasHighInterestDebt.value && wishes.length"
        class="debt-warning-bar"
      >
        <van-icon name="warning-o" />
        <span>{{
          t('wish.debtWarning.listHint', {
            amount: Number(debtWarning.highInterestLiabilities.value[0]?.remaining_amount ?? 0),
            rate: debtWarning.highInterestLiabilities.value[0]?.interest_rate ?? 0,
          })
        }}</span>
        <van-button size="mini" plain @click="goToLiabilityStrategy">
          {{ t('wish.debtWarning.viewStrategy') }}
        </van-button>
      </div>

      <!-- W4 (Plan B T7): AI wish-priority advice card. Hides itself when the
           backend returns empty (<2 wishes / no monthly_saving / LLM unavailable). -->
      <WishAdviceCard :wishes="wishes.map((w) => ({ id: w.id, name: w.name, monthly_saving: w.monthly_saving ?? '0' }))" />

      <!-- Skeleton for initial loading -->
      <WishListSkeleton v-if="wishStore.loading && wishes.length === 0" />

      <!-- Actual Content -->
      <template v-else-if="sortedWishes.length">
        <ul class="wish-list" :aria-label="t('wish.aria.listLabel')">
          <li
            v-for="wish in sortedWishes"
            :key="wish.id"
            class="wish-item"
            :class="`priority-${wish.priority}`"
            tabindex="0"
            :aria-label="t('wish.aria.itemLabel', { name: wish.name, priority: t('wish.priorityText.' + wish.priority), price: wish.expected_price ? t('wish.aria.priceFormat', { price: Number(wish.expected_price).toLocaleString() }) : '' })"
            @click="$router.push(`/wishes/${wish.id}`)"
            @keydown.enter="$router.push(`/wishes/${wish.id}`)"
          >
            <!-- Priority stripe -->
            <div class="priority-stripe" aria-hidden="true" />

            <!-- Icon anchor -->
            <div class="wish-icon" aria-hidden="true">
              <template v-if="wish.category">
                <SvgIcon :name="getIconId(wish.category.icon)" class="icon-svg" />
              </template>
              <span v-else class="wish-emoji">✨</span>
            </div>

            <!-- Main content -->
            <div class="wish-body">
              <div class="wish-top">
                <span class="wish-name">{{ wish.name }}</span>
                <div class="wish-right">
                  <span v-if="wish.expected_price" class="wish-price">
                    {{ currency.format(wish.expected_price) }}
                  </span>
                  <van-icon v-if="wish.status === 'realized'" name="success" color="#07c160" size="16" />
                  <van-icon name="arrow" size="12" class="card-arrow" />
                </div>
              </div>

              <div class="wish-bottom">
                <span class="priority-badge" :class="wish.priority">
                  {{ t('wish.priorityText.' + wish.priority) }}{{ t('wish.prioritySuffix') }}
                </span>
                <span v-if="wish.category" class="wish-cat">{{ wish.category.name }}</span>
                <span v-if="wish.description" class="wish-desc">{{ wish.description }}</span>
              </div>

              <!-- W2 (Plan B T9): afford bar — single-line compact (spec §3.2). -->
              <div
                v-if="wish.expected_price"
                class="afford-bar"
                :class="affordStateClass(wish)"
              >
                <span v-if="affordFor(wish).state.value.kind === 'unset_monthly'">{{ t('wish.afford.setMonthly') }}</span>
                <span v-else-if="affordFor(wish).state.value.kind === 'reached'">{{ t('wish.afford.reached') }} ✓</span>
                <span v-else-if="affordFor(wish).state.value.kind === 'progress'">{{ t('wish.afford.etaMonths', { n: affordMonths(wish) }) }}</span>
                <span v-if="affordFor(wish).accelerate" class="accelerate">! {{ t('wish.afford.needAccelerate') }}</span>
              </div>
            </div>
          </li>
        </ul>
      </template>
      <!-- Empty states -->
      <div v-else class="empty-state">
        <!-- Pending: guide to add first wish -->
        <template v-if="activeTab === 'pending'">
          <div class="empty-illustration empty-pending" aria-hidden="true">
            <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="40" cy="40" r="36" fill="var(--van-primary-color)" fill-opacity="0.08"/>
              <path d="M40 22c-1.1 0-2 .9-2 2v14H24c-1.1 0-2 .9-2 2s.9 2 2 2h14v14c0 1.1.9 2 2 2s2-.9 2-2V42h14c1.1 0 2-.9 2-2s-.9-2-2-2H42V24c0-1.1-.9-2-2-2z" fill="var(--van-primary-color)"/>
            </svg>
          </div>
          <p class="empty-title"><ShimmerText :text="t('wish.emptyState.noWishesTitle')" :duration="3" /></p>
          <p class="empty-desc">{{ t('wish.emptyState.noWishesDesc') }}</p>
          <button class="empty-action-btn" @click="$router.push('/wishes/new')">
            <svg viewBox="0 0 16 16" fill="none" width="14" height="14" aria-hidden="true">
              <path d="M8 2v12M2 8h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            {{ t('wish.emptyState.addFirstBtn') }}
          </button>
        </template>

        <!-- Realized: encouraging -->
        <template v-else-if="activeTab === 'realized'">
          <div class="empty-illustration empty-realized" aria-hidden="true">
            <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="40" cy="40" r="36" fill="#07c160" fill-opacity="0.08"/>
              <path d="M40 20l4.9 9.9 10.9 1.6-7.9 7.7 1.9 10.9L40 45.4l-9.8 5.1 1.9-10.9-7.9-7.7 10.9-1.6L40 20z" fill="#07c160" fill-opacity="0.25" stroke="#07c160" stroke-width="1.5" stroke-linejoin="round"/>
            </svg>
          </div>
          <p class="empty-title"><ShimmerText :text="t('wish.emptyState.noRealizedTitle')" :duration="3" /></p>
          <p class="empty-desc">{{ t('wish.emptyState.noRealizedDesc') }}</p>
        </template>

        <!-- Cancelled: neutral -->
        <template v-else>
          <div class="empty-illustration empty-cancelled" aria-hidden="true">
            <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="40" cy="40" r="36" fill="#999" fill-opacity="0.08"/>
              <path d="M28 28l24 24M52 28L28 52" stroke="#999" stroke-width="3" stroke-linecap="round"/>
            </svg>
          </div>
          <p class="empty-title"><ShimmerText :text="t('wish.emptyState.noCancelledTitle')" :duration="3" /></p>
          <p class="empty-desc">{{ t('wish.emptyState.noCancelledDesc') }}</p>
        </template>
      </div>
    </div>

    <div class="fab" :aria-label="t('wish.aria.addWish')" role="button" tabindex="0" @click="$router.push('/wishes/new')" @keydown.enter="$router.push('/wishes/new')" @keydown.space.prevent="$router.push('/wishes/new')">
      <van-icon name="plus" size="22" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, toRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { Wish } from '@/types'
import { getIconId } from '@/utils/icon'
import { useDashboardStore } from '@/stores/dashboard'
import { useWishStore } from '@/stores/wish'
import { useLiabilityStore } from '@/stores/liability'
import { useDebtWarning } from '@/composables/useDebtWarning'
import { useAffordBar } from '@/composables/useAffordBar'
import { useCurrency } from '@/composables/useCurrency'
import WishListSkeleton from '@/components/wishes/WishListSkeleton.vue'
import WishAdviceCard from '@/components/wishes/WishAdviceCard.vue'
import ShimmerText from '@/components/ai-chat/ShimmerText.vue'
import SvgIcon from '@/components/SvgIcon.vue'

const { t } = useI18n()
const router = useRouter()
const currency = useCurrency()
const dashboardStore = useDashboardStore()
const wishStore = useWishStore()
const liabilityStore = useLiabilityStore()

const wishes = ref<Wish[]>([])

// W5 (Plan B T8): high-interest-debt ↔ wish linkage. Warn before saving (spec §5.4).
const debtWarning = useDebtWarning(
  toRef(liabilityStore, 'liabilities'),
  wishes,
)
const activeTab = ref<'pending' | 'realized' | 'cancelled'>('pending')
const sortBy = ref<'priority' | 'price' | 'name'>('priority')
const sortDir = ref<'asc' | 'desc'>('desc')

const sortOptions = computed(() => [
  { value: 'priority' as const, label: t('wish.sortBar.priority') },
  { value: 'price' as const, label: t('wish.sortBar.price') },
  { value: 'name' as const, label: t('wish.sortBar.name') },
])

const priorityOrder: Record<string, number> = { high: 3, medium: 2, low: 1 }

const filteredWishes = computed(() =>
  wishes.value.filter(w => w.status === activeTab.value)
)

const sortedWishes = computed(() => {
  const list = [...filteredWishes.value]
  const dir = sortDir.value === 'asc' ? 1 : -1
  return list.sort((a, b) => {
    if (sortBy.value === 'priority') {
      return dir * ((priorityOrder[a.priority] ?? 2) - (priorityOrder[b.priority] ?? 2))
    }
    if (sortBy.value === 'price') {
      return dir * ((Number(a.expected_price) || 0) - (Number(b.expected_price) || 0))
    }
    return dir * a.name.localeCompare(b.name)
  })
})


function toggleSort(value: typeof sortBy.value) {
  if (sortBy.value === value) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = value
    sortDir.value = 'desc'
  }
}

// W2 (Plan B T9): per-wish afford-bar logic. Cache by wish.id to avoid recompute
// churn across re-renders (spec §3.2 list single-line compact).
const affordCache = new Map<string, ReturnType<typeof useAffordBar>>()
function affordFor(w: Wish) {
  if (!affordCache.has(w.id)) {
    affordCache.set(w.id, useAffordBar(() => w, () => dashboardStore.overview?.net_worth ?? 0))
  }
  return affordCache.get(w.id)!
}
function affordStateClass(w: Wish): string {
  const kind = affordFor(w).state.value.kind
  return `afford-${kind}`
}
// Months-to-goal for the 'progress' state; 0 otherwise (template can't narrow the union).
function affordMonths(w: Wish): number {
  const s = affordFor(w).state.value
  return s.kind === 'progress' ? s.months : 0
}

async function loadWishes() {
  await wishStore.fetchWishes()
  wishes.value = wishStore.wishes
  if (!dashboardStore.overview) {
    dashboardStore.fetchOverview().catch(() => {})
  }
  // W5: load debt thresholds + liabilities so the high-interest hint can render.
  void debtWarning.loadThresholds()
  liabilityStore.fetchLiabilities().catch(() => {})
}

// W5: jump to the liability strategy view (spec §5.4: 先止血再储蓄). The liability
// list now lives under the finance tab — deep-link to the L1 strategy card there.
function goToLiabilityStrategy() {
  router.push({ path: '/finance', query: { tab: 'liabilities', focus: 'liability_strategy' } })
}

onMounted(loadWishes)

defineExpose({
  activeTab,
  sortBy,
  sortDir,
  filteredWishes,
  sortedWishes,
  toggleSort,
  goToLiabilityStrategy,
})
</script>

<style scoped>
/* ── W5 debt-warning bar (Plan B T8) ── */
.debt-warning-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 12px;
  padding: 8px 10px;
  background: rgba(255, 151, 106, 0.12);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-primary, #323233);
}
.debt-warning-bar span {
  flex: 1;
}

/* ── Sort bar ── */
.sort-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--separator);
}

.sort-btn {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 30px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  position: relative;
}

.sort-btn::after {
  content: '';
  position: absolute;
  inset: -6px;
}

.sort-btn.active {
  background: #eeece7;
  color: #17171c;
  border-color: #17171c;
  font-weight: 500;
}

[data-theme='dark'] .sort-btn {
  border-color: rgba(255, 255, 255, 0.15);
}

[data-theme='dark'] .sort-btn.active {
  background: rgba(255, 255, 255, 0.12);
  color: #f5f5f5;
  border-color: rgba(255, 255, 255, 0.4);
}

.sort-dir {
  font-size: 11px;
}

/* ── List ── */
.list-content {
  padding: 12px 16px;
}

.wish-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── Item ── */
.wish-item {
  display: flex;
  align-items: stretch;
  background: var(--card-bg);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  min-height: 72px;
}

[data-theme='dark'] .wish-item {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

.wish-item:active {
  transform: scale(0.985);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.wish-item:focus-visible {
  outline: 2px solid var(--color-focus-blue);
  outline-offset: 2px;
}

/* ── Priority stripe (4px left border) ── */
.priority-stripe {
  width: 4px;
  flex-shrink: 0;
  border-radius: 0;
}

.priority-high .priority-stripe  { background: #f44336; }
.priority-medium .priority-stripe { background: #ff9800; }
.priority-low .priority-stripe   { background: #4caf50; }

/* ── Icon anchor ── */
.wish-icon {
  width: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-svg {
  width: 22px;
  height: 22px;
  color: var(--van-primary-color);
}

.wish-emoji {
  font-size: 20px;
  line-height: 1;
}

/* ── Body ── */
.wish-body {
  flex: 1;
  min-width: 0;
  padding: 12px 12px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

/* Top row: name + price + arrow */
.wish-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.wish-name {
  flex: 1;
  min-width: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: linear-gradient(
    90deg,
    var(--text-primary) 0%,
    var(--van-primary-color) calc(50% - 3%),
    var(--van-primary-color) calc(50% + 3%),
    var(--text-primary) 100%
  );
  background-size: 200% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: wish-name-shimmer 3s ease-in-out infinite;
}

@keyframes wish-name-shimmer {
  0% { background-position: -100% 0; }
  50% { background-position: 0% 0; }
  100% { background-position: 100% 0; }
}

@media (prefers-reduced-motion: reduce) {
  .wish-name {
    animation: none;
    background: none;
    -webkit-text-fill-color: initial;
  }
}

.wish-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.wish-price {
  font-size: 15px;
  font-weight: 700;
  color: #ee0a24;
  letter-spacing: -0.3px;
}

.card-arrow {
  color: var(--text-tertiary);
}

/* Bottom row: badge + category + desc */
.wish-bottom {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.priority-badge {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 10px;
  flex-shrink: 0;
}

.priority-badge.low    { background: rgba(76, 175, 80, 0.12); color: #4caf50; }
.priority-badge.medium { background: rgba(255, 152, 0, 0.12); color: #ff9800; }
.priority-badge.high   { background: rgba(244, 67, 54, 0.12); color: #f44336; }

[data-theme='dark'] .priority-badge.low    { background: rgba(76, 175, 80, 0.2); color: #81c784; }
[data-theme='dark'] .priority-badge.medium { background: rgba(255, 152, 0, 0.2); color: #ffb74d; }
[data-theme='dark'] .priority-badge.high   { background: rgba(244, 67, 54, 0.2); color: #e57373; }

.wish-cat {
  font-size: 12px;
  color: var(--text-tertiary);
}

.wish-cat::before {
  content: '·';
  margin-right: 6px;
  color: var(--text-tertiary);
}

.wish-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* ── Empty state ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56px 32px 32px;
  gap: 8px;
  text-align: center;
}

.empty-illustration {
  width: 80px;
  height: 80px;
  margin-bottom: 8px;
}

.empty-illustration svg {
  width: 100%;
  height: 100%;
}

.empty-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

/* Preserve empty-title weight (ShimmerText defaults to 500) */
.empty-title :deep(.shimmer-text) {
  font-weight: 600;
}

@media (prefers-reduced-motion: reduce) {
  .empty-title :deep(.shimmer-text) {
    animation: none;
    -webkit-text-fill-color: initial;
  }
}

.empty-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.empty-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 10px 20px;
  border-radius: 20px;
  border: none;
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s;
  min-height: 44px;
}

[data-theme='dark'] .empty-action-btn {
  background: var(--color-lavender);
  color: #010120;
}

.empty-action-btn:active {
  opacity: 0.8;
}

/* ── Afford bar ── */
.afford-bar {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 6px;
  align-self: flex-start;
}

/* W2 afford-bar state colors (Plan B T9). afford-${state.kind} from affordStateClass. */
.afford-reached {
  background: rgba(7, 193, 96, 0.1);
  color: #07c160;
}
.afford-progress {
  background: rgba(25, 137, 250, 0.1);
  color: #1989fa;
}
.afford-unset_monthly,
.afford-need_accelerate {
  background: rgba(255, 151, 106, 0.1);
  color: #ff976a;
}
.afford-bar .accelerate {
  font-weight: 600;
  margin-left: 2px;
}

/* FAB */
.fab {
  position: fixed;
  right: 16px;
  bottom: 72px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-elevated);
  z-index: 10;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  cursor: pointer;
  border: none;
}

.fab:active {
  transform: scale(0.93);
  box-shadow: 0 2px 8px rgba(1, 1, 32, 0.2);
}

[data-theme='dark'] .fab {
  background: var(--color-lavender);
  color: #010120;
  box-shadow: 0 4px 16px rgba(189, 187, 255, 0.3);
}
</style>
