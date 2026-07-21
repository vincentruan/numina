# Area 5 — Child app navigation coverage (every tab + sub-pages)

Shared conventions in [`_common.md`](./_common.md).

> **Why this area exists:** Area 1 tests child *features*; this area tests
> **navigation completeness** for the child app — that **every bottom-nav tab
> and its sub-pages render and navigate correctly**.
>
> **Child TabBar source:** `frontend/apps/child/src/components/ChildTabBar.vue` —
> 5 tabs (home / wishes / tasks / treasures / ledger), each a `van-icon` size 22,
> `routeToTab` maps by first path segment, `onTabChange` does `router.push` (or
> `replace` if same path).
>
> **No currency layer:** the child app is coin-based (integer `parseInt` in
> ChildLedger gift flow; no `useCurrency`/`formatCurrency`/`MoneyDisplay`
> imports). The currency-switch bug class (Area 4 C4.0) does NOT apply here.
> Child coin amounts are single-currency (⭐) by design.

Auth: docker mode reuses the adult session (same origin via nginx). Dev mode
requires the child two-step emoji-PIN injection (see `_common.md` "Child session
injection (dev mode — password-manager fallback)"). All routes under
`${CHILD_BASE}`.

## Child routes (grounded from `frontend/apps/child/src/router/index.ts`)

| path | name | component | tab? |
|------|------|-----------|------|
| `` (root) | ChildHome | ChildHomePage.vue | **tab: home** |
| `tasks` | ChildTasks | ChildTasksPage.vue | **tab: tasks** |
| `ledger` | ChildLedger | ChildLedgerPage.vue | **tab: ledger** |
| `wishes` | ChildWishes | ChildWishesPage.vue | **tab: wishes** |
| `wishes/new` | ChildWishCreate | ChildWishCreatePage.vue | sub |
| `wishes/:id` | ChildWishDetail | ChildWishDetailPage.vue | sub |
| `assets/:id` | ChildAssetDetail | ChildAssetDetailPage.vue | sub |
| `treasures` | ChildTreasures | ChildTreasuresPage.vue | **tab: treasures** |
| `blind-box` | (redirect) | → `/treasures` | — |
| `calendar/day` | ChildDayDetail | ChildDayDetailPage.vue | sub |
| `settings` | ChildSettings | ChildSettingsPage.vue | sub (no tab) |

`ChildLayout.vue` renders `<router-view>` + `<ChildTabBar />`; KeepAlive
includes ChildHome/Tasks/Ledger/Wishes/Treasures. Auth guard `verifyChildSession()`
calls `authStore.fetchMe()`; non-child redirects to adult login.

---

## Tab 1 — Home (`/`)

### C5.1 Home tab — render + calendar + chore summary

```
bsk navigate ${CHILD_BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] **home tab active** in ChildTabBar
- [ ] `van-pull-refresh` present
- [ ] `ChildCalendar :fetch-month="fetchChildMonth" day-route="/calendar/day" variant="child"` renders
- [ ] Computeds populated: `completedChores`, `pendingChores`, `totalChoreCoins`
- [ ] Tapping a calendar day → `/calendar/day`
- [ ] `[console]` zero errors

## Tab 2 — Wishes (`/wishes`) + sub-pages

### C5.2 Wishes tab — list + redeem + sectioned statuses

```
bsk navigate ${CHILD_BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] **wishes tab active**
- [ ] `van-pull-refresh`; sectioned lists: active / pending_review / redemption_requested / realized / rejected
- [ ] `totalWishes`, `wishDaysMap`, `wishTintMap` populated (constellation tint + days estimate)
- [ ] `redeem(wish.id)` action on redeemable wishes
- [ ] FAB → `/wishes/new`
- [ ] `[console]` zero errors

### C5.3 Wish create + detail sub-pages

```
bsk navigate ${CHILD_BASE}wishes/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
# fill name, submit
bsk fill @eN --value 测试心愿 --session <id>
bsk snapshot --session <id>
bsk click @eM --session <id>
bsk navigate ${CHILD_BASE}wishes/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] `ChildWishCreatePage`: name (required `*`), emoji field + picker, description, priority buttons, submit `submitWish`; back → `router.replace('/wishes')`
- [ ] Empty name submit → validation error, no API call
- [ ] `ChildWishDetailPage`: back button, redeem button, wishId resolved
- [ ] `[console]` zero errors

## Tab 3 — Tasks (`/tasks`)

### C5.4 Tasks tab — day nav + complete/abandon + auto-draw

```
bsk navigate ${CHILD_BASE}tasks --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] **tasks tab active**
- [ ] Prev/next day navigation (day label via `dateLabel`, `isToday` computed)
- [ ] Available chore → `doComplete` sheet; abandon → `doAbandon` sheet
- [ ] `allDone` computed reflects completion state
- [ ] Auto-draw overlay (`autoDraw`) triggers when eligible
- [ ] `[console]` zero errors

