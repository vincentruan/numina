---
date: 2026-04-18
topic: quick-wins-ux-performance
---

# Quick Wins: UX & Performance Polish (6 Tasks)

## Problem Frame

Six high-confidence, low-complexity improvements identified in ideation but not yet implemented.
All are pure frontend changes — no new backend endpoints, no schema migrations required.
`star_coin_cost` per wish is already available via `getChildWishStats().priority_simulation` (no backend touch needed).
Together they improve perceived performance, child UX clarity, and frontend reliability.

---

## Requirements

**Task 1 — AI 端点独立超时配置**

- R1. Requests to `/api/v1/ai/` paths use a 120s timeout; all other requests keep the existing 15s timeout.
- R2. The timeout split is applied by mutating `config.timeout` inside the existing axios request interceptor in `frontend/src/api/index.ts`. The interceptor currently passes config through unchanged — this adds a URL-based branch to set `config.timeout = 120000` for AI paths and `config.timeout = 15000` for all others.
- R3. No other behavior of the interceptor changes.

**Task 2 — Store 级别请求去重（Dashboard）**

- R4. If `fetchAll()` is called while a previous call is still in-flight, the second call returns the same in-flight Promise instead of issuing a new network request.
- R5. Once the in-flight request settles (success or error), the dedup lock is released so subsequent calls work normally.
- R6. `fetchAll()` always returns `Promise<void>`. The dedup path returns the existing in-flight Promise; the staleness-guard early-return (R8) returns `Promise.resolve()`.
- R7-note. Evaluation order inside `fetchAll()`: (1) if a request is in-flight, return the existing Promise; (2) if `lastFetchedAt` is within TTL, return `Promise.resolve()`; (3) otherwise issue a new request.

**Task 3 — Store 级别 Staleness Guard（Dashboard）**

- R7. After a successful `fetchAll()`, a `lastFetchedAt` timestamp is recorded in the dashboard store.
- R8. If `fetchAll()` is called again within 2 minutes of the last successful fetch (and no request is in-flight), it returns `Promise.resolve()` immediately without issuing a network request.
- R9. The following store actions invalidate the staleness guard (reset `lastFetchedAt` to null) so the next `fetchAll()` always fetches fresh data: `createAsset`, `updateAsset`, `deleteAsset`, `updateValue`, `sellAsset`, `retireAsset`, `reactivateAsset` (asset store); `createLiability`, `updateLiability`, `deleteLiability`, `recordPayment` (liability store).
- R10. The TTL is 2 minutes. It is a constant in the store, not a user-configurable setting.
- R11. A single line of muted text — "数据可能不是最新" — is shown below the stats bar in `DashboardPage.vue` when the staleness guard was triggered (i.e., `fetchAll()` was skipped). It is not user-dismissible; it disappears automatically once a fresh fetch completes. No new component is needed — inline conditional text suffices.
- R12. `fetchAll()` accepts an optional `force: boolean = false` parameter. Pull-to-refresh (`onRefresh()` in `DashboardPage.vue`) passes `force: true` to bypass the TTL. Programmatic calls on route mount use the default (`force: false`).

**Task 4 — Skeleton Loading States（Dashboard & Asset List）**

- R13. Verify that `DashboardPage.vue` already wires `DashboardSkeleton.vue` correctly (confirmed: `v-if="dashboardStore.loading && !overview?.asset_count"`). No change needed unless the condition needs adjustment.
- R14. Verify that `AssetListPage.vue` already wires `AssetCardSkeleton.vue` (3×) correctly (confirmed: `v-if="assetStore.loading"`). No change needed unless the condition needs adjustment.
- R15. Task 4 is a verification pass only. If either wiring is found to be incorrect or incomplete during planning, fix it; otherwise mark as done.

**Task 5 + 6 — 心愿「还需几天家务」计算 + 进度条显示优化（ChildWishesPage）**

*(Tasks 5 and 6 are merged — they are both ChildWishesPage.vue changes with a hard dependency.)*

