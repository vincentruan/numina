# Area 4 — Main app navigation coverage (every tab + sub-pages + data validation)

Shared conventions in [`_common.md`](../../_common.md).

> **Why this area exists:** Areas 1–3 test *features*; this area tests
> *navigation completeness* — that **every bottom-nav tab and its sub-pages
> render, navigate, and validate data correctly**, with special attention to the
> **currency-switch bug class** (amounts not re-converted by exchange rate after
> switching `default_currency`). The currency bug was confirmed by source audit
> (see "Currency-switch bug class" below) and is the user's explicit ask.
>
> **TabBar source:** `components/common/AppTabBar.vue` — 6 tabs (dashboard /
> wishes / ai / liabilities / baby[owner-only] / settings), order 1–6, flex:1
> equal width, `activeTab` computed from path prefix.

Auth: adult session as `demouser` via the cookie+localStorage injection
fallback (SKILL.md "Phase 2 fallback"). All routes under `${BASE}`.

## Currency-switch bug class (confirmed by source — the user's explicit ask)

**Root cause (grounded):**
- `composables/useCurrency.ts` → `format(amount)` calls `formatCurrency(amount, currency.value)`.
- `utils/format.ts:formatCurrency` (L16-44) applies **symbol + locale grouping only — NO rate factor**. Changing currency re-renders the same number with a new symbol.
- `components/common/MoneyDisplay.vue:displayValue` (L160-178) formats `props.amount` directly. `rateInfo` (fetched via `useExchangeRate`) feeds **only the tooltip popover** (`originalAmountDisplay` L131-137, `rateDisplay` L143-146) — the displayed number is never multiplied by `rateInfo.rate`.
- The **only** path that actually converts is the backend: `services/dashboard.py:get_overview` (L54-120) server-converts each asset/liability to `user.default_currency` via `ExchangeRateService.convert` (`server/packages/domain/exchange_rate/service.py:95`) **before** summing. So dashboard *aggregates* are currency-correct; per-record list/detail/form pages are NOT.

**Per-page behavior (verify each):**

| Page | Site (file:line) | Source passed? | Re-converts on switch? |
|------|------------------|----------------|------------------------|
| Dashboard NetWorthCard totals | backend-converted sums | n/a | **Yes (server-side)** — correct |
| WishListPage price | `¥{{ formatPrice(wish.expected_price) }}` (WishListPage.vue:86) | raw | **NO** — hard-coded `¥` + raw value (double-¥ if formatPrice ever prepends; wrong symbol + no conversion) |
| LiabilityListPage total | `formatAmountDisplay(totalAmount)` (L50) — client sum of raw `remaining_amount` | raw | **NO** — symbol-only; **sums across currencies without conversion** |
| LiabilityDetailPage amounts | `<MoneyDisplay :amount="Number(liability.remaining_amount)">` (L9,56,59) | raw | **NO** — `sourceCurrency` NOT passed → even tooltip suppressed; symbol-only |
| AssetDetailPage current_value | `<MoneyDisplay :amount="asset.current_value" :source-currency="asset.currency">` (L30-42) | raw | **NO display conversion** — tooltip shows rate/original, but displayed number = raw value re-symbolled to user currency (e.g. $10,000 USD shown as "¥10,000.00" after switching to CNY — **the exact reported bug**) |
| AssetDetailPage daily_cost | `¥{{ asset.daily_cost.toFixed(2) }}` (template) | raw | **NO** — hard-coded ¥, ignores currency entirely |

### C4.0 Currency switch — the bug-class smoke test

