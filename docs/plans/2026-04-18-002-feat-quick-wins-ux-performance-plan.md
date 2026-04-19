---
date: 2026-04-18
id: 2026-04-18-002
title: Quick Wins — UX & Performance Polish (6 Tasks)
status: completed
origin: docs/brainstorms/2026-04-18-quick-wins-ux-performance-requirements.md
---

# Plan: Quick Wins — UX & Performance Polish

## Problem Frame

Six high-confidence, low-complexity frontend improvements. All pure frontend — no backend endpoints, no schema migrations. Improves perceived performance, child UX clarity, and frontend reliability.

(see origin: docs/brainstorms/2026-04-18-quick-wins-ux-performance-requirements.md)

---

## Research Findings

**Key files confirmed:**
- `frontend/src/api/index.ts` — axios instance (timeout: 15000 at line 30), request interceptor is a no-op pass-through (lines 41–47)
- `frontend/src/stores/dashboard.ts` — `fetchAll()` at lines 82–98, no dedup or staleness logic currently
- `frontend/src/stores/asset.ts` — 7 write actions: `createAsset`, `updateAsset`, `deleteAsset`, `updateValue`, `sellAsset`, `retireAsset`, `reactivateAsset`
- `frontend/src/stores/liability.ts` — 4 write actions: `createLiability`, `updateLiability`, `deleteLiability`, `recordPayment`
- `frontend/src/pages/DashboardPage.vue` — `onRefresh()` at lines 686–692 calls `dashboardStore.fetchAll()`; batch ops call `fetchAll()` directly at lines 600 and 667
- `frontend/src/pages/child/ChildWishesPage.vue` — progress bar at lines 24–29; `load()` calls `Promise.all([listChildWishes(), getChildWishStats()])` at line 172
- `frontend/src/api/childWishes.ts` — `ChildWishStats.priority_simulation` confirmed: `{ wish_id, name, priority, star_coin_cost, progress, covered }[]` with top-level `balance`
- `frontend/src/api/coins.ts` — `CoinTransaction`: `{ id, amount, transaction_type, narrative, narrative_emoji, created_at, relative_time }`; `getCoinLedger()` at lines 24–27

**Deferred questions resolved:**
- `priority_simulation` has `wish_id` and `star_coin_cost` — no backend change needed ✓
- Batch ops call `fetchAll()` directly — no store-level invalidation hooks needed for them ✓

**No prior Pinia dedup/staleness patterns** in `docs/solutions/` — designing from scratch following existing store conventions.

---

## Implementation Units

### Unit 1 — AI Endpoint Timeout Split
**File:** `frontend/src/api/index.ts`

**Approach:** Add a URL-based branch inside the existing request interceptor (lines 41–47). The interceptor currently returns `config` unchanged. Add `config.timeout = config.url?.includes('/ai/') ? 120000 : 15000` before the return.

**Pattern to follow:** The existing response interceptor already branches on `url.includes('/auth/')` — same pattern.

**Test scenarios:**
- A request to `/api/v1/ai/report` has `config.timeout === 120000`
- A request to `/api/v1/assets` has `config.timeout === 15000`
- A request to `/api/v1/dashboard/bundle` has `config.timeout === 15000`

---

### Unit 2 — Dashboard Store: Request Dedup + Staleness Guard + Force Param
**File:** `frontend/src/stores/dashboard.ts`

**Approach:** Add three new refs to the store:
- `lastFetchedAt: ref<number | null>(null)` — timestamp of last successful fetch
- `_fetchPromise: ref<Promise<void> | null>(null)` — in-flight Promise ref for dedup

Rewrite `fetchAll(force = false)` with this evaluation order:
1. If `_fetchPromise.value` is not null → return `_fetchPromise.value` (dedup)
2. If `!force && lastFetchedAt.value && Date.now() - lastFetchedAt.value < DASHBOARD_TTL_MS` → return `Promise.resolve()` (staleness guard)
3. Otherwise → issue new request, store Promise in `_fetchPromise`, on success set `lastFetchedAt = Date.now()`, on finally clear `_fetchPromise`

Add constant: `const DASHBOARD_TTL_MS = 2 * 60 * 1000`

Add `invalidateDashboard()` helper that sets `lastFetchedAt.value = null`. Export it.

`fetchAll()` signature: `async function fetchAll(force = false): Promise<void>`

**Pattern to follow:** Existing `loading` ref pattern in the same store.