- R16. For each active wish with `has_cost_set === true` and `progress < 1`, display below the progress bar:「再做约 X 天家务就能实现 🎯」
- R17. `X` is calculated as `ceil((star_coin_cost - balance) / daily_avg)` where:
  - `star_coin_cost` is sourced from `getChildWishStats().priority_simulation` matched by wish id (already fetched on mount — no new API call).
  - `balance` is the top-level field from `getChildWishStats()`.
  - `daily_avg` = sum of ledger entries where `amount > 0` (earn transactions only, excluding spend/gift debits) with `created_at` within the last 7 calendar days, divided by 7.
- R18. The hint is hidden (not shown) when: fewer than 3 calendar days in the last 7 have any earn transaction, OR `daily_avg <= 0`. Do not show "∞ days" or negative values.
- R19. The hint is a pure frontend calculation — no new API endpoint.
- R20. Ledger data is fetched once on page mount alongside the existing `listChildWishes()` + `getChildWishStats()` calls.
- R21. Display priority chain for the progress area of each active wish (evaluated top-to-bottom, first match wins):
  1. If `progress >= 1` → show「积分已够！快让爸妈实现吧 🎉」
  2. Else if hint is computable (R17–R18 conditions met) → show hint
  3. Else → show `Math.round((wish.progress ?? 0) * 100) + '%'` (existing behavior, zero regression)

---

## Success Criteria

- On first load, `DashboardPage` shows `DashboardSkeleton` while data is loading.
- If the user navigates away and returns within 2 minutes of a successful fetch, no new network request is issued and the "数据可能不是最新" indicator is visible.
- If the user manually pulls to refresh within the TTL, a network request IS issued (force bypass works).
- Concurrent calls to `fetchAll()` result in exactly one network request.
- AI chat/report pages do not time out on slow LLM responses (120s window).
- A child with ≥3 days of earn history sees a concrete day-count on each active wish.
- Asset list page shows skeleton cards instead of blank white during load (verify existing wiring).

## Scope Boundaries

- No new backend endpoints. No backend schema changes. `star_coin_cost` is sourced from the already-fetched `getChildWishStats()` response.
- Staleness guard applies only to `fetchAll()` in the dashboard store, not to individual fetch methods.
- Task 4 is verification only — no new skeleton component wiring unless existing wiring is found broken.
- No changes to `DashboardSkeleton.vue` or `AssetCardSkeleton.vue` component internals.
- No Service Worker, no sessionStorage caching — those are separate ideas.
- The "数据可能不是最新" indicator appears only on `DashboardPage`, not on other pages.

## Key Decisions

- **2-minute TTL (R10):** Balances freshness vs. unnecessary requests for a family app where data changes infrequently. Hardcoded constant, not configurable.
- **Dedup via single Promise ref (R4–R6):** Simpler than a Map-based approach since only `fetchAll()` is targeted.
- **star_coin_cost from getChildWishStats() (R17):** Avoids any backend schema change. The field is already returned in `priority_simulation` items.
- **Earn-only daily_avg (R17):** Filters `amount > 0` to exclude spend/gift debits, giving the true earning rate.
- **Percentage fallback (R21 step 3):** Preserves existing behavior when hint cannot be computed, zero regression risk.
- **force parameter (R12):** Pull-to-refresh must bypass TTL — a force flag is the minimal correct solution.
- **Tasks 5+6 merged:** Both are ChildWishesPage.vue changes with a hard dependency; splitting them creates no value.

## Dependencies / Assumptions

- `DashboardSkeleton.vue` and `AssetCardSkeleton.vue` exist and are functional (confirmed).
- `/child/coins/ledger` returns `amount` (int, can be negative) and `created_at` per transaction (confirmed).
- `getChildWishStats()` returns `priority_simulation` array with per-wish `star_coin_cost` and top-level `balance` (confirm shape during planning).
- Batch delete and batch status-change in `DashboardPage.vue` call `dashboardStore.fetchAll()` directly — these already bypass the staleness guard naturally (direct call with no force flag needed since they trigger a fresh fetch).

## Outstanding Questions

### Deferred to Planning

- [Affects R17][Needs research] Confirm exact shape of `getChildWishStats().priority_simulation` — verify each item has a wish `id` field for matching and a `star_coin_cost` field.
- [Affects R9][Technical] Confirm that batch operations in `DashboardPage.vue` (batch delete, batch status-change) call `fetchAll()` directly and do not need store-level invalidation hooks.

## Next Steps
→ `/ce:plan` for structured implementation planning