```
# 1) Baseline: capture displayed amounts in CNY (default)
bsk navigate ${BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk evaluate --session <id> --expr "JSON.stringify({cur: localStorage.getItem('numina_user') && JSON.parse(localStorage.getItem('numina_user')).default_currency})"
# Note the current currency (expect CNY) and navigate to each money-bearing page, recording the displayed numbers.
bsk navigate ${BASE}assets --session <id> --wait-until networkidle
bsk snapshot --session <id>     # record each asset's displayed current_value
bsk navigate ${BASE}assets/<usd-asset-id> --session <id> --wait-until networkidle
bsk snapshot --session <id>     # record the detail current_value + daily_cost
bsk navigate ${BASE}liabilities --session <id> --wait-until networkidle
bsk snapshot --session <id>     # record totalAmount + each liability remaining
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>     # record each wish expected_price

# 2) Switch currency to USD (or any non-CNY) via Settings → default-currency cell
bsk navigate ${BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # default-currency cell → CurrencyPicker
bsk snapshot --session <id>
bsk click @eM --session <id>     # select USD
bsk snapshot --session <id>     # confirm picker closed + cell shows USD
bsk wait-ms 1s                  # let updateSetting + fetchMe settle

# 3) Re-visit each page and compare displayed numbers to baseline
bsk navigate ${BASE}assets --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk navigate ${BASE}assets/<usd-asset-id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk navigate ${BASE}liabilities --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c4.0-currency-switch.png
```

Prerequisite: at least one asset/liability with `currency ≠ CNY` (e.g. a USD-denominated asset). If all records are CNY, the bug is masked — note in report and skip the per-record assertions.

Assertions:
- [ ] After switching to USD, the **symbol** changes to `$` on every money display (confirms the switch took effect)
- [ ] **Dashboard net-worth totals ARE re-converted** (correct behavior): the number changes by ~the CNY→USD rate (e.g. ¥59M → ~$8.1M at ~7.25)
- [ ] **BUG — AssetDetailPage `current_value`**: a USD asset's value stays the **same number** but is now shown as `$<same-number>` instead of being the already-USD value (no double-conversion, but also a CNY asset would wrongly show `$<cny-number>` — wrong magnitude). Verify a CNY asset shows `$<cny-amount>` (wrong — should be /7.25)
- [ ] **BUG — AssetDetailPage `daily_cost`**: hard-coded `¥` does NOT change to `$` (symbol ignored entirely on currency switch)
- [ ] **BUG — LiabilityListPage `totalAmount`**: client-side sum of raw `remaining_amount` across mixed currencies is arithmetically wrong AND not re-converted
- [ ] **BUG — WishListPage `expected_price`**: raw value re-symbolled, not converted
- [ ] `[console]` zero errors (the rate fetch `/currencies/rates/{code}` may fire — that's expected, not an error)
- [ ] **Restore**: switch back to CNY and confirm baseline numbers return (no stale state)

> **Reporting this bug:** record the baseline number, the post-switch number, and the expected post-switch number (baseline ÷ rate for CNY→USD). A correct implementation changes the magnitude; the bug leaves the magnitude unchanged and only swaps the symbol. Cite `MoneyDisplay.vue:160-178` (displayValue ignores rate) as the root cause in the report's 初步判断.

---

## Tab 1 — Dashboard (`/`)

Landing component `DashboardPage.vue` (1036 lines). `activeTab` → `dashboard`.

### C4.1 Dashboard tab — render + pull-refresh + FAB + view-mode

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Bottom TabBar renders 6 (or 5 if not owner) tabs; **dashboard tab is active** (highlighted)
- [ ] `van-pull-refresh` present — pull down triggers `onRefresh` (re-fetch assets + overview + liabilities)
- [ ] NetWorthCard renders: totalAssets, netWorth, totalLiabilities (via `MoneyDisplay`), totalDailyCost (via `currency.format`)
- [ ] "新增资产" button → navigates to `/assets/new`
- [ ] View-mode toggle (card↔list) reflects `authStore.user?.view_mode || 'card'`; toggling persists (calls `updateSetting('view_mode', ...)`)
- [ ] FAB menu opens → `onFabAction('import')` → `/settings/import-report`; `onFabAction('add')` → `/assets/new`
- [ ] Selection mode (`enterSelectionMode`) exposes batch delete / more-actions sheet
- [ ] Per-asset card/list item → `/assets/${id}`
- [ ] `[console]` zero errors

### C4.2 Dashboard → analytics sub-page

```
bsk navigate ${BASE}dashboard/analytics --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] AssetAnalyticsPage renders (charts/allocations)
- [ ] Allocation breakdown `{items, total}` renders (not a flat list — CLAUDE.md convention)
- [ ] `[console]` zero errors

---

## Tab 2 — Wishes (`/wishes`) + sub-pages

### C4.3 Wishes tab — list + sort + pull-refresh + liability-strategy link

```
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] **wishes tab active** in TabBar
- [ ] Sort toggle cycles sort modes; `van-pull-refresh` re-fetches
- [ ] "go to liability strategy" button → `/liabilities?focus=liability_strategy`
- [ ] Each wish card shows priority + progress + **price** (`¥{{ formatPrice(wish.expected_price) }}` — verify single ¥, not ¥¥; see yy-double-currency fix)
- [ ] Card → `/wishes/${id}`
- [ ] `[console]` zero errors

