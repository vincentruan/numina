# Area 14 — Travel module (家庭旅行管理)

Shared conventions in [`_common.md`](../../_common.md).

## Success Criteria (成功标准)

### Pass Threshold
- **Overall pass rate**: ≥ 95% (21/22 cases must pass, 2 optional SKIP allowed)
- **Critical cases** (MUST pass): C14.1, C14.2, C14.6, C14.12
- **Optional cases** (can SKIP with reason): C14.11 (receipt scan requires AI + vision pipeline), C14.22 (AI context requires AI enabled)

### Performance Benchmarks
| Case | Metric | Target | Max |
|------|--------|--------|-----|
| C14.1 Travel tab | Page load | < 2s | < 5s |
| C14.2 Trip list | Page load | < 2s | < 5s |
| C14.6 Trip detail | Page load | < 2s | < 5s |
| C14.12 Settlement | Page load | < 2s | < 5s |
| All cases | Console errors | 0 | 0 |

### Data Quality Checks
- **No NaN/undefined** in any money field (amounts are Numeric(18,2), serialized as str)
- **No scientific notation** in amounts
- **Snowflake IDs as strings** — no precision loss in trip/expense/settlement IDs
- **Currency formatting**: single symbol, no double symbols (¥¥)
- **Multi-currency**: amount_cny computed correctly, exchange_rate displayed when non-CNY

---

Auth: adult session as `demouser` / `DemoPass123`. All routes under `${BASE}`
(adult SPA). Travel data is per-entity (family-scoped), safe to interleave
within G1.

### Prerequisites (seed data required before run)

Several cases require pre-existing travel data beyond what the default seed
provides. If these are absent, the affected cases will SKIP (not fail):

- **C14.9**: ≥1 travel wish with `converts_to_asset=False` and `status='pending'`
- **C14.13–C14.14**: ≥1 trip with an active split group + ≥2 shared expenses from different participants
- **C14.16**: ≥1 trip linked to a graduated wish (with `wish_id` set)

If no travel data exists, C14.3 (create trip) and C14.12 (create split group)
will establish the required data during the run — later cases that depend on
it will work. Only cases requiring *specific* data shapes (travel wish,
graduated trip) will SKIP.

Covers the travel module implemented in `feat/family-travel-module` + review
gap fixes from `docs/plans/2026-09-21-001-fix-travel-module-review-gaps-plan.md`:
- Trip lifecycle (planning → active → settled → archived, cancel with revert)
- Expense ledger (debit/credit pairs, multi-currency, receipt scan)
- Split groups (invite codes, shared expenses with **proportional share**, debt simplification)
- Split type selector (均摊/按人头/自定义金额) on shared-expense trips
- Wish-to-trip graduation pipeline (wired on wishes tab)
- Dashboard travel_float metric (with CNY conversion for unsettled settlements)
- Receipt-first expense entry (AI extraction via import-parse)
- MCP tool exposure for AI queries
- `useTravelMoney` composable for currency-aware formatting

## Quick Reference

