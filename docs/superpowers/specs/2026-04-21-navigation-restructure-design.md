# Navigation Restructure: Overview Merge + Baby Page

**Date:** 2026-04-21  
**Status:** Approved  
**Scope:** Frontend only — no backend changes required

## Background

The admin-switches-to-child-view feature has a session bug (cookie not restored on return). Rather than fix the technical issue, this redesign eliminates the need for that feature entirely by giving parents a dedicated "Baby Page" that surfaces all child management in one place, accessible from the main tab bar.

## Goals

1. Merge the Statistics page content into the Overview page — one less tab, richer overview
2. Replace the Statistics tab with a "Baby" tab (owner-only) for child management
3. Add infinite-scroll pagination to the Overview asset list
4. Remove `PendingApprovalsSection` from Overview — consolidate child-related content in Baby page

## Non-Goals

- No backend API changes
- No changes to child authentication or the child-mode UI (`ChildLayout`, `ChildTabBar`)
- No changes to the AI, Wishes, Liabilities, or Settings tabs

---

## Section 1: Navigation (AppTabBar)

**Tab bar layout (6 tabs, unchanged count):**

| # | Name | Icon | Route | Visibility |
|---|------|------|-------|------------|
| 1 | 总览 | `chart-trending-o` | `/` | All users |
| 2 | 心愿 | `star-o` | `/wishes` | All users |
| 3 | AI | `AIBrainIcon` | `/ai` | All users |
| 4 | 负债 | `bill-o` | `/liabilities` | All users |
| 5 | **宝贝** | `friends-o` | `/baby` | **Owner only** (`v-if="isOwner"`) |
| 6 | 设置 | `setting-o` | `/settings` | All users |

**Changes to `AppTabBar.vue`:**
- Tab 5: rename `stats` → `baby`, icon `bar-chart-o` → `friends-o`, route `/stats` → `/baby`
- Add `isOwner` computed from `useAuthStore`, wrap tab 5 with `v-if="isOwner"`
- Update `routeToTab` and `tabToRoute` maps accordingly

**Router changes:**
- Add route `/baby` → `BabyPage.vue` (inside MainLayout, requires auth)
- Keep `/stats` route pointing to `DataStatsPage.vue` (file preserved, just removed from tab bar)

---

## Section 2: Overview Page (DashboardPage.vue)

**New layout order (top to bottom):**

1. `NetWorthCard` — existing, unchanged
2. Stale data hint — existing, unchanged
3. **资产趋势** (new, default expanded) — `TrendLineChart` wrapped in `van-collapse`
4. **资产分布** (new, default collapsed) — `AllocationPieChart` wrapped in `van-collapse`
5. `StatusSummaryGrid` + toolbar — existing, unchanged
6. `AlertCards` — existing, unchanged
7. Asset list with pagination — see Section 4

**Removed from Overview:**
- `PendingApprovalsSection` — moved to Baby page entirely

**Collapse state persistence:**
- `dashboard_trend_expanded` in localStorage, default `true`
- `dashboard_allocation_expanded` in localStorage, default `false`

**Data:** No new API calls. `dashboardStore.trend` and `dashboardStore.allocation` are already fetched by `fetchAll()`.

**Quick stats (资产数量 / 本月新增 / 日均成本):**
- Displayed as a compact `van-cell-group` immediately below `NetWorthCard` (no changes to NetWorthCard internals)
- Data source: `dashboardStore.overview` (already available)

---

## Section 3: Baby Page (BabyPage.vue)

New file: `frontend/src/pages/BabyPage.vue`  
Route: `/baby` (owner-only, guarded by router)

**Layout (top to bottom):**

### ① Pending Approvals
- Reuse `PendingApprovalsSection` component directly
- Hidden when there are no pending items

### ② Child Selector (横向 tab)
- `van-tabs` with `scrollable` for overflow
- First tab: "全部" (all children aggregated)
- Subsequent tabs: one per child — avatar initial circle + display name
- Tab header shows child's summary stats: `余额 ⭐ / 本周家务完成率 / 进行中心愿数`
- Only shown when `childMembers.length > 0`

### ③ Content Area (switches with selected child)
Three sections displayed below the selector, using `van-tabs` (心愿 / 任务 / 完成情况):

**心愿 tab:**
- List of wishes for selected child (or all children when "全部" selected)
- Each item: wish name, status badge, progress bar
- Tap → navigate to `/wishes/:id`
- Data: `listParentChildWishes()`, filtered by `child_user_id`

**任务 tab:**
- This week's chores for selected child
- Each item: chore name, completion status (done/pending)
- Data: existing chore APIs

**完成情况 tab:**
- Weekly/monthly completion rate chart or simple stats
- Data: `getChildrenChoreStats()` API

**Data sources (all existing APIs, no new endpoints):**
- Child list: `familyStore.members.filter(m => m.role === 'child')`
- Balances: `getAllChildBalances()`
- Chore stats: `getChildrenChoreStats()`
- Wishes: `listParentChildWishes()`
- Pending approvals: `getPendingApprovals()`

---

## Section 4: Overview Asset List Pagination

**Approach:** Frontend pagination over in-memory data (no new API).

**Store changes (`dashboardStore`):**
- Add `displayedAssets: Asset[]` — the currently rendered slice
- Add `assetPage: number` (starts at 1)
- Add `assetPageSize: number` (= 20)
- Add `assetListFinished: boolean` — true when all assets are displayed
- Add `loadMoreAssets()` — appends next 20 from `sortedAndFilteredAssets` to `displayedAssets`
- `fetchAll()` resets `assetPage = 1`, `displayedAssets = []`, then calls `loadMoreAssets()` once

**Component changes (`DashboardPage.vue`):**
- Wrap asset list with `van-list` component
- Bind `v-model:loading="loadingMore"`, `:finished="dashboardStore.assetListFinished"`, `@load="onLoadMore"`
- `onLoadMore` calls `dashboardStore.loadMoreAssets()`
- On sort/filter change: reset `assetPage = 1`, `displayedAssets = []`, reload first page
- Pull-to-refresh resets pagination and calls `fetchAll(true)`

**UX:** User scrolls to bottom → `van-list` fires `@load` → next 20 assets append → repeat until `finished = true`.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/common/AppTabBar.vue` | Rename stats→baby tab, add owner guard |
| `frontend/src/router/index.ts` | Add `/baby` route, keep `/stats` |
| `frontend/src/pages/DashboardPage.vue` | Add trend/allocation collapse sections, remove PendingApprovals, add van-list pagination |
| `frontend/src/stores/dashboard.ts` | Add pagination state + `loadMoreAssets()` |
| `frontend/src/pages/BabyPage.vue` | New file |
| `frontend/src/pages/DataStatsPage.vue` | No change (kept, just removed from tab bar) |

## Removed Feature

The `switchToChildView` function in `FamilyPage.vue` and the `admin_child_view` localStorage key are no longer needed once the Baby page is in place. They can be removed in a follow-up cleanup PR after this feature ships.