### C4.4 Wish form — per-wish currency + all fields

```
bsk navigate ${BASE}wishes/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] `WishFormPage` renders: name (required), description, priceStr + **`<CurrencyButton v-model="form.currency">`** (per-wish currency selectable), priority radio, monthlySavingStr, target_date picker, category picker, converts_to_asset switch
- [ ] Empty name submit → Chinese validation error, no API call
- [ ] Valid submit → 201, navigates to detail
- [ ] Edit mode (`/wishes/:id/edit`) loads existing values
- [ ] `[console]` zero errors

### C4.5 Wish detail — all status-dependent actions

Covered in C2.3; here verify the **full action set** by status:
- [ ] active: realize dialog (purchase_price required + purchase_date required rules), AI chat deep-link (`source:'wish_detail'`), edit, cancel
- [ ] realized/cancelled: reactivate, delete (`:loading="deleting"`)
- [ ] Debt-warning ignore button (W5) when `showDebtWarning` true
- [ ] `[console]` zero errors

---

## Tab 3 — AI (`/ai`) + sub-pages

Navigation coverage only — interaction detail is in [`area3-ai.md`](../g1-adult-stable/area3-ai.md). Here verify each AI sub-route renders + active-tab correctness.

### C4.6 AI hub + every AI sub-route renders

```
for R in ai ai/report ai/chat ai/chat/history ai/time-machine; do
  bsk navigate ${BASE}${R} --session <id> --wait-until networkidle
  bsk snapshot --session <id>