| Case | Feature | Route | Depends on |
|------|---------|-------|------------|
| C14.1 | Travel tab (FinanceHubPage) | `/finance?tab=travel` | — |
| C14.2 | Trip list (TravelTripPanel) | `/finance?tab=travel` | — |
| C14.3 | Create trip form | `/travel/new` | — |
| C14.4 | Trip detail (status-adaptive) | `/travel/:id` | C14.3 |
| C14.5 | Edit trip form | `/travel/:id/edit` | C14.3 |
| C14.6 | Manual expense entry + split type | `/travel/:tripId/expense/new` | C14.3, C14.12 |
| C14.7 | Multi-currency expense | `/travel/:tripId/expense/new` | C14.3 |
| C14.8 | Expense list panel | `/travel/:id` | C14.6 |
| C14.9 | Wish graduation trigger | `/finance?tab=wishes` | pre-existing wish |
| C14.10 | Graduation confirmation | `/travel/:id` | C14.9 |
| C14.11 | Receipt scan entry | `/travel/:tripId/expense/new` | C14.3, AI enabled |
| C14.12 | Split group creation | `/travel/:id` | C14.3 |
| C14.13 | Shared expense page | `/travel/shared/:code` | C14.12 |
| C14.14 | Settlement page | `/travel/:tripId/settlement` | C14.12, C14.6 |
| C14.15 | Copy transfer info | `/travel/:tripId/settlement` | C14.14 |
| C14.16 | Cancel trip | `/travel/:id` | C14.3 |
| C14.17 | Dashboard travel_float | `/` (DashboardPage) | C14.6 |
| C14.18 | Expense category CRUD | API `/expense-categories` | — |
| C14.19 | Status transition buttons | `/travel/:id` | C14.3 |
| C14.20 | Co-organizer delegation | `/travel/:id` | C14.3 |
| C14.21 | Settlement complete + reverse | `/travel/:tripId/settlement` | C14.14 |
| C14.22 | MCP tools in AI chat | `/ai/chat` | AI enabled |

---

## C14.1 — FinanceHubPage 5th tab (旅游)

**Performance target:** Page load < 2s | **Critical case:** MUST pass

```
bsk navigate ${BASE}finance?tab=travel --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.1-travel-tab.png
```

Assertions:
- [ ] 5th tab "旅游" renders with compass icon (`compass-o`) + `t('travel.tab')` label
- [ ] Tab is selectable via URL `?tab=travel` (direct deep link)
- [ ] Tab bar shows 5 tabs: 资产 / 负债 / 心愿 / 租赁 / 旅游
- [ ] TravelTripPanel renders inside the tab content area
- [ ] TravelListSkeleton shows during loading (brief flash, then content)
- [ ] `[console]` zero errors

---

## C14.2 — Trip list (TravelTripPanel) — empty + populated states

```
# Empty state (if no trips exist)
bsk navigate ${BASE}finance?tab=travel --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions (empty state):
- [ ] Empty state illustration visible with "创建第一个旅行" CTA button
- [ ] Clicking CTA → navigates to `/travel/new`

```
# Populated state (trips exist)
# If empty, create a trip first via C14.3, then return here
bsk navigate ${BASE}finance?tab=travel --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.2-trip-list.png
```

Assertions (populated state):
- [ ] TravelTripCard renders for each trip: name, destination, date range, status badge
- [ ] Budget progress bar (`van-progress-bar`) shows actual_spend / planned_budget
- [ ] Status badges: planning=info, active=success, settled=warning, cancelled=danger
- [ ] Current month travel spend overview visible
- [ ] "+ 新建旅行" quick-action button visible → navigates to `/travel/new`
- [ ] upcomingTrips getter filters planning + active trips only
- [ ] `[console]` zero errors

---

## C14.3 — Create trip form (TravelFormPage)

```
bsk navigate ${BASE}travel/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.3-trip-create.png
```

Assertions:
- [ ] PageHeader shows "新建旅行"
- [ ] Form fields render: name (van-field), destination, departure_date (date picker), return_date (optional), planned_budget, currency (CurrencyButton), timezone (optional)
- [ ] Required field validation: name + departure_date are mandatory
- [ ] Submit empty form → Chinese validation error messages
- [ ] Fill form with valid data → submit POSTs to `/api/v1/trips`, returns 201
- [ ] After success → navigates to trip detail `/travel/:id`
- [ ] `[console]` zero errors

---

## C14.4 — Trip detail page (TravelDetailPage) — status-adaptive layout

**Performance target:** Page load < 2s | **Critical case:** MUST pass

```
# Navigate to a trip in planning status
bsk navigate ${BASE}travel/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.4-trip-detail-planning.png
```

Assertions (planning phase):
- [ ] Trip name + destination + date range displayed
- [ ] Status badge shows "规划中" (planning)
- [ ] Budget breakdown above the fold: planned_budget vs actual_spend
- [ ] Initial funding displayed (if wish graduation)
- [ ] ExpenseListPanel renders (may be empty for new trip)
- [ ] "+ 记录费用" FAB/button visible → bottom sheet with "拍照记账" + "手动录入"
- [ ] SplitGroupManager section visible (invite code, participant list) if split enabled
- [ ] Edit button → navigates to `/travel/:id/edit`
- [ ] Cancel button visible (planning trips can be cancelled)
- [ ] `[console]` zero errors

---

## C14.5 — Edit trip form

```
bsk navigate ${BASE}travel/<id>/edit --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] PageHeader shows "编辑行程"
- [ ] All form fields pre-filled with existing trip data
- [ ] Status field visible (can transition: planning → active)
- [ ] Modify a field (e.g., destination) → save PATCHes to `/api/v1/trips/:id`
- [ ] After save → navigates back to trip detail with updated data
- [ ] `router.back()` returns to trip detail
- [ ] `[console]` zero errors