**Test scenarios:**
- Calling `fetchAll()` twice concurrently → only one network request, both callers resolve when it completes
- Calling `fetchAll()` after a successful fetch within 2 minutes → returns immediately, no network request
- Calling `fetchAll(force: true)` within 2 minutes → issues a new network request
- Calling `fetchAll()` after `invalidateDashboard()` → issues a new network request
- `fetchAll()` on error → `_fetchPromise` is cleared, `lastFetchedAt` is NOT updated, next call retries

---

### Unit 3 — Staleness Invalidation in Asset + Liability Stores
**Files:** `frontend/src/stores/asset.ts`, `frontend/src/stores/liability.ts`

**Approach:** Import `useDashboardStore` inside each write action (or at store init) and call `dashboardStore.invalidateDashboard()` at the end of each write action's success path.

Write actions to hook:
- Asset store: `createAsset`, `updateAsset`, `deleteAsset`, `updateValue`, `sellAsset`, `retireAsset`, `reactivateAsset`
- Liability store: `createLiability`, `updateLiability`, `deleteLiability`, `recordPayment`

**Important:** Call `invalidateDashboard()` only on success (inside the try block after the API call succeeds), not in finally. A failed write should not invalidate the cache.

**Pattern to follow:** Existing store actions already update local state after API success — add `invalidateDashboard()` as the last line of each success path.

**Note on batch ops:** `DashboardPage.vue` calls `dashboardStore.fetchAll()` directly after batch delete (line 600) and batch status-change (line 667). These already trigger a fresh fetch — no store-level hook needed for them.

**Test scenarios:**
- After `createAsset()` succeeds → `dashboardStore.lastFetchedAt` is null
- After `updateValue()` succeeds → `dashboardStore.lastFetchedAt` is null
- After `sellAsset()` succeeds → `dashboardStore.lastFetchedAt` is null
- After `recordPayment()` succeeds → `dashboardStore.lastFetchedAt` is null
- After a failed `createAsset()` → `dashboardStore.lastFetchedAt` is unchanged

---

### Unit 4 — Stale Indicator + Force Pull-to-Refresh in DashboardPage
**File:** `frontend/src/pages/DashboardPage.vue`

**Approach — force param:**
Update `onRefresh()` (lines 686–692) to call `dashboardStore.fetchAll(true)` instead of `dashboardStore.fetchAll()`.

**Approach — stale indicator:**
Add a computed ref `isShowingCachedData` that is `true` when `dashboardStore.lastFetchedAt !== null && !dashboardStore.loading`. This means data was served from cache (staleness guard fired).

Insert a single line of muted text below the stats bar (after the `NetWorthCard` component, before the first content section):
```vue
<p v-if="isShowingCachedData" class="stale-hint">数据可能不是最新</p>
```
Style: `color: var(--van-gray-6); font-size: 12px; text-align: center; margin: 4px 0;`

**Test scenarios:**
- After navigating back to dashboard within TTL → stale indicator is visible
- After pull-to-refresh → stale indicator disappears (fresh fetch completes, `lastFetchedAt` updated)
- After `invalidateDashboard()` + `fetchAll()` → stale indicator disappears

---

### Unit 5 — Task 4 Verification (Skeleton States)
**Files:** `frontend/src/pages/DashboardPage.vue`, `frontend/src/pages/AssetListPage.vue`

**Verification only — no implementation expected.**

Confirm during implementation:
- `DashboardPage.vue` line 4: `<DashboardSkeleton v-if="dashboardStore.loading && !overview?.asset_count" />` — verify this condition is correct. With the new staleness guard, `loading` is only true during an actual network request, so the skeleton correctly shows on first load and after TTL expiry, but not during staleness-guard skips. No change needed.
- `AssetListPage.vue`: `<AssetCardSkeleton v-for="i in 3" :key="i" />` inside `v-if="assetStore.loading"` — verify still correct. No change expected.

If either wiring is found broken, fix it. Otherwise mark done.

---

### Unit 6 — ChildWishesPage: Days-to-Wish Hint
**File:** `frontend/src/pages/child/ChildWishesPage.vue`

**Approach:**

1. **Add ledger fetch to `load()`:** Change `Promise.all([listChildWishes(), getChildWishStats()])` to `Promise.all([listChildWishes(), getChildWishStats(), getCoinLedger()])`. Store result in `const ledger = ref<CoinTransaction[]>([])`.

2. **Add `daysToWish(wishId: string): number | null` computed helper:**
   ```
   - Find priority_simulation item where wish_id === wishId
   - If not found or star_coin_cost is null → return null
   - remaining = star_coin_cost - stats.balance
   - If remaining <= 0 → return null (already affordable, handled by progress >= 1 branch)
   - Filter ledger to entries where amount > 0 AND created_at is within last 7 calendar days
   - Count distinct calendar days with at least one earn entry
   - If distinct days < 3 → return null
   - daily_avg = sum(earn amounts in last 7 days) / 7
   - If daily_avg <= 0 → return null
   - return Math.ceil(remaining / daily_avg)
   ```

