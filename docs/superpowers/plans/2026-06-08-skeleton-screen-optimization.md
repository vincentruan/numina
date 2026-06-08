# Skeleton Screen Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add skeleton screens to WishListPage and LiabilityListPage with NProgress layered collaboration for optimized weak network loading experience.

**Architecture:** Route meta field `hasSkeleton` identifies skeleton pages; router `afterEach` immediately completes NProgress for skeleton pages, letting skeleton components provide visual feedback. Page-level skeleton components display during initial load (`loading && data.length === 0`), not during pull-to-refresh.

**Tech Stack:** Vue 3 + Vant 4 `van-skeleton` / `van-skeleton-avatar` + NProgress + Vue Router meta fields

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `frontend/apps/main/src/router/index.ts` | Modify | Add `meta.hasSkeleton` to routes, conditional NProgress in `afterEach` |
| `frontend/apps/main/src/components/wishes/WishListSkeleton.vue` | Create | Skeleton for WishListPage (tabs + sort bar + wish items) |
| `frontend/apps/main/src/components/liability/LiabilityListSkeleton.vue` | Create | Skeleton for LiabilityListPage (tabs + filter bar + banner + cards) |
| `frontend/apps/main/src/pages/WishListPage.vue` | Modify | Integrate WishListSkeleton with loading state |
| `frontend/apps/main/src/pages/LiabilityListPage.vue` | Modify | Integrate LiabilityListSkeleton with loading state |

---

## Task 1: Route Configuration with meta.hasSkeleton

**Files:**
- Modify: `frontend/apps/main/src/router/index.ts:52-127`

- [ ] **Step 1: Add hasSkeleton meta to existing skeleton routes**

Update the Dashboard and AssetList routes to include `meta.hasSkeleton: true`:

```typescript
// frontend/apps/main/src/router/index.ts
// Lines 52-66 (Dashboard and AssetList routes)

{
  path: '',
  name: 'Dashboard',
  component: () => import('@/pages/DashboardPage.vue'),
  meta: { hasSkeleton: true }
},
{
  path: 'dashboard/analytics',
  name: 'AssetAnalytics',
  component: () => import('@/pages/AssetAnalyticsPage.vue')
},
{
  path: 'assets',
  name: 'AssetList',
  component: () => import('@/pages/AssetListPage.vue'),
  meta: { hasSkeleton: true }
},
```

- [ ] **Step 2: Add hasSkeleton meta to WishList and LiabilityList routes**

Update the WishList and LiabilityList routes:

```typescript
// frontend/apps/main/src/router/index.ts
// Lines 88-127

{
  path: 'liabilities',
  name: 'LiabilityList',
  component: () => import('@/pages/LiabilityListPage.vue'),
  meta: { hasSkeleton: true }
},
{
  path: 'liabilities/new',
  name: 'LiabilityCreate',
  component: () => import('@/pages/LiabilityFormPage.vue')
},
{
  path: 'liabilities/:id/edit',
  name: 'LiabilityEdit',
  component: () => import('@/pages/LiabilityFormPage.vue')
},
{
  path: 'liabilities/:id',
  name: 'LiabilityDetail',
  component: () => import('@/pages/LiabilityDetailPage.vue')
},
{
  path: 'wishes',
  name: 'WishList',
  component: () => import('@/pages/WishListPage.vue'),
  meta: { hasSkeleton: true }
},
{
  path: 'wishes/new',
  name: 'WishCreate',
  component: () => import('@/pages/WishFormPage.vue')
},
{
  path: 'wishes/:id/edit',
  name: 'WishEdit',
  component: () => import('@/pages/WishFormPage.vue')
},
{
  path: 'wishes/:id',
  name: 'WishDetail',
  component: () => import('@/pages/WishDetailPage.vue')
},
```

- [ ] **Step 3: Modify afterEach for conditional NProgress**

Replace the existing `afterEach` with conditional logic:

