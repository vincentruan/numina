# Area 2 — Main app financial management (财务管理能力优化)

Shared conventions in [`_common.md`](./_common.md).

Auth: establish the adult session as `demouser` / `DemoPass123` first. The
default `bsk fill` form-login (SKILL.md Phase 2) can trigger a password-manager
extension that hijacks the Agent Window tab. **Prefer the cookie+localStorage
injection fallback** (SKILL.md "Phase 2 fallback") — it never focuses the
password field, so the extension never activates. All routes under `${BASE}`
(adult SPA).

Covers Plan A (`finance_coach` capability) + Plan B (P0 business touchpoints
W1/W2/W4/W5, L1/L2, D2, A1a/A1b). All features verified landed in
`frontend/apps/main/src/`.

## Existing cases — core financial flows

### C2.1 Dashboard (DashboardPage) — totals, net worth, trend

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Asset total + liability total + net worth render
- [ ] Net worth = assets − liabilities (verify the arithmetic, not just presence)
- [ ] Trend chart (ECharts) renders with data points
- [ ] Money values display as formatted strings (post Float→Numeric migration, backend returns str; frontend may Number()-coerce for display — check no `NaN`/`undefined`)
- [ ] Allocation breakdown `{items, total}` renders (not a flat list)
- [ ] `[console]` zero errors

### C2.2 Wish list (WishListPage) — savings progress + advice + debt hint

```
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Wish list renders with priority + progress
- [ ] WishSavingsProgress component shows saved/target bar for wishes with savings
- [ ] WishAdviceCard (W4) renders AI advice for wishes (if AI enabled + advice generated)
- [ ] Debt warning hint bar appears ABOVE the W4 card when a wish's category exceeds family debt thresholds (W5 linkage)
- [ ] Tap a wish → navigates to WishDetail

### C2.3 Wish detail (WishDetailPage) — savings log + record + afford bar

```
# Navigate to a wish with savings, e.g. /wishes/:id
bsk snapshot --session <id>
```

Assertions:
- [ ] WishSavingsProgress shows progress bar + percentage
- [ ] "记录储蓄" button → opens WishSavingsRecordDialog (van-dialog/popup)
- [ ] "储蓄日志" button → opens WishSavingsLogDialog (list of past savings entries)
- [ ] Afford bar (useAffordBar composable, 4 states) renders: can-afford / cannot / loading / error
- [ ] "忽略" button (W5 debt warning) calls T3 backend route, hides the hint
- [ ] A1b buttons (wish_detail → /ai/chat) present when AI enabled

### C2.4 Wish savings record dialog — amount input + submit

```
bsk snapshot --session <id>   # get dialog refs after opening
bsk fill @eN --value 100 --session <id>
bsk click @eM --session <id>   # confirm button
```

Assertions:
- [ ] Amount field accepts numeric input
- [ ] Submit POSTs to savings endpoint, returns 201
- [ ] Progress bar updates after successful record
- [ ] Invalid amount (negative / non-numeric) → validation error

### C2.5 Liability list (LiabilityListPage) — strategy card + interest forecast

```
bsk navigate ${BASE}liabilities --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Liability list renders with category, remaining amount, monthly payment
- [ ] LiabilityStrategyCard renders (client-side monthly-interest sum + 估算)
- [ ] InterestForecast component shows projection (hides when interest_rate=0, per spec §6.1)
- [ ] PaymentCountdown shows days until next payment
- [ ] `?focus=liability_strategy` query param scrolls to / highlights strategy card
- [ ] Tap liability → navigates to LiabilityDetail

### C2.6 Liability detail (LiabilityDetailPage) — simulate extra payment

```
# /liabilities/:id
bsk snapshot --session <id>
# open SimulateExtraDialog
```

Assertions:
- [ ] SimulateExtraDialog opens with extra_monthly input
- [ ] calc_amortization (equal / min-payment modes) runs client-side
- [ ] min-payment non-cover boundary: rate=60% edge case handled (no crash)
- [ ] Result shows revised payoff timeline + interest saved
- [ ] A1b button (liability_detail → /ai/chat) present when AI enabled

### C2.7 Liability create/edit form (LiabilityFormPage)

```
bsk navigate ${BASE}liabilities/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Form fields: name, category, original_amount, remaining_amount, monthly_payment, interest_rate
- [ ] Vant van-field uses `:model-value` binding (not `:value`)
- [ ] Submit POSTs, returns 201, navigates to detail
- [ ] Required field validation (Chinese error messages)

### C2.8 Asset list + detail + sell flow

```
bsk navigate ${BASE}assets --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Asset list renders with category filter + status badges (in_use/idle/retired/sold)
- [ ] Money fields (purchase_price, current_value) display correctly post-Float→Numeric migration
- [ ] Tap asset → AssetDetailPage
- [ ] From detail → 出售 button → AssetSellPage
- [ ] Sell form: sell_price + sell_fee → net_recovery shown → submit returns 201

