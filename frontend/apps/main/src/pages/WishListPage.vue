<template>
  <div class="wish-list-page">
    <van-nav-bar :title="t('wish.nav.title')" />

    <van-tabs v-model:active="activeTab" sticky>
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
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <template v-if="sortedWishes.length">
          <ul class="wish-list" :aria-label="t('wish.aria.listLabel')">
            <li
              v-for="wish in sortedWishes"
              :key="wish.id"
              class="wish-item"
              :class="`priority-${wish.priority}`"
              tabindex="0"
              :aria-label="t('wish.aria.itemLabel', { name: wish.name, priority: t('wish.priorityText.' + wish.priority), price: wish.expected_price ? t('wish.aria.priceFormat', { price: wish.expected_price.toLocaleString() }) : '' })"
              @click="$router.push(`/wishes/${wish.id}`)"
              @keydown.enter="$router.push(`/wishes/${wish.id}`)"
            >
              <!-- Priority stripe -->
              <div class="priority-stripe" aria-hidden="true" />

              <!-- Icon anchor -->
              <div class="wish-icon" aria-hidden="true">
                <template v-if="wish.category">
                  <svg class="icon-svg" aria-hidden="true">
                    <use :href="`#${getIconId(wish.category.icon)}`" />
                  </svg>
                </template>
                <span v-else class="wish-emoji">✨</span>
              </div>

              <!-- Main content -->
              <div class="wish-body">
                <div class="wish-top">
                  <span class="wish-name">{{ wish.name }}</span>
                  <div class="wish-right">
                    <span v-if="wish.expected_price" class="wish-price">
                      ¥{{ formatPrice(wish.expected_price) }}
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

                <!-- Afford bar -->
                <div
                  v-if="wish.expected_price && dashboardStore.overview"
                  class="afford-bar"
                  :class="wish.expected_price <= dashboardStore.overview.net_worth ? 'afford-yes' : 'afford-no'"
                >
                  <template v-if="wish.expected_price <= dashboardStore.overview.net_worth">
                    <svg class="afford-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path d="M3 8l3.5 3.5L13 5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    {{ t('wish.afford.canAfford') }}
                  </template>
                  <template v-else>
                    <svg class="afford-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path d="M8 3v5M8 11v1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
                    </svg>
                    {{ t('wish.afford.shortage', { amount: formatPrice(wish.expected_price - dashboardStore.overview.net_worth) }) }}
                  </template>
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
            <p class="empty-title">{{ t('wish.emptyState.noWishesTitle') }}</p>
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
            <p class="empty-title">{{ t('wish.emptyState.noRealizedTitle') }}</p>
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
            <p class="empty-title">{{ t('wish.emptyState.noCancelledTitle') }}</p>
            <p class="empty-desc">{{ t('wish.emptyState.noCancelledDesc') }}</p>
          </template>
        </div>
      </van-pull-refresh>
    </div>

    <div class="fab" :aria-label="t('wish.aria.addWish')" @click="$router.push('/wishes/new')">
      <van-icon name="plus" size="22" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getWishes } from '@/api/wishes'
import type { Wish } from '@/types'
import { getIconId } from '@/utils/icon'
import { useDashboardStore } from '@/stores/dashboard'

const { t } = useI18n()
const dashboardStore = useDashboardStore()

const wishes = ref<Wish[]>([])
const activeTab = ref<'pending' | 'realized' | 'cancelled'>('pending')
const refreshing = ref(false)
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
      return dir * ((a.expected_price ?? 0) - (b.expected_price ?? 0))
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

function formatPrice(value: number): string {
  if (value >= 10000) {
    return (value / 10000).toFixed(value % 10000 === 0 ? 0 : 1) + t('common.unitTenThousand')
  }
  return value.toLocaleString()
}

async function loadWishes() {
  const res = await getWishes()
  wishes.value = res.data
  if (!dashboardStore.overview) {
    dashboardStore.fetchOverview().catch(() => {})
  }
}

async function onRefresh() {
  await loadWishes()
  refreshing.value = false
}

onMounted(loadWishes)
</script>

<style scoped>
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

.afford-yes {
  background: rgba(7, 193, 96, 0.1);
  color: #07c160;
}

.afford-no {
  background: rgba(255, 125, 0, 0.1);
  color: #ff7d00;
}

.afford-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
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