---

## C14.6 — Expense recording — manual entry + split type selector

**Performance target:** Page load < 2s | **Critical case:** MUST pass

```
bsk navigate ${BASE}travel/<tripId>/expense/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.6-expense-create.png
```

Assertions:
- [ ] PageHeader shows "记录费用"
- [ ] Form fields: amount (van-field numeric), currency (CurrencyButton), category (picker from ExpenseCategory list), expense_date (date picker, defaults to trip's timezone), description
- [ ] Expense is pre-linked to current trip (no trip selector needed)
- [ ] Fill form with CNY amount → submit POSTs to `/api/v1/trips/:id/expenses`, returns 201
- [ ] After success → navigates back to trip detail
- [ ] Trip detail shows updated actual_spend (reflects new expense)
- [ ] ExpenseListPanel shows the new expense entry
- [ ] `[console]` zero errors

### Split type selector (shared-expense trips only — R7 fix)

When the trip has an active split group, the expense form shows a split type
segmented control with three options: "均摊" (equal), "按人头" (per-person),
"自定义金额" (custom amounts). Non-shared trips do NOT show this selector.

```
# Navigate to expense form on a trip WITH a split group
bsk navigate ${BASE}travel/<tripId>/expense/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions (split type selector):
- [ ] Split type segmented control visible (van-radio-group or similar)
- [ ] Three options: "均摊" / "按人头" / "自定义金额"
- [ ] Selecting "自定义金额" expands per-participant amount input fields
- [ ] Submitting with "均摊" → `split_type="equal"` stored on the expense
- [ ] Submitting with "按人头" → `split_type="per_person"` stored
- [ ] Submitting with "自定义金额" → `split_type="custom"` with individual amounts
- [ ] Participant names list visible (select who shares this expense)

### Proportional share (R7a fix)

When an expense is recorded on a trip with a split group, `actual_spend`
reflects only the family's proportional share (1/N of the amount), not 100%.

Assertions (proportional share):
- [ ] Trip with split group of 4 total participants (1 family + 3 external), equal split, ¥4000 expense → `actual_spend` increases by ¥1000 (family's 1/4 share, not ¥4000)
- [ ] Trip without split group → `actual_spend` increases by full `amount_cny` (100%)
- [ ] Delete shared expense → `actual_spend` decreases by proportional share

---

## C14.7 — Multi-currency expense — exchange rate handling

Reverse-engineered from AE2 (multi-currency expense recording).

```
bsk navigate ${BASE}travel/<tripId>/expense/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Select JPY as currency, enter amount 8000
bsk screenshot --session <id> --out dogfood-output/c14.7-expense-multicurrency.png
```

Assertions:
- [ ] Select non-CNY currency (e.g., JPY) → form still accepts input
- [ ] On submit, backend fetches JPY→CNY rate via ExchangeRateService
- [ ] Response includes `amount_cny` (computed) and `exchange_rate` (captured)
- [ ] Trip detail shows the expense with both original amount (¥8,000 JPY) and CNY equivalent
- [ ] Trip's actual_spend increases by the CNY-converted amount
- [ ] If ExchangeRateService returns no rate: "手动汇率" badge shown, user can enter rate manually
- [ ] `[console]` zero errors

---

## C14.8 — Expense list panel (ExpenseListPanel)

```
bsk navigate ${BASE}travel/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Scroll to expense list section
bsk screenshot --session <id> --out dogfood-output/c14.8-expense-list.png
```

Assertions:
- [ ] Expenses grouped by date (date headers)
- [ ] Each expense shows: amount, currency, category, description
- [ ] Amounts formatted via `useTravelMoney` composable — currency-aware (JPY no decimals, CNY 2 decimals)
- [ ] Pull-to-refresh works (van-pull-refresh) with "last synced" timestamp
- [ ] Swipe-to-delete on expense → confirmation dialog → DELETEs expense
- [ ] After delete → trip's actual_spend decreases by **proportional share** (not full amount) for shared expenses, or full amount for non-shared
- [ ] ExpenseListPanel refreshes after delete
- [ ] Empty state when no expenses ("暂无费用记录")
- [ ] `[console]` zero errors

---

## C14.9 — Wish-to-trip graduation — trigger on wishes tab

Reverse-engineered from R19 (graduation discoverability) and AE1 (graduation flow).
**R19 fix:** "转化为行程" button is now wired on the wishes tab (previously missing).

```
# Navigate to wishes tab, find a travel wish (converts_to_asset=False)
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Find the "转化为行程" button on a travel wish
bsk screenshot --session <id> --out dogfood-output/c14.9-graduation-trigger.png
```

Assertions:
- [ ] Travel wishes (converts_to_asset=False, status='pending') show "转化为行程" button
- [ ] Non-travel wishes (converts_to_asset=True) do NOT show the button
- [ ] Already realized wishes do NOT show the button
- [ ] Clicking "转化为行程" → confirmation dialog: "将心愿转化为行程？心愿状态将变为'已实现'。"
- [ ] Cancel dialog → no API call, wish unchanged
- [ ] Confirm → calls `POST /api/v1/trips/graduate` with wish_id, returns 201
- [ ] Success toast: "行程已创建" with deep link to new trip
- [ ] Clicking deep link → navigates to `/travel/:new_trip_id`
- [ ] Wish list refreshes: the graduated wish now shows "已实现" status
- [ ] `[console]` zero errors

---

## C14.10 — Graduation verification — trip created correctly

Reverse-engineered from AE1 (graduation acceptance example).

```
# Navigate to the newly created trip (from deep link or trip list)
bsk navigate ${BASE}travel/<new_trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Trip name = wish name (e.g., "Japan 2027")
- [ ] planned_budget = wish's expected_price (serialized as str, no precision loss)
- [ ] initial_funding = wish's saved_amount at graduation time
- [ ] departure_date = wish's target_date
- [ ] Trip has wish_id set (traceability to original wish)
- [ ] Original wish status is now "已实现" (realized) with fulfilled_at set
- [ ] Wish's WishSavingsLog entries preserved (check via wish detail — savings history intact)
- [ ] `[console]` zero errors

---

## C14.11 — Receipt-first expense entry (拍照记账)

Reverse-engineered from AE5 (receipt-first expense entry). Requires AI enabled + vision pipeline.
**R17 fix:** Receipt endpoint now performs actual AI extraction via import-parse (previously only uploaded file). "拍照记账" button now opens the scan flow (previously showed hardcoded toast).

```
bsk navigate ${BASE}travel/<tripId>/expense/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click "拍照记账" option from the bottom sheet
bsk snapshot --session <id>
```

> **File upload note:** Click on `<van-uploader>` does not open the OS file picker
> in most drivers. Evaluate JS to set `input.files` via DataTransfer, or call the
> backend parse endpoint with `curl` and load the preview page with the returned
> token. See `test-cases/_common.md` "File upload note".

Assertions:
- [ ] "拍照记账" button visible in the expense entry bottom sheet
- [ ] Clicking "拍照记账" → opens camera/file picker (NOT a hardcoded toast)
- [ ] After uploading a receipt image → "识别中…" loading indicator with image preview
- [ ] Backend calls import-parse pipeline with travel receipt prompt → structured extraction returned
- [ ] Extraction result contains: vendor, amount, currency, date, expense_category, confidence
- [ ] Form pre-filled with extracted data (user can edit fields before confirming)
- [ ] Confirm → expense created with receipt_image_url linked
- [ ] Low-confidence extraction → partially pre-filled form with empty fields highlighted for manual completion
- [ ] Invalid file type (e.g., .txt) → 400 error
- [ ] File > 10MB → 400 error
- [ ] Existing asset/holdings parse pipeline unaffected (no regression)
- [ ] `[console]` zero errors

> **SKIP-AI** if AI provider not configured or vision pipeline unavailable.

---

## C14.12 — Split group creation + invite code

Reverse-engineered from R6 (split group) and AE3 (debt simplification setup).

```
# On a trip detail page, find the split group section
bsk navigate ${BASE}travel/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click "创建分摊组" or enable split
bsk screenshot --session <id> --out dogfood-output/c14.12-split-group.png
```

Assertions:
- [ ] SplitGroupManager section visible on trip detail
- [ ] "创建分摊组" button → POSTs to `/api/v1/trips/:id/split`, returns split group with invite_code
- [ ] 6-char invite code displayed (uppercase + digits) with copy button
- [ ] Participant list shows organizer (the creating user)
- [ ] "生成邀请链接" button → copies `/travel/shared/<invite_code>` to clipboard
- [ ] "添加参与者" allows adding more participants by name (max 200 chars)
- [ ] "移除" action on each participant (except organizer)
- [ ] Cannot create duplicate split group for same trip
- [ ] `[console]` zero errors

---

## C14.13 — Shared expense page (magic link, no auth)

Reverse-engineered from AE4 (external participant joins) and AE7 (bookmark revisit).

```
# Get the invite code from the trip detail
INVITE_CODE=$(curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/trips/<id>/split" | jq -r '.data.invite_code')

# Use a fresh browser session (no auth cookies)
# In dev mode: start new bsk session, navigate to child origin or fresh tab
# Clear cookies + localStorage first (see F.5 guest pattern in area8)
bsk navigate ${BASE}travel/shared/${INVITE_CODE} --session <guest_sid> --wait-until networkidle
bsk snapshot --session <guest_sid>
bsk screenshot --session <guest_sid> --out dogfood-output/c14.13-shared-expense.png
```

Assertions:
- [ ] SharedExpensePage renders without authentication
- [ ] Join form: enter name + confirm → POSTs to `/travel/shared/<code>/join`
- [ ] After joining: trip name + dates displayed
- [ ] Shared expense list visible: payer family name, amount, currency, category
- [ ] Participant names visible (external participants + family display names)
- [ ] No family IDs, no asset/liability data, no receipt images exposed
- [ ] Read-only: no edit/create/delete buttons
- [ ] Invite code displayed prominently (for manual re-entry if localStorage lost)
- [ ] localStorage persists group association (revisit page → auto-restored)
- [ ] Invalid invite code → 404 or "邀请码无效" error
- [ ] All names rendered via Vue text interpolation (`{{ name }}`), NOT v-html (XSS prevention)
- [ ] `[console]` zero errors

---

## C14.14 — Settlement page (debt simplification)

Reverse-engineered from AE3 (debt simplification) and AE8 (settlement with copy-transfer-info).

```
# Prerequisites: trip has shared expenses from multiple participants
bsk navigate ${BASE}travel/<tripId>/settlement --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.14-settlement.png
```

Assertions:
- [ ] "简化债务" button → calls POST `/trips/:id/split/settle`, runs greedy max-creditor/max-debtor algorithm
- [ ] Settlement cards render: from_participant → to_participant, amount, currency
- [ ] Number of settlements ≤ N-1 (where N = number of participants)
- [ ] Each settlement has "已结清" toggle button
- [ ] Clicking "已结清" → confirmation dialog: "确认已结清？24小时内可撤销。"
- [ ] After confirming: settlement shows "已结清" status with settled_at timestamp
- [ ] "撤销" button visible within 24h window
- [ ] `[console]` zero errors

---

## C14.15 — Copy transfer info (复制转账信息)

Reverse-engineered from AE8 (settlement with copy-transfer-info).

```
# On the settlement page (C14.14)
bsk snapshot --session <id>
# Click "复制转账信息" button on a settlement card
bsk click @eN --session <id>    # copy button
```

Assertions:
- [ ] "复制转账信息" button visible on each settlement card
- [ ] Clicking copies formatted text to clipboard: "请转账 ¥X 给 Y (微信/支付宝)"
- [ ] Amount in clipboard matches settlement amount
- [ ] Recipient name matches to_participant_name
- [ ] Toast notification: "已复制到剪贴板"
- [ ] `[console]` zero errors

---

## C14.16 — Cancel trip (with wish revert + expense reversal)

Reverse-engineered from R5 (trip cancellation) and test_cancel_trip.

```
# On a trip in planning status
bsk navigate ${BASE}travel/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Click "取消行程" button
bsk screenshot --session <id> --out dogfood-output/c14.16-trip-cancel.png
```

Assertions:
- [ ] Cancel button visible on planning trips (NOT on active/settled/archived)
- [ ] Click → confirmation dialog: "取消行程？已记录的费用将冲销。"
- [ ] Confirm → POSTs to `/trips/:id/cancel`
- [ ] Trip status becomes "cancelled" (soft-deleted, is_active=False)
- [ ] If trip was linked to a wish: wish reverts to "pending" status (savings preserved)
- [ ] If trip had expenses: expenses reversed via offsetting ledger entries
- [ ] If trip had split group: invite code invalidated, shared page shows "行程已取消"
- [ ] Trip disappears from active trip list
- [ ] `[console]` zero errors

---

## C14.17 — Dashboard travel_float metric

Reverse-engineered from AE6 (travel float in dashboard) and R15.
**R15 fix:** Unsettled component now converts settlement amounts to CNY before summing (previously summed raw amounts without conversion — wrong for multi-currency trips).

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.17-dashboard-travel-float.png
```

Assertions:
- [ ] Dashboard shows travel_float metric when travel data exists
- [ ] travel_float = prepaid_component - unsettled_shared_component
- [ ] Prepaid expenses (trips in planning status) → positive contribution
- [ ] Unsettled shared expenses (is_complete=False) → negative contribution
- [ ] **Multi-currency settlements**: unsettled amounts converted to CNY via ExchangeRateService before summing (e.g., ¥5000 JPY unsettled → converted to CNY at current rate)
- [ ] No trips → travel_float = null (metric hidden, not shown as ¥0)
- [ ] All trips settled → travel_float = 0 or null
- [ ] All-CNY settlements → same result as before (no regression)
- [ ] Money value formatted correctly (no NaN, no scientific notation)
- [ ] Verified via API: `GET /dashboard/overview` → `data.travel_float` matches displayed value
- [ ] `[console]` zero errors

---

## C14.18 — Expense category API (system seeds + custom)

```
# API-level check (no browser needed)
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/expense-categories" | jq .
```

Assertions:
- [ ] GET returns list of categories including system defaults: 餐饮, 交通, 住宿, 活动, 购物, 其他
- [ ] System categories have `is_system=True`
- [ ] POST creates a custom category (family-scoped)
- [ ] Custom categories appear in the list alongside system defaults
- [ ] Category has: id, name, icon, sort_order, is_system
- [ ] `[console]` zero errors (curl N/A, but frontend category picker should not error)

---

## C14.19 — Trip status transition buttons

Reverse-engineered from R5 (status FSM) and the state diagram.

```
# On a trip in planning status
bsk navigate ${BASE}travel/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Planning trip: "开始旅行" button → transitions to active (PATCH status=active)
- [ ] Active trip: "结算" button → transitions to settled (only when all splits resolved)
- [ ] Settled trip: "归档" button → transitions to archived
- [ ] Invalid transitions not offered (e.g., archived → active)
- [ ] Status badge updates after transition
- [ ] Page layout adapts to new status (C14.4 status-adaptive)
- [ ] `[console]` zero errors

---

## C14.20 — Co-organizer delegation

Reverse-engineered from KTD11 (co-organizer).

```
# On a trip detail page
bsk navigate ${BASE}travel/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Find co-organizer section in SplitGroupManager
```

Assertions:
- [ ] Co-organizer delegation section visible
- [ ] "添加共同组织者" → selects a family member → POSTs to `/trips/:id/split/co-organizers`
- [ ] Co-organizer appears in the list with delegated permissions
- [ ] Max 3 co-organizers enforced (4th attempt → error)
- [ ] "移除" action on co-organizer → DELETEs from co-organizers
- [ ] Co-organizer can add/modify expenses (verified via API if second user available)
- [ ] `[console]` zero errors

---

## C14.21 — Settlement complete + 24h reverse

Reverse-engineered from R9 (settlement lifecycle).

```
# On the settlement page with at least one settlement
bsk navigate ${BASE}travel/<tripId>/settlement --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Mark a settlement as complete
bsk click @eN --session <id>    # "已结清" button
bsk wait-ms 1s
bsk snapshot --session <id>
```

Assertions:
- [ ] Mark complete → PATCH `/trips/:id/split/settlements/:sid` → settled_at set
- [ ] "撤销" button visible next to completed settlement
- [ ] Click "撤销" → DELETE `/trips/:id/split/settlements/:sid` → creates reverse record
- [ ] After reverse: settlement returns to uncompleted state
- [ ] Settlement shows "已结清" with checkmark after completion
- [ ] Navigate to Dashboard (`${BASE}`) → travel_float updates after settlement completion (unsettled component decreases)
- [ ] `[console]` zero errors

---

## C14.22 — MCP travel tools in AI context

Reverse-engineered from R16 (MCP exposure). Requires AI enabled.

```
# Verify MCP tools are registered (API-level)
# MCP tools are internal to the AI system; verify indirectly via AI context
# Navigate to AI chat and ask about travel data
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Send a message asking about travel: "我最近的旅行花费情况如何？"
```

Assertions:
- [ ] AI can query travel data (trip list, expenses, split balances) via MCP tools
- [ ] Response includes travel spending information when trips exist
- [ ] Response does NOT include external participant names or individual split amounts (R16 privacy)
- [ ] AI context paragraph includes travel summary (active trips, budget, spend)
- [ ] No travel data → AI does not mention travel in context
- [ ] `[console]` zero errors

> **SKIP-AI** if AI provider not configured.

---

## Navigation coverage additions (for Area 4 extension)

The following routes should also be added to Area 4 (navigation coverage) when
Area 4 is next updated:

- **C4.17** Travel tab + trip list renders
- **C4.18** Travel create form (`/travel/new`)
- **C4.19** Travel detail (`/travel/:id`)
- **C4.20** Travel edit (`/travel/:id/edit`)
- **C4.21** Expense create (`/travel/:tripId/expense/new`)
- **C4.22** Settlement page (`/travel/:tripId/settlement`)
- **C4.23** Currency switch impact on travel pages (per-record pages do NOT re-convert, same bug class)

> These are deferred to Area 4 to keep Area 14 focused on functional correctness.
> Area 4 verifies that all pages render + currency-switch behavior is consistent.