done
```

Assertions:
- [ ] `/ai` → AIHubPage renders (report card + 小鸣 + agents + analysis apps + chat input)
- [ ] `/ai/report` → AIReportPage renders (3-step timeline OR cached report OR empty CTA)
- [ ] `/ai/chat` → AIChatPage/AIChatBox renders (message list + input)
- [ ] `/ai/chat/history` → ChatHistoryPage renders (date-grouped thread list)
- [ ] `/ai/time-machine` → AITimeMachinePage renders (3 tabs: WhatIfSimulator / ProjectionChart / PurchasingPowerCalc)
- [ ] **All `/ai/*` routes show the `ai` tab active** in TabBar
- [ ] `[console]` zero errors

---

## Tab 4 — Liabilities (`/liabilities`) + sub-pages

### C4.7 Liabilities tab — filter + sort + batch + quick-pay

```
bsk navigate ${BASE}liabilities --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] **liabilities tab active**
- [ ] Category filter chips + sort toggle + `van-pull-refresh`
- [ ] Summary `formatAmountDisplay(totalAmount)` (L50) — verify the currency bug: if mixed-currency liabilities exist, the sum is unconverted (see C4.0)
- [ ] Active/inactive tabs; card click → detail; "new" → `/liabilities/new`
- [ ] Batch: selectAll, batchSettle, batchDelete
- [ ] Quick-pay sheet: `payAmount` formatter strips non-numeric; percent buttons `setPayPercent`
- [ ] Validation toasts: `paymentAmountRequired`, `paymentExceedsBalance`, `liabilitySelectFirst`
- [ ] `[console]` zero errors

### C4.8 Liability form — all fields + Vant binding

```
bsk navigate ${BASE}liabilities/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] `LiabilityForm.vue` fields: name, category, original_amount, remaining_amount, monthly_payment, interest_rate
- [ ] Vant `van-field` uses `:model-value` binding (NOT `:value` — Vant4 invariant)
- [ ] Required-field validation (Chinese messages)
- [ ] Submit → 201 → detail; edit mode loads existing
- [ ] `[console]` zero errors

---

## Tab 5 — Baby (`/baby`) — OWNER ONLY

> `v-if="isOwner"` on the tab (`authStore.user?.role === 'owner'`). If demouser
> is not owner, skip this section and note in report. The agent audit confirmed
> demouser is owner/adult, so the tab should be visible.

### C4.9 Baby tab — landing + chore-approval + templates + blind-box

```
for R in baby baby/chore-templates family/chore-approvals blind-box/draws blind-box/gifts blind-box/config baby/calendar/day; do
  bsk navigate ${BASE}${R} --session <id> --wait-until networkidle
  bsk snapshot --session <id>
done
```

Assertions:
- [ ] **baby tab visible** (owner only) + active on `/baby/*`, `/blind-box/*`, `/chore-approvals`
- [ ] `/baby` (BabyPage) renders chore/child management
- [ ] `/baby/chore-templates` + `/:id/edit` render template CRUD
- [ ] `/family/chore-approvals` renders pending chore approvals (owner approves/rejects child chore completions)
- [ ] `/blind-box/draws` (draw history), `/blind-box/gifts` + `/new` + `/:id/edit` (gift CRUD), `/blind-box/config` (config)
- [ ] `/baby/calendar/day` renders day detail
- [ ] `[console]` zero errors

---

## Tab 6 — Settings (`/settings`) + ALL sub-pages

> Settings is the largest sub-tree. This case is a **render smoke test** for every
> settings sub-route (each must render without console errors). Interaction depth
> for AI settings is in [`area3-ai.md`](../g1-adult-stable/area3-ai.md) (C3.7).

### C4.10 Settings tab — landing + every sub-route renders

```
for R in settings settings/categories settings/tags \
         settings/ai settings/ai/provider/new \
         settings/ai/mcp settings/ai/web-search settings/ai/skills settings/ai/agents settings/ai/agents/new \
         settings/devices settings/notifications settings/notifications/threshold \
         settings/password settings/second-factor settings/import-report settings/family/coin-rates stats; do
  bsk navigate ${BASE}${R} --session <id> --wait-until networkidle
  bsk snapshot --session <id>
done
```

Assertions (per route — render + no console error):
- [ ] `/settings` (SettingsPage): family-title edit (owner), theme, theme-color, language, **default-currency cell** (opens CurrencyPicker — the C4.0 switch entry point), AI enable toggle (`aiEnabled = configs.some(c=>c.is_active)`; `enableAINoModel` toast if no model), notifications cell, logout
- [ ] `/settings/categories` + `/settings/tags` — manage CRUD
- [ ] `/settings/ai` (AIConfigPage): draggable config list, API-key reveal/copy, per-slot test (`onTestModel` → `testSuccess`/`testFailed`), add/edit/delete, reset circuit; owner-only
- [ ] `/settings/ai/provider/new` + `/:id/edit` (AIProviderFormPage): provider_name, api_key reveal/copy, base_url, timeout_seconds, max_tokens, per-slot model+capabilities pickers
- [ ] `/settings/ai/mcp`, `/settings/ai/web-search` (+`/form`), `/settings/ai/skills`, `/settings/ai/agents` (+`/new`, `/:id/edit`)
- [ ] `/settings/devices`, `/settings/notifications` (+`/threshold`)
- [ ] `/settings/password`, `/settings/second-factor`
- [ ] `/settings/import-report` (ImportReportPage: upload + parse + preview + confirm; `fileTooLarge` toast on `@oversize`)
- [ ] `/settings/family/coin-rates` (CoinRatesPage)
- [ ] `/stats` (DataStatsPage)
- [ ] **All `/settings/*` + `/family/*` routes show the `settings` tab active**
- [ ] `[console]` zero errors across all routes

### C4.11 Settings — default-currency switch round-trip (C4.0 entry point)

```
bsk navigate ${BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # default-currency cell
bsk snapshot --session <id>      # CurrencyPicker open
bsk click @eM --session <id>     # pick a currency
bsk wait-ms 1s
bsk evaluate --session <id> --expr "JSON.parse(localStorage.getItem('numina_user')).default_currency"
```

Assertions:
- [ ] CurrencyPicker opens with the supported list (CNY/USD/EUR/GBP/JPY/HKD + backend `/currencies` entries)
- [ ] Selecting a currency calls `updateSetting('default_currency', X)` → `authStore.fetchMe()` → localStorage `numina_user.default_currency` updates
- [ ] The cell `:value` reflects the new currency
- [ ] `[console]` zero errors

---

## Cross-tab invariants

### C4.12 activeTab correctness across all routes

```
# Visit one route per tab group, snapshot, assert the highlighted tab
for R in / wishes ai liabilities baby settings; do
  bsk navigate ${BASE}${R} --session <id> --wait-until networkidle
  bsk snapshot --session <id>
  # assert the matching tab is marked active
done
```

Assertions:
- [ ] `/` → dashboard active
- [ ] `/wishes` + `/wishes/*` → wishes active
- [ ] `/ai` + `/ai/*` → ai active
- [ ] `/liabilities` + `/liabilities/*` → liabilities active
- [ ] `/baby` + `/blind-box/*` + `/chore-approvals` → baby active (owner)
- [ ] `/settings` + `/settings/*` + `/family/*` → settings active
- [ ] `[console]` zero errors

### C4.13 Back-navigation + route-guard integrity

```
# Deep-link a protected route while logged out (clear localStorage + cookie)
bsk evaluate --session <id> --expr "localStorage.clear(); 'cleared'"
bsk navigate ${BASE}assets --session <id> --wait-until domcontentloaded
bsk snapshot --session <id>
```

Assertions:
- [ ] Unauthenticated deep-link to `/assets` redirects to `/login` (route guard)
- [ ] After re-establishing session (Phase 2 fallback), the deep-link lands on `/assets` (not `/login`)
- [ ] Browser back from a sub-page returns to the parent tab (no SPA history corruption)
- [ ] `[console]` zero errors

---

## Edit-mode form coverage (the 3 edit routes absent from C4.1–C4.13)

> **Why this section exists:** a 2026-07-21 navigation audit found three edit
> routes with **zero case coverage** (direct or indirect): `assets/:id/edit`,
> `liabilities/:id/edit`, `baby/chores/new`. These reuse the create-form
> components (AssetFormPage / LiabilityFormPage) gated by `route.params.id`,
> except `baby/chores/new` which is a standalone create page. All three
> navigate via `router.back()` on success (NOT push to detail) — a fact that
> would break any test asserting "navigates to /assets/:id".

### C4.14 Asset edit form (`/assets/:id/edit`) — edit-mode load + all fields + currency

```
# Pick an existing asset id from the API first (so the <id> is real)
ASSET_ID=$(curl -s -H "$AUTH" "${API_BASE}/assets" | jq -r '.data[0].id')
bsk navigate ${BASE}assets/${ASSET_ID}/edit --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Grounding: `AssetFormPage.vue` (`isEdit = !!route.params.id`, onMounted
`fetchAsset(id)` + `fetchCategories()`); form component `AssetForm.vue`.

Assertions:
- [ ] Edit mode detected via `route.params.id` → existing asset values loaded into all fields (name, category, purchase_price, current_value, purchase_date)
- [ ] `status` field renders ONLY in edit mode (`v-if="isEdit"`, `AssetForm.vue:132-148`) — 4-option picker in_use/idle/sold/retired (verify NOT present on `/assets/new`)
- [ ] Per-asset-type conditional fields: physical → usage_frequency/expected_lifespan_days(显示为年)/location/annual_maintenance_cost; financial → institution/interest_rate/maturity_date; warranty_expiry_date (physical only)
- [ ] `CurrencyButton v-model="form.currency"` bound in purchase_price left-icon (`AssetForm.vue:86`); `currencySymbol` computed shows ¥/$/€/£/¥/HK$ by `form.currency`
- [ ] "同购入价" `syncPurchasePrice` button in current_value right-icon (`AssetForm.vue:102-109`) copies purchase_price → current_value
- [ ] Required validation (Chinese messages via i18n `assetForm.*Required`): name, category_id, purchase_price, current_value, purchase_date
- [ ] Empty required field submit → validation error, no API call
- [ ] Valid submit → PUT `/assets/{id}` → success toast `toast.updateSuccess` → **`router.back()`** (NOT push to detail — assert history-back lands on the prior page, not `/assets/:id`)
- [ ] **Currency-switch input-side note**: `currencySymbol` only swaps the symbol prefix on amount fields, does NOT multiply by rate (same class as the Area 4 `MoneyDisplay` display bug, but this is the input side where raw amounts are entered — switching currency here changes the symbol on the input, not the stored value's magnitude). Record as input-side observation, not a new bug.
- [ ] `[console]` zero errors

### C4.15 Liability edit form (`/liabilities/:id/edit`) — edit-mode load + all fields

```
LIAB_ID=$(curl -s -H "$AUTH" "${API_BASE}/liabilities" | jq -r '.data[0].id')
bsk navigate ${BASE}liabilities/${LIAB_ID}/edit --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Grounding: `LiabilityFormPage.vue` (`isEdit`, onMounted `fetchLiability(id)`);
form component `LiabilityForm.vue`.

Assertions:
- [ ] Edit mode loads existing liability values: name, category, original_amount, remaining_amount, monthly_payment, interest_rate, start_date/end_date, institution, notes
- [ ] `category` is a hardcoded 5-option popup (mortgage/car_loan/credit_card/personal_loan/other) — NOT store-driven (differs from AssetForm's store-driven categories)
- [ ] `interest_rate` is **required** on liability (non-required on asset-financial)
- [ ] `CurrencyButton v-model="form.currency"` in original_amount left-icon (`LiabilityForm.vue:47`); remaining_amount + monthly_payment show `currencySymbol` prefix (symbol-only, no rate — same input-side note as C4.14)
- [ ] **No edit-only fields** (no status, no image upload, no tags) — liability form is identical in create/edit except pre-filled values
- [ ] Required validation (Chinese i18n `liability.*Required`): name, category, original_amount, remaining_amount, monthly_payment, interest_rate
- [ ] Valid submit → PUT `/liabilities/{id}` → `toast.updateSuccess` → **`router.back()`** (NOT push)
- [ ] `[console]` zero errors

### C4.16 Baby chore create (`/baby/chores/new`) — form + coin_reward validation

```
# owner-only route; demouser is owner (gate confirms)
bsk navigate ${BASE}baby/chores/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Grounding: `BabyChoreCreatePage.vue` (standalone page, no separate form
component, inline `van-form`). API: POST `/family/chore-templates`
(`api/chores.ts:36`). **No edit mode** (edit is a separate route
`baby/chore-templates/:id/edit` → `BabyChoreTemplateEditPage.vue`).

Assertions:
- [ ] `van-nav-bar` with `left-arrow @click-left="$router.back()"` (NOT the PageHeader used by asset/liability forms)
- [ ] Form fields: name (required), emoji (optional), `rewardStr` (required, type=digit, right-icon ⭐), frequency radio (daily/weekly, default daily), assignment_type radio (assigned/pool, default assigned)
- [ ] `assignees` checkbox-group renders ONLY when `assignment_type==='assigned'`; checkboxes populated from `familyStore.members.filter(m.role==='child')` (the gate-discovered child names)
- [ ] **No currency field** — coin_reward is the child star-coin system (⭐), unrelated to the Area 4 currency-switch bug class
- [ ] Required validation: van-field `required` rule on name + rewardStr (non-empty); **plus manual `coin_reward > 0` check** (`parseInt(rewardStr)` — `"0"` → 0 falsy → blocked; non-numeric → NaN → blocked; toast `baby.choreForm.rewardRequired`)
- [ ] Empty name submit → validation error, no API call
- [ ] rewardStr="0" or non-numeric → toast, no API call (the manual `>0` guard)
- [ ] Valid submit → POST `/family/chore-templates` → `baby.choreForm.success` toast → **`router.back()`** (NOT push)
- [ ] `submitting` ref drives van-button `:loading` during the request
- [ ] `[console]` zero errors