```typescript
// frontend/apps/main/src/router/index.ts
// Replace lines 412-414

router.afterEach((to) => {
  // Pages with skeleton: immediately complete NProgress
  // Skeleton takes over visual feedback during data loading
  if (to.meta.hasSkeleton) {
    NProgress.done()
  }
  // Pages without skeleton: NProgress stays active
  // Page's onMounted data loading will call NProgress.done() when complete
})
```

- [ ] **Step 4: Run typecheck to verify router changes**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS with no type errors

- [ ] **Step 5: Commit route configuration**

```bash
git add frontend/apps/main/src/router/index.ts
git commit -m "$(cat <<'EOF'
feat(router): add hasSkeleton meta and conditional NProgress

- Add meta.hasSkeleton to Dashboard, AssetList, WishList, LiabilityList routes
- Modify afterEach to immediately complete NProgress for skeleton pages
- Skeleton components provide visual feedback instead of progress bar

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: WishListSkeleton Component

**Files:**
- Create: `frontend/apps/main/src/components/wishes/WishListSkeleton.vue`

- [ ] **Step 1: Create WishListSkeleton.vue**

Create the skeleton component matching WishListPage structure:

```vue
<!-- frontend/apps/main/src/components/wishes/WishListSkeleton.vue -->
<template>
  <div class="wish-list-skeleton">
    <!-- Tabs skeleton -->
    <div class="skeleton-tabs">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- Sort bar skeleton -->
    <div class="skeleton-sort-bar">
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
    </div>

    <!-- Wish items skeleton (3 items) -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="wish-item-skeleton">
        <!-- Priority stripe -->
        <div class="priority-stripe-skeleton" />
        <!-- Icon anchor -->
        <div class="wish-icon-skeleton">
          <van-skeleton-avatar avatar-size="44px" avatar-shape="round" animate />
        </div>
        <!-- Body: two rows -->
        <div class="wish-body-skeleton">
          <van-skeleton :row="2" row-width="70% 50%" animate />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton component for WishListPage loading state
</script>

<style scoped>
.wish-list-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
}

/* Tabs skeleton */
.skeleton-tabs {
  background: var(--card-bg);
  padding: 12px 16px;
}
.skeleton-tabs :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-tabs :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}

/* Sort bar skeleton */
.skeleton-sort-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--separator);
}
.sort-btn-skeleton {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 30px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .sort-btn-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.sort-btn-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.sort-btn-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

/* List skeleton */
.skeleton-list {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Wish item skeleton */
.wish-item-skeleton {
  display: flex;
  align-items: stretch;
  background: var(--card-bg);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  min-height: 72px;
}
[data-theme='dark'] .wish-item-skeleton {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

/* Priority stripe skeleton (gray placeholder) */
.priority-stripe-skeleton {
  width: 4px;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.12);
}
[data-theme='dark'] .priority-stripe-skeleton {
  background: rgba(255, 255, 255, 0.12);
}

/* Icon anchor */
.wish-icon-skeleton {
  width: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 2px;
}
.wish-icon-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .wish-icon-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}

/* Body skeleton */
.wish-body-skeleton {
  flex: 1;
  min-width: 0;
  padding: 12px 12px 12px 0;
  display: flex;
  flex-direction: column;
}
.wish-body-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.wish-body-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
}
.wish-body-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}
</style>
```

- [ ] **Step 2: Run typecheck to verify component**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS with no type errors

- [ ] **Step 3: Commit WishListSkeleton component**

```bash
git add frontend/apps/main/src/components/wishes/WishListSkeleton.vue
git commit -m "$(cat <<'EOF'
feat(wishes): add WishListSkeleton component

- Tabs skeleton with 3 placeholder tabs
- Sort bar skeleton with 3 sort buttons
- Wish item skeletons with priority stripe + icon + body
- Dark mode CSS variable adaptation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: LiabilityListSkeleton Component

**Files:**
- Create: `frontend/apps/main/src/components/liability/LiabilityListSkeleton.vue`