## Tab 4 — Treasures (`/treasures`)

### C5.5 Treasures tab — coins + draw history

```
bsk navigate ${CHILD_BASE}treasures --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] **treasures tab active**
- [ ] `van-pull-refresh`; `totalCoins` computed; draw history (formatted via `formatDate`)
- [ ] `/child/blind-box` redirects to `/treasures` (route alias — verify via `bsk evaluate "location.pathname"`)
- [ ] `[console]` zero errors

## Tab 5 — Ledger (`/ledger`)

### C5.6 Ledger tab — transactions + sibling gift (coin-based)

```
bsk navigate ${CHILD_BASE}ledger --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] **ledger tab active**
- [ ] Transaction list renders (emoji + narrative + relative_time + amount; positive/negative color)
- [ ] Gift button visible only when `hasSiblings` true (demouser has 2 children → visible)
- [ ] Gift flow: sibling pick → `giftAmountStr` field; `giftAmount`/`giftExceedsBalance`/`giftRemaining`/`giftCanSubmit` computeds; `doGift` → `childGrantedStars` toast
- [ ] **Coin amounts are integers** (`parseInt`-based) — NOT currency-formatted (no ¥/$; no exchange-rate path) — confirm the child app has no currency layer
- [ ] Empty state (EmptyState) shows when no transactions
- [ ] `[console]` zero errors

---

## Sub-pages (no tab)

### C5.7 Child asset detail

```
bsk navigate ${CHILD_BASE}assets/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] `ChildAssetDetailPage` renders (name, emoji, value as seen by child role)
- [ ] **No adult-only fields leak** (no purchase_price edit, no sell button, no interest_rate)
- [ ] Back → `/wishes` (per `router.replace`)
- [ ] `[console]` zero errors

### C5.8 Child day detail

```
bsk navigate ${CHILD_BASE}calendar/day --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] `ChildDayDetailPage` renders; `isParentView = !!childId` toggles title (`pageTitle`)
- [ ] `[console]` zero errors

### C5.9 Child settings

```
bsk navigate ${CHILD_BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Theme mode buttons, locale buttons, logout (confirm + `logoutSuccess` toast)
- [ ] **No adult-only settings** (no AI config, no family management, no default-currency cell)
- [ ] `[console]` zero errors

---

## Cross-tab invariants

### C5.10 activeTab correctness + route guard

```
for R in / wishes tasks treasures ledger; do
  bsk navigate ${CHILD_BASE}${R} --session <id> --wait-until networkidle
  bsk snapshot --session <id>
done
# Guard: clear child session, deep-link a protected child route
bsk evaluate --session <id> --expr "localStorage.clear(); 'cleared'"
bsk navigate ${CHILD_BASE}wishes --session <id> --wait-until domcontentloaded
bsk snapshot --session <id>
```

Assertions:
- [ ] Each tab route shows the matching tab active
- [ ] Unauthenticated deep-link to `/wishes` redirects to adult login (`${mainBaseUrl}/login?redirect=/child/wishes`) — child guard `verifyChildSession()` rejects non-child
- [ ] After re-establishing child session (dev: PIN injection; docker: adult session), deep-link lands on `/wishes`
- [ ] `[console]` zero errors