---

## New cases — Plan A: FinanceCoachCard (D2)

Covers Plan A `finance_coach` capability + Plan B D2 dashboard card.
Component: `components/dashboard/FinanceCoachCard.vue`. Backend:
`POST /ai/finance-coach/generate?force=false` (8h capability-cache, streams
`finance_coach.result` frame with `suggestions[]`). AI must be enabled.

### C2.9 FinanceCoachCard — cached state render

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c2.9-finance-coach-cached.png
```

Prerequisite: a finance_coach cache already exists for demouser (run generate
once before, or seed). If no cache, skip to C2.10 first.

Assertions:
- [ ] `FinanceCoachCard` renders on the dashboard with the cached suggestions
- [ ] Each suggestion shows: severity, title, action, target_type, cta_label
- [ ] `generated_at` timestamp displayed (human-readable)
- [ ] A "刷新" / regenerate affordance is present (calls generate with `force=true`)
- [ ] `[console]` zero errors (no SSE/EventSource errors after cached load)

### C2.10 FinanceCoachCard — generate (stream) + cache populate

```
# If no cache: click generate on the card
bsk snapshot --session <id>
bsk click @eN --session <id>     # "生成" / generate button
bsk wait-ms 8s                   # finance_coach streams; poll if needed
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c2.10-finance-coach-generate.png
```

Assertions:
- [ ] Card shows loading/spinner state during stream
- [ ] Stream completes; suggestions render (non-empty `suggestions[]`)
- [ ] After completion, the result is cached (revisiting dashboard shows cached state without re-stream — verify via `[console]` no second generate POST)
- [ ] `[console]` zero errors (blank-response / stream-stuck fixes from chat bugs do not regress here)

### C2.11 FinanceCoachCard — entity-change invalidation

```
# After C2.10 cached: create/edit an asset or liability, then return to dashboard
bsk navigate ${BASE}assets/new --session <id> --wait-until networkidle
# ... create an asset (C2.7-style flow) ...
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] After an asset/liability write, the finance_coach cache is invalidated (Plan A T9 entity-change invalidation)
- [ ] Dashboard card no longer shows stale `generated_at` — it re-generates or shows a regenerate prompt
- [ ] `[console]` zero errors

---

## New cases — Plan B: W1/W2 savings + afford bar rhythm

Covers W1 (wish savings fields: `saved_amount`/`target_date`/`monthly_saving` +
`WishSavingsLog`) and W2 (afford bar refactored from "net worth can afford" to
"months-to-reach by monthly-savings rhythm" = `(price-saved)/monthly_saving`).

### C2.12 Wish savings fields — monthly_saving + target_date

```
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Open a wish that has monthly_saving + target_date set
bsk click @eN --session <id>
bsk snapshot --session <id>
```

Assertions:
- [ ] Wish detail shows `monthly_saving` (月存) and `target_date` (目标日期) fields (W1)
- [ ] WishSavingsProgress shows `已存 ¥X / ¥Y (Z%)` with the savings ratio
- [ ] Afford bar shows the months-to-reach projection = `(price - saved) / monthly_saving` (W2 rhythm, NOT net-worth affordability)
- [ ] If `monthly_saving` is 0/null, afford bar degrades gracefully (shows "未设定月存" or cannot-compute, not NaN/crash)
- [ ] `[console]` zero errors

### C2.13 Afford bar — 4 states + edge cases

```
# Navigate to wishes with different savings states
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions (verify across multiple wishes if available):
- [ ] can-afford state: saved ≥ price → green/positive afford bar
- [ ] cannot (on-track) state: saved < price but monthly_saving set → shows "≈ N 月达成" projection
- [ ] loading state: brief skeleton/spinner while computing
- [ ] error state: if compute fails, shows error affordance (not a blank bar)
- [ ] Edge: wish with `price=0` or `saved>price` handled without NaN
- [ ] `[console]` zero errors

### C2.14 Wish savings log — entry list + add entry updates progress

```
# On a wish detail, open the savings log
bsk snapshot --session <id>
bsk click @eN --session <id>     # "储蓄日志" button → WishSavingsLogDialog
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c2.14-savings-log.png
```

Assertions:
- [ ] WishSavingsLogDialog lists past savings entries (amount + timestamp)
- [ ] Each entry reflects a `WishSavingsLog` row (W1 table)
- [ ] Adding a new entry (via WishSavingsRecordDialog, C2.4) appends to this log
- [ ] Progress bar + afford bar recompute after the new entry
- [ ] `[console]` zero errors

---

## New cases — Plan B: W5 debt-warning + L1/L2 simulate endpoint

Covers W5 (high-interest liability ↔ wish linkage hint) and L1/L2
(`calc_amortization` util + `POST /liabilities/simulate` endpoint). Model:
`FamilyDebtThresholds` (GET/PUT `/family/debt-thresholds`, owner-only).

### C2.15 Debt-warning hint bar — threshold linkage

```
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Prerequisite: demouser has a high-interest liability (interest_rate ≥ category
threshold in `FamilyDebtThresholds`).