- [ ] **Step 1: Create LiabilityListSkeleton.vue**

Create the skeleton component matching LiabilityListPage structure:

```vue
<!-- frontend/apps/main/src/components/liability/LiabilityListSkeleton.vue -->
<template>
  <div class="liability-list-skeleton">
    <!-- Tabs skeleton (2 tabs) -->
    <div class="skeleton-tabs">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- Filter bar skeleton -->
    <div class="skeleton-filter-bar">
      <div class="filter-chips-skeleton">
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="40px" animate />
        </div>
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="50px" animate />
        </div>
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="60px" animate />
        </div>
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="50px" animate />
        </div>
      </div>
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="50px" animate />
      </div>
    </div>

    <!-- Summary Banner skeleton -->
    <div class="summary-banner-skeleton">
      <div class="summary-top-skeleton">
        <div class="summary-main-skeleton">
          <van-skeleton :row="2" row-width="80px 120px" animate />
        </div>
        <div class="summary-count-skeleton">
          <van-skeleton :row="1" row-width="60px" animate />
        </div>
      </div>
      <div class="progress-bar-skeleton">
        <van-skeleton :row="1" row-width="100%" animate />
      </div>
      <div class="progress-text-skeleton">
        <van-skeleton :row="1" row-width="80px" animate />
      </div>
    </div>

    <!-- Liability cards skeleton (3 cards) -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="liability-card-skeleton">
        <van-skeleton :row="2" row-width="100% 60%" animate />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton component for LiabilityListPage loading state
</script>

<style scoped>
.liability-list-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
}

/* Tabs skeleton */
.skeleton-tabs {
  background: var(--card-bg);
  padding: 12px 16px;
}
.skeleton-tabs :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-tabs :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}

/* Filter bar skeleton */
.skeleton-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  overflow-x: auto;
}
[data-theme='dark'] .skeleton-filter-bar {
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.filter-chips-skeleton {
  display: flex;
  gap: 6px;
  flex: 1;
}

.chip-skeleton {
  flex-shrink: 0;
  padding: 4px 14px;
  border-radius: 30px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .chip-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.chip-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.chip-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

.sort-btn-skeleton {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .sort-btn-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.sort-btn-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.sort-btn-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

/* Summary Banner skeleton - matches gradient background */
.summary-banner-skeleton {
  margin: 12px 12px 4px;
  background: linear-gradient(135deg, #991b1b 0%, #dc2626 60%, #ea580c 100%);
  border-radius: 16px;
  padding: 20px;
}

/* White semi-transparent skeleton bars on gradient background */
.summary-banner-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.2) !important;
}

.summary-top-skeleton {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.summary-main-skeleton {
  flex: 1;
}
.summary-main-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.summary-main-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  margin-top: 6px;
}
.summary-main-skeleton :deep(.van-skeleton__row:last-child) {
  height: 36px;
  margin-top: 6px;
}

.summary-count-skeleton {
  padding-top: 4px;
}
.summary-count-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.summary-count-skeleton :deep(.van-skeleton__row) {
  height: 28px;
  width: 60px !important;
}

.progress-bar-skeleton {
  height: 6px;
  margin-bottom: 8px;
}
.progress-bar-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.progress-bar-skeleton :deep(.van-skeleton__row) {
  height: 6px;
  border-radius: 3px;
}

.progress-text-skeleton {
  display: flex;
  justify-content: flex-end;
}
.progress-text-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.progress-text-skeleton :deep(.van-skeleton__row) {
  height: 12px;
  width: 80px !important;
}

/* List skeleton */
.skeleton-list {
  padding: 8px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Liability card skeleton */
.liability-card-skeleton {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .liability-card-skeleton {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.liability-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.liability-card-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
}
.liability-card-skeleton :deep(.van-skeleton__row:first-child) {
  height: 16px;
  margin-top: 0;
}
</style>
```

- [ ] **Step 2: Run typecheck to verify component**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS with no type errors

- [ ] **Step 3: Commit LiabilityListSkeleton component**