3. **Update progress area template** — replace the `<span class="jar-pct">` line with the priority chain (R21):
   ```vue
   <span v-if="(wish.progress ?? 0) >= 1" class="jar-pct full-msg">
     积分已够！快让爸妈实现吧 🎉
   </span>
   <span v-else-if="daysToWish(wish.id) !== null" class="jar-pct days-hint">
     再做约 {{ daysToWish(wish.id) }} 天家务就能实现 🎯
   </span>
   <span v-else class="jar-pct">
     {{ Math.round((wish.progress ?? 0) * 100) }}%
   </span>
   ```

4. **Import `getCoinLedger`** from `@/api/coins` and `CoinTransaction` type.

**Calendar day logic:** Use `new Date(tx.created_at).toDateString()` to bucket transactions by calendar day. Compare against `new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)` for the 7-day cutoff.

**Test scenarios:**
- Child with 5 days of earn history, balance=10, star_coin_cost=50, daily_avg=8 → shows "再做约 5 天家务就能实现 🎯"
- Child with only 2 days of earn history → shows percentage fallback
- Child with daily_avg=0 (no earns in last 7 days) → shows percentage fallback
- Child with progress >= 1 → shows "积分已够！快让爸妈实现吧 🎉" regardless of history
- Wish without `has_cost_set` → no progress bar shown (existing guard, unchanged)
- Wish with `has_cost_set` but no matching `priority_simulation` entry → shows percentage fallback

---

## Sequencing

```
Unit 1 (timeout)          — independent, do first (5 lines)
Unit 2 (dedup+staleness)  — independent of others
Unit 3 (invalidation)     — depends on Unit 2 (needs invalidateDashboard export)
Unit 4 (stale indicator)  — depends on Unit 2 (needs lastFetchedAt + force param)
Unit 5 (verification)     — independent, quick check
Unit 6 (days-to-wish)     — independent of Units 1–5
```

Units 1, 2, 5, 6 can be done in parallel. Unit 3 and 4 must follow Unit 2.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/api/index.ts` | Add timeout branch in request interceptor |
| `frontend/src/stores/dashboard.ts` | Add dedup + staleness guard + force param + invalidateDashboard |
| `frontend/src/stores/asset.ts` | Call invalidateDashboard() in 7 write actions |
| `frontend/src/stores/liability.ts` | Call invalidateDashboard() in 4 write actions |
| `frontend/src/pages/DashboardPage.vue` | force:true in onRefresh(), stale indicator |
| `frontend/src/pages/child/ChildWishesPage.vue` | Add ledger fetch, daysToWish helper, priority chain template |

No new files. No backend changes.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `_fetchPromise` ref holds a Promise — Pinia may warn about non-serializable state | Use a plain module-level variable (`let _fetchPromise: Promise<void> \| null = null`) instead of a ref, keeping it outside the reactive store state |
| `invalidateDashboard()` called from asset/liability stores creates a circular store dependency | Use `useDashboardStore()` lazily inside each action (not at store init) — Pinia supports this pattern |
| `daysToWish()` called in template for each wish on every render | Memoize with a computed Map keyed by wish_id, or accept the cost (list is small, ≤10 wishes) |
| Stale indicator visible on first load before any fetch completes | Guard: `isShowingCachedData` requires `lastFetchedAt !== null` — on first load it's null, so indicator never shows |

---

## Test File

No dedicated test file exists for these stores/pages. The existing E2E regression suite (`tests/e2e/`) covers integration behavior. Unit-level test scenarios are enumerated per implementation unit above for manual verification during implementation.

If a unit test file is added in the future: `frontend/src/stores/dashboard.test.ts`

---

## Checklist

- [ ] Unit 1: Timeout split in `api/index.ts`
- [ ] Unit 2: Dedup + staleness guard + force param in `dashboard.ts`
- [ ] Unit 3: `invalidateDashboard()` in asset + liability stores
- [ ] Unit 4: Force pull-to-refresh + stale indicator in `DashboardPage.vue`
- [ ] Unit 5: Verify skeleton wiring in `DashboardPage.vue` + `AssetListPage.vue`
- [ ] Unit 6: Days-to-wish hint in `ChildWishesPage.vue`
- [ ] Run `npm run typecheck` — zero errors
- [ ] Run `npm run lint` — zero errors