Assertions:
- [ ] Debt warning hint bar appears ABOVE the WishAdviceCard (W5) for wishes in categories exceeding the family debt threshold
- [ ] Hint text references the high-interest liability (e.g. "建议优先还债 利率 18%")
- [ ] "忽略" button hides the hint (persists via T3 backend route)
- [ ] After "忽略", hint does NOT reappear on reload for that wish
- [ ] Wishes in categories BELOW the threshold show no hint bar
- [ ] `[console]` zero errors

### C2.16 Debt thresholds config — owner GET/PUT

```
# Owner session. Hit the thresholds endpoint (or via settings UI if present)
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/family/debt-thresholds" | jq .
```

Assertions:
- [ ] GET `/family/debt-thresholds` returns the family's per-category thresholds (owner-only — child/non-owner gets 403)
- [ ] PUT updates a threshold; subsequent GET reflects the change
- [ ] After raising a threshold above a liability's rate, the C2.15 hint bar disappears for that category
- [ ] `[console]` zero errors on the settings/threshold UI if present

### C2.17 Liability /simulate endpoint — amortization modes

```
# Direct API test (L1/L2 single-source amortization util + route)
curl -s -X POST "${API_BASE}/liabilities/simulate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"liability_id":"<id>","mode":"equal","extra_monthly":500}' | jq .
curl -s -X POST "${API_BASE}/liabilities/simulate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"liability_id":"<id>","mode":"min-payment","extra_monthly":0}' | jq .
```

Assertions:
- [ ] `mode=equal` returns a revised payoff timeline (months) + total interest + interest saved
- [ ] `mode=min-payment` with `extra_monthly=0` returns the baseline min-payment schedule
- [ ] min-payment non-cover boundary: when min-payment < monthly interest (rate=60% edge), returns a structured "cannot-pay-off" result (no 500/crash, no infinite loop — 1200-month cap)
- [ ] Frontend SimulateExtraDialog (C2.6) consumes the same util client-side; results match the API
- [ ] `[console]` zero errors

---

## New cases — Plan B: A1b passive buttons (wish/liability → /ai/chat)

Covers A1b: passive "ask AI" buttons on wish_detail and liability_detail that
deep-link into `/ai/chat` with context. Already referenced in C2.3/C2.6; this
case verifies the navigation + context handoff.

### C2.18 A1b — wish_detail → /ai/chat context handoff

```
# On a wish detail page (AI enabled)
bsk navigate ${BASE}wishes/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # the A1b "问 AI" / consult button
bsk wait-ms 1s
bsk snapshot --session <id>
```

Assertions:
- [ ] Clicking the A1b button navigates to `/ai/chat` (with a context query param or prefilled message referencing the wish)
- [ ] The chat page loads with the wish context (thread or prefilled prompt mentions the wish)
- [ ] No blank/empty state (chat input is ready, not stuck loading)
- [ ] `[console]` zero errors

### C2.19 A1b — liability_detail → /ai/chat context handoff

```
bsk navigate ${BASE}liabilities/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # the A1b button on liability detail
bsk wait-ms 1s
bsk snapshot --session <id>
```

Assertions:
- [ ] Navigates to `/ai/chat` with liability context
- [ ] Chat loads ready (not stuck); liability context visible or prefilled
- [ ] `[console]` zero errors

---

## New cases — Plan B: money Float→Numeric migration display

Covers the money-type migration (Asset/Liability/Wish/PaymentRecord Numeric
columns, str on wire). Verifies display correctness post-migration across
financial pages.

### C2.20 Money display — no precision loss across financial pages

```
bsk navigate ${BASE} --session <id> --wait-until networkidle        # dashboard
bsk navigate ${BASE}assets --session <id> --wait-until networkidle   # asset list
bsk navigate ${BASE}liabilities --session <id> --wait-until networkidle  # liability list
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle   # wish list
bsk snapshot --session <id>
```

Assertions (per page):
- [ ] All money values render as formatted strings — no `NaN`, `undefined`, scientific notation, or float artifacts (e.g. `30413901.0` not `30413901.00000001`)
- [ ] Large amounts (e.g. demouser's 59M total assets) display without JS precision loss (bigint-as-str wire format)
- [ ] Computed values (net worth, totals, allocation percentages) are arithmetically correct
- [ ] `[console]` zero errors