```bash
git add frontend/apps/main/src/components/liability/LiabilityListSkeleton.vue
git commit -m "$(cat <<'EOF'
feat(liability): add LiabilityListSkeleton component

- Tabs skeleton with 2 placeholder tabs
- Filter bar skeleton with category chips and sort button
- Summary banner skeleton with gradient background
- White semi-transparent skeleton bars for banner content
- Liability card skeletons with dark mode adaptation

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Integrate WishListSkeleton into WishListPage

**Files:**
- Modify: `frontend/apps/main/src/pages/WishListPage.vue`

- [ ] **Step 1: Add WishListSkeleton import**

Add import statement after existing imports:

```typescript
// frontend/apps/main/src/pages/WishListPage.vue
// Add after line 156 (import { useDashboardStore } from '@/stores/dashboard')

import WishListSkeleton from '@/components/wishes/WishListSkeleton.vue'
```

- [ ] **Step 2: Add loading state from wishStore**

The WishListPage currently uses local `wishes` ref. Add wishStore for loading state:

```typescript
// frontend/apps/main/src/pages/WishListPage.vue
// Add after line 158 (const dashboardStore = useDashboardStore())

import { useWishStore } from '@/stores/wish'
const wishStore = useWishStore()
```

Update `loadWishes` function to use wishStore:

```typescript
// frontend/apps/main/src/pages/WishListPage.vue
// Replace lines 211-217

async function loadWishes() {
  await wishStore.fetchWishes()
  wishes.value = wishStore.wishes
  if (!dashboardStore.overview) {
    dashboardStore.fetchOverview().catch(() => {})
  }
}
```

- [ ] **Step 3: Add skeleton display logic in template**

Wrap the existing content with skeleton conditional:

```vue
<!-- frontend/apps/main/src/pages/WishListPage.vue -->
<!-- Replace lines 1-149 (entire template) -->

<template>
  <div class="wish-list-page">
    <van-nav-bar :title="t('wish.nav.title')" />

    <!-- Skeleton for initial loading -->
    <WishListSkeleton v-if="wishStore.loading && wishes.length === 0" />

    <!-- Actual Content -->
    <template v-else>
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
    </template>
  </div>
</template>
```

- [ ] **Step 4: Run typecheck to verify integration**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS with no type errors

- [ ] **Step 5: Commit WishListPage integration**

```bash
git add frontend/apps/main/src/pages/WishListPage.vue
git commit -m "$(cat <<'EOF'
feat(wishes): integrate WishListSkeleton into WishListPage

- Import WishListSkeleton component
- Use wishStore.loading for skeleton display condition
- Skeleton shows only on initial load (loading && wishes.length === 0)
- Pull-to-refresh uses van-pull-refresh built-in indicator

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Integrate LiabilityListSkeleton into LiabilityListPage

**Files:**
- Modify: `frontend/apps/main/src/pages/LiabilityListPage.vue`

- [ ] **Step 1: Add LiabilityListSkeleton import**

Add import statement after existing component imports:

```typescript
// frontend/apps/main/src/pages/LiabilityListPage.vue
// Add after line 151 (import LiabilityCard from '@/components/liability/LiabilityCard.vue')

import LiabilityListSkeleton from '@/components/liability/LiabilityListSkeleton.vue'
```

- [ ] **Step 2: Add skeleton display logic in template**

Wrap the content (after PageHeader) with skeleton conditional:

```vue
<!-- frontend/apps/main/src/pages/LiabilityListPage.vue -->
<!-- Replace lines 1-139 (entire template) -->

<template>
  <div class="liability-list-page">
    <PageHeader :title="t('liability.pageTitle')" :show-back="false">
      <template v-if="selectMode" #right>
        <span class="select-cancel" @click="exitSelectMode">{{ t('liability.cancelSelect') }}</span>
      </template>
    </PageHeader>

    <!-- Skeleton for initial loading -->
    <LiabilityListSkeleton v-if="liabilityStore.loading && liabilityStore.liabilities.length === 0" />

    <!-- Actual Content -->
    <template v-else>
      <van-tabs v-model:active="activeTab" sticky @change="onTabChange">
        <van-tab :title="t('liability.tabActive')" name="active" />
        <van-tab :title="t('liability.tabInactive')" name="inactive" />
      </van-tabs>

      <!-- Filter / Sort bar -->
      <div class="filter-bar">
        <div class="filter-chips">
          <button
            class="chip"
            :class="{ active: filterCategory === '' }"
            @click="filterCategory = ''"
          >{{ t('liability.filterAll') }}</button>
          <button
            v-for="cat in categories"
            :key="cat.value"
            class="chip"
            :class="{ active: filterCategory === cat.value }"
            @click="filterCategory = cat.value"
          >{{ cat.label }}</button>
        </div>
        <button class="sort-btn" @click="toggleSort">
          <van-icon name="sort" size="16" />
          <span>{{ sortLabel }}</span>
        </button>
      </div>

      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Summary Banner -->
        <div v-if="liabilityStore.liabilities.length" class="summary-banner">
          <div class="summary-top">
            <div class="summary-main">
              <div class="summary-label">{{ activeTab === 'active' ? t('liability.summaryTotal') : t('liability.summarySettled') }}</div>
              <div class="summary-amount">{{ formatAmountDisplay(totalAmount) }}</div>
            </div>
            <div class="summary-count">
              <span class="count-num">{{ filteredLiabilities.length }}</span>
              <span class="count-unit">{{ t('liability.countUnit') }}</span>
            </div>
          </div>
          <template v-if="activeTab === 'active' && totalOriginal > 0">
            <div class="summary-progress-bar">
              <div class="summary-progress-fill" :style="{ width: repaidPercent + '%' }" />
            </div>
            <div class="summary-progress-text">
              <span>{{ t('liability.summaryProgress') }}</span>
              <span class="summary-percent">{{ repaidPercent }}%</span>
            </div>
          </template>
        </div>

        <div v-if="filteredLiabilities.length" class="liability-list">
          <LiabilityCard
            v-for="item in filteredLiabilities"
            :key="item.id"
            :liability="item"
            :select-mode="selectMode"
            :selected="selectedIds.has(item.id)"
            @click="onCardClick(item)"
            @longpress="onLongPress(item)"
            @pay="openPayDialog"
            @edit="goEdit"
            @delete="confirmDelete"
          />
        </div>
        <EmptyState v-else :description="activeTab === 'active' ? t('liability.noLiabilityDesc') : t('liability.noSettledLiability')">
          <van-button v-if="activeTab === 'active'" size="small" type="primary" @click="$router.push('/liabilities/new')">
            {{ t('liability.addLiability') }}
          </van-button>
        </EmptyState>
      </van-pull-refresh>

      <!-- Batch action bar -->
      <Transition name="slide-up">
        <div v-if="selectMode" class="batch-bar">
          <span class="batch-count">{{ t('liability.batchCount', { count: selectedIds.size }) }}</span>
          <div class="batch-actions">
            <van-button size="small" plain @click="selectAll">{{ t('liability.batchSelectAll') }}</van-button>
            <van-button
              v-if="activeTab === 'active'"
              size="small"
              type="success"
              :disabled="selectedIds.size === 0"
              @click="batchSettle"
            >{{ t('liability.batchSettle') }}</van-button>
            <van-button
              size="small"
              type="danger"
              :disabled="selectedIds.size === 0"
              @click="batchDelete"
            >{{ t('liability.batchDelete') }}</van-button>
          </div>
        </div>
      </Transition>

      <!-- FAB (hidden in select mode) -->
      <div v-if="!selectMode" class="fab" @click="$router.push('/liabilities/new')">
        <van-icon name="plus" size="22" />
      </div>

      <!-- Quick payment dialog -->
      <van-dialog
        v-model:show="payDialogVisible"
        :title="t('liability.payDialogTitle', { name: payTarget?.name ?? '' })"
        show-cancel-button
        :confirm-button-text="t('liability.payConfirmBtn')"
        confirm-button-color="#059669"
        @confirm="submitPayment"
      >
        <div class="pay-dialog-body">
          <div class="pay-hint">{{ t('liability.payRemainingHint', { amount: payTarget ? formatAmountDisplay(payTarget.remaining_amount) : '' }) }}</div>
          <van-field
            v-model="payAmount"
            type="number"
            :placeholder="t('liability.payPlaceholder')"
            input-align="center"
            autofocus
            :formatter="(v: string) => v.replace(/[^0-9.]/g, '')"
          />
          <div class="pay-quick-btns">
            <button
              v-for="pct in [25, 50, 100]"
              :key="pct"
              class="quick-pct-btn"
              @click="setPayPercent(pct)"
            >{{ pct === 100 ? t('liability.payFull') : pct + '%' }}</button>
          </div>
        </div>
      </van-dialog>
    </template>
  </div>
</template>
```

- [ ] **Step 3: Run typecheck to verify integration**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS with no type errors

- [ ] **Step 4: Commit LiabilityListPage integration**

```bash
git add frontend/apps/main/src/pages/LiabilityListPage.vue
git commit -m "$(cat <<'EOF'
feat(liability): integrate LiabilityListSkeleton into LiabilityListPage

- Import LiabilityListSkeleton component
- Use liabilityStore.loading for skeleton display condition
- Skeleton shows only on initial load (loading && liabilities.length === 0)
- Pull-to-refresh uses van-pull-refresh built-in indicator

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Verification and Testing

**Files:**
- No file changes (verification only)

- [ ] **Step 1: Run full typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS with no type errors

- [ ] **Step 2: Run lint check**

Run: `cd frontend/apps/main && pnpm lint`
Expected: PASS with no lint errors

- [ ] **Step 3: Manual browser verification**

Start dev server and verify:

```bash
cd frontend/apps/main && pnpm dev
```

Open browser at http://localhost:5173 and navigate to:
1. **WishListPage** (`/wishes`):
   - Clear localStorage or use browser DevTools Network throttling (Slow 3G)
   - Navigate to `/wishes` and observe skeleton screen appears before data loads
   - Verify skeleton structure matches actual page layout
   - Verify NProgress completes immediately (no visible progress bar)
   - Pull down to refresh — verify skeleton does NOT appear, only pull indicator

2. **LiabilityListPage** (`/liabilities`):
   - Same verification steps as WishListPage
   - Verify summary banner skeleton gradient background displays correctly
   - Verify white semi-transparent skeleton bars visible on gradient

3. **Dark Mode**:
   - Toggle dark mode in settings
   - Verify skeleton screens adapt to dark theme correctly

- [ ] **Step 4: Final commit (if all verification passes)**

```bash
git status
# If any uncommitted changes remain, commit them
```

---

## Self-Review Checklist

After writing this plan, I verified:

1. **Spec coverage:**
   - Route meta field `hasSkeleton` → Task 1
   - Conditional NProgress in afterEach → Task 1, Step 3
   - WishListSkeleton component → Task 2
   - LiabilityListSkeleton component → Task 3
   - WishListPage integration → Task 4
   - LiabilityListPage integration → Task 5
   - Verification/testing → Task 6
   - Dark mode adaptation → Covered in Task 2 and Task 3 CSS styles

2. **Placeholder scan:** No TBD, TODO, or vague instructions. All code blocks contain complete implementation.

3. **Type consistency:**
   - `wishStore.loading` (ref<boolean>) used consistently
   - `liabilityStore.loading` (ref<boolean>) used consistently
   - `wishes.length === 0` condition matches Wish type
   - `liabilityStore.liabilities.length === 0` matches Liability type
   - All imports use correct paths (`@/components/wishes/`, `@/components/liability/`, `@/stores/wish`, `@/stores/liability`)