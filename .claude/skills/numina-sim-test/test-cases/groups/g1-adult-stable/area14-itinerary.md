# Area 14 — Itinerary Planning (行程规划 + Cross-day)

Shared conventions in [`_common.md`](../../_common.md).

> **旅行核心功能在 [`area14-travel.md`](./area14-travel.md)** (C14.1–C14.22)。
> 本文件覆盖行程规划子系统: 时间线视图、行程项 CRUD、跨天行程、
> 购买日期、费用同步、Dashboard 负债详情。

## Success Criteria (成功标准)

### Pass Threshold
- **Overall pass rate**: ≥ 95% (17/18 cases must pass, 1 optional SKIP allowed)
- **Critical cases** (MUST pass): C14.23, C14.24, C14.34, C14.35

### Performance Benchmarks
| Case | Metric | Target | Max |
|------|--------|--------|-----|
| C14.23 | Timeline view | Page load | < 2s | < 5s |
| C14.24 | Create itinerary item | Form submit | < 3s | < 8s |
| All cases | Console errors | 0 | 0 |

### Data Quality Checks
- **No NaN/undefined** in any money field (amounts are Numeric(18,2), serialized as str)
- **Snowflake IDs as strings** — no precision loss
- **Currency formatting on cost_amount**: single symbol, no precision loss

---

Auth: adult session as `demouser` / `DemoPass123`. All routes under `${BASE}`
(adult SPA).

### Prerequisites (seed data required before run)

- **C14.23**: ≥1 trip with ≥3 itinerary items spanning ≥2 days (demo seed "三亚年假" has 10 items across 6 days)
- **C14.35**: C14.34 will create a cross-day item during the run (no pre-existing data needed)
- **C14.39**: ≥1 liability (any category) for the dashboard liability detail popup; tenant rental contract for rent section; itinerary items with cost for travel spending section

If no travel data exists, C14.24 (create itinerary item) will establish
required data during the run. Only cases requiring *specific* data shapes
(populated itinerary, liabilities) will SKIP.

Covers itinerary planning from `docs/plans/2026-09-21-002-feat-travel-itinerary-planning-plan.md`:
- **Itinerary planning**: day-by-day vertical card timeline, 4 core item types
  (accommodation/dining/transport/activity) + custom types, optional cost linked
  to expense ledger (auto-sync), delete with cascade/unlink choice
- **Cross-day itinerary items**: `end_date` for multi-day items (e.g. 3-night
  hotel stay), `purchase_date` for expense date control, timeline bucketing
  across days with ContinuationHint ("Day N") on continuation days, duration
  badge on cards (e.g. "10/1-10/3 · 3天")
- **Dashboard liability detail popup**: extended breakdown on overview card
  (category totals + monthly rent + travel spending by purchase_date)

## Quick Reference

| Case | Feature | Route | Depends on |
|------|---------|-------|------------|
| C14.23 | Itinerary timeline view | `/travel/:id` | seed data (trip with items) |
| C14.24 | Create itinerary item (all types) | `/travel/:id` | C14.3 (or seed trip) |
| C14.25 | Edit itinerary item + cost update | `/travel/:id` | C14.24 |
| C14.26 | Delete item — cascade vs unlink | `/travel/:id` | C14.24 |
| C14.27 | Standalone expense on timeline | `/travel/:id` | C14.6, C14.23 |
| C14.28 | Custom itinerary item type CRUD | API `/itinerary-types` | — |
| C14.29 | Empty day + empty trip states | `/travel/:id` | C14.3 |
| C14.30 | Itinerary ↔ expense ledger sync | API `/trips/:id/itinerary` | C14.24 |
| C14.31 | Timeline dark mode + accessibility | `/travel/:id` | C14.23 |
| C14.32 | Itinerary item form UX | `/travel/:id` | C14.24 |
| C14.33 | Trip detail page — itinerary as primary | `/travel/:id` | C14.23 |
| C14.34 | Create cross-day itinerary item | `/travel/:id` | C14.3 (or seed trip) |
| C14.35 | Cross-day timeline: ContinuationHint + duration badge | `/travel/:id` | C14.34 |
| C14.36 | Edit cross-day item (change/remove end_date) | `/travel/:id` | C14.34 |
| C14.37 | Purchase date on itinerary item form | `/travel/:id` | C14.24 |
| C14.38 | Purchase date → expense date sync (API) | API `/trips/:id/itinerary` | C14.34 |
| C14.39 | Dashboard liability detail popup | `/` (DashboardPage) | seed data (liabilities/rent/travel) |
| C14.40 | Cross-day + purchase_date combined scenario | `/travel/:id` + API | C14.34 |

---

## C14.23 — Itinerary timeline view (ItineraryTimeline as primary content)

Reverse-engineered from R15–R18, F3, AE1, AE4 (timeline as main trip detail view).
**Critical case:** MUST pass

```
# Navigate to a trip with pre-existing itinerary items (demo seed: "三亚年假" has 10 items across 6 days)
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.23-itinerary-timeline.png
```

Assertions:
- [ ] ItineraryTimeline renders as the **primary content** on the trip detail page (above the collapsible expense list)
- [ ] Day sections displayed for each day from `departure_date` to `return_date` inclusive
- [ ] Each day section has a date header with weekday (e.g., "10月1日 周三")
- [ ] Itinerary items render as cards (ItineraryItemCard) within their day section
- [ ] Cards show type-specific icon using CSS class theming (`.timeline-card--accommodation`, etc.)
- [ ] Accommodation/dining/transport cards show: icon + name + location + description + cost (right-aligned) + chain-link (🔗) if cost present
- [ ] **Activity cards:** display icon + type name + location/description **if present in data**. Cards with only `type` (no location/description) show minimal content — this is correct conditional rendering (`v-if="item.location"`, `v-if="item.description"`). To test full card layout, create an activity item with location + description fields populated
- [ ] Cards without cost show no price (free activity — R14)
- [ ] Items sorted by `sort_order` within each day; equal order → by `start_time` then `created_at`
- [ ] Standalone expenses render as simpler entries (smaller, muted style, wallet icon), visually distinct from itinerary cards (R18)
- [ ] Reversal entries (冲销) from cascade delete / cost edit render as standalone entries — may cause visual clutter (UX-7)
- [ ] `[console]` zero errors
- [ ] Performance: page load < 2s

---

## C14.24 — Create itinerary item (all core types)

Reverse-engineered from R1–R9, R10, F1, AE1 (create items with cost).
**Critical case:** MUST pass

> **bsk protocol drift workaround:** The type selector uses `van-picker` (NOT
> `van-action-sheet`). Items are in `.van-picker-column__item` with a toolbar
> "取消"/"确认". When bsk extension protocol (1.3) drifts from daemon (1.0),
> `bsk click` on picker column items and form submit buttons may not trigger
> Vue event handlers. This is a **bsk testing limitation, NOT a product bug** —
> real users interact via touch events which work correctly.
> **Workaround:** Use `bsk evaluate` to dispatch `MouseEvent('click', {bubbles:true})`
> on picker items, and `.click()` on form submit buttons. The form already has
> `submitting` ref + `:disabled` guard to prevent real-user double-submission.

```
# On a trip detail page (create a new trip if needed via C14.3)
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Tap the "+" add button on a day section (or the trip-level empty state CTA)
# ItineraryItemForm popup opens (van-popup position="bottom")
bsk screenshot --session <id> --out dogfood-output/c14.24-itinerary-form.png
```

Assertions (form):
- [ ] ItineraryItemForm opens as a bottom popup (`van-popup position="bottom"`)
- [ ] Type selector button shows current type (default: "活动") + dropdown arrow
- [ ] Clicking type button opens `van-picker` with 4 core types: 住宿 / 餐饮 / 交通 / 活动 + "+ 添加自定义类型"
- [ ] Picker has toolbar with "取消" (left) and "确认" (right) buttons
- [ ] Date picker pre-filled with the day section's date (or today if trip-level add)
- [ ] Optional time pickers (start_time, end_time) — not required by default (R7)
- [ ] Location field (optional, R9) and description field (optional, R8) visible
- [ ] Cost section: amount + currency fields (optional, R10, currency defaults to "CNY")

> **Close button icon note:** The form header close button (``) may show raw icon
> code instead of a rendered icon — this is an Iconify registration issue (UX-3).
> The popup can be dismissed via backdrop tap or the picker toolbar "取消".

```
# Fill form: select type "住宿" via picker → confirm, set location, cost ¥500 CNY
# Step 1: click type button to open picker
bsk click @eN_type --session <id>
bsk wait-ms 800ms
# Step 2: select "住宿" via JS (bsk click on picker items may not work)
bsk evaluate --session <id> "(function() {
  const items = document.querySelectorAll('.van-picker-column__item');
  for (let item of items) { if (item.textContent.trim() === '住宿') {
    item.dispatchEvent(new MouseEvent('click', {bubbles:true})); return 'ok'; } }
  return 'not found';
})()"
bsk wait-ms 500ms
# Step 3: click picker toolbar "确认"
bsk click @eN_confirm --session <id>
bsk wait-ms 1s
# Step 4: fill location, description, cost
bsk fill @eN_loc --value "东京新宿格拉斯丽酒店" --session <id>
bsk fill @eN_desc --value "5晚住宿" --session <id>
bsk fill @eN_cost --value "500" --session <id>
# Step 5: submit (use JS if bsk click fails)
bsk evaluate --session <id> "(function() {
  const btns = document.querySelectorAll('[role=dialog] button');
  for (let b of btns) { if (b.textContent.trim() === '确认') { b.click(); return 'ok'; } }
  return 'not found';
})()"
bsk wait-ms 2s
```

Assertions (accommodation — R2, type_metadata):
- [ ] After type switch to "住宿": form shows type-specific fields "入住时间" + "退房时间" (replacing "门票价格")
- [ ] Submit POSTs to `/api/v1/trips/:id/itinerary`, returns 201
- [ ] Response includes `type="accommodation"`, `cost_amount="500.00"` (string — Snowflake convention), `cost_currency="CNY"`
- [ ] `type_metadata` contains check-in time if entered (R2)
- [ ] Success toast "操作成功" shown, popup closes
- [ ] Timeline refreshes: new card appears in the correct day section with accommodation icon (🏨)
- [ ] Card shows: type icon + name + location (📍) + description + cost (right-aligned) + chain-link indicator (🔗)
- [ ] **Duplicate prevention:** verify only ONE card was created (bsk click + JS click may each trigger submit — see UX-6)

```
# Create additional items: "餐饮" (R3 — diners in type_metadata), "交通" (R4 — origin/destination), "活动" (R5 — no cost, free activity)
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.24-itinerary-created.png
```

Assertions (all types created):
- [ ] Dining item: `type_metadata` contains diners count (R3)
- [ ] Transport item: `type_metadata` contains origin and destination (R4)
- [ ] Activity item with no cost: `cost_amount=null`, card shows no price (R14 — free activity valid)
- [ ] Each item with cost auto-created a corresponding expense entry in the ledger (R11) — verify via API: `GET /api/v1/trips/:id/expenses` shows new entries
- [ ] Trip's `actual_spend` updated to reflect new expenses (R11)
- [ ] `[console]` zero errors

---

## C14.25 — Edit itinerary item + cost sync

Reverse-engineered from R12, F1 (editing cost syncs to expense ledger).

> **UX-2 note (bsk artifact, NOT product bug):** The right-swipe "编辑" button
> uses `.van-button--primary` inside `van-swipe-cell`. During bsk testing with
> protocol drift, clicking the swipe button's `@eN` ref may hit the trip header
> edit button (``) instead — both have empty text in the a11y tree.
> **Real users:** swipe actions work correctly via touch events. The parent
> `openEditForm()` handler in `TravelDetailPage.vue` correctly sets
> `editingItem` and opens `ItineraryItemForm` popup.
> **Test workaround:** Tap the card body (`@click="$emit('edit', item)"`)
> instead of the swipe action button to reliably open the edit form.

```
# On the trip detail page, tap the card body (NOT the swipe edit button)
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Tap the card body (description text) to open edit form
# ItineraryItemForm opens pre-filled with title "编辑行程项"
bsk screenshot --session <id> --out dogfood-output/c14.25-itinerary-edit.png
```

Assertions (edit form):
- [ ] ItineraryItemForm opens with title "编辑行程项" (NOT "添加行程项")
- [ ] All fields pre-filled: date, type (current type), location, description, cost
- [ ] Submit button text is "保存" (NOT "确认" — create mode uses "确认")
- [ ] Type-specific fields match current type (e.g. accommodation → 入住时间/退房时间)

```
# Modify the cost amount from ¥500 to ¥650, then submit
bsk fill @eN_cost --value "650" --session <id>
# Use JS click if bsk click doesn't trigger submit (protocol drift)
bsk evaluate --session <id> "(function() {
  const btns = document.querySelectorAll('[role=dialog] button');
  for (let b of btns) { if (b.textContent.trim() === '保存') { b.click(); return 'ok'; } }
  return 'not found';
})()"
bsk wait-ms 2s
```

Assertions (cost sync — R12):
- [ ] Submit PATCHes to `/api/v1/trips/:id/itinerary/:item_id`
- [ ] Response shows updated `cost_amount="650.00"` (string, no precision loss)
- [ ] Linked expense entry updated: old expense reversed (offsetting entry with negative amount), new expense created with ¥650
- [ ] Trip's `actual_spend` updated: delta = +¥150 (650 - 500)
- [ ] Timeline card refreshes with new amount (¥650.00)
- [ ] `[console]` zero errors

Assertions (remove cost — set cost_amount to null):
- [ ] Edit item, clear cost amount field → submit
- [ ] Old expense reversed (offsetting ledger entries)
- [ ] Item's `cost_amount` and `cost_currency` become null
- [ ] Trip's `actual_spend` decreases by the removed amount
- [ ] Card no longer shows the linked expense indicator (🔗 disappears)
- [ ] `[console]` zero errors

---

## C14.26 — Delete itinerary item (cascade vs unlink)

Reverse-engineered from R13, F2, AE3 (delete with linked expense — user choice).

> **Swipe delete note (bsk artifact):** The `van-swipe-cell` right action button
> (`.van-button--danger`) emits `'delete'` event → parent shows cascade/unlink
> confirmation dialog. Under bsk protocol drift, `bsk click` on swipe action
> buttons may not register. Use `bsk evaluate` to dispatch click on the
> `.van-button--danger` element, or test delete via API calls with
> `?mode=cascade` / `?mode=unlink` for reliable verification.
> **Real users:** swipe-to-delete works correctly via touch events.

```
# On the trip detail page, find an item WITH a linked cost
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Method A (UI): swipe + tap delete button via JS (bsk swipe unreliable)
bsk evaluate --session <id> "(function() {
  const cells = document.querySelectorAll('.van-swipe-cell');
  for (let cell of cells) {
    if (cell.textContent.includes('住宿') || cell.textContent.includes('餐饮')) {
      const delBtn = cell.querySelector('.van-button--danger');
      if (delBtn) { delBtn.click(); return 'clicked delete'; }
    }
  }
  return 'no delete button found';
})()"
# Method B (API): direct DELETE call
# curl -s -X DELETE -H "Authorization: Bearer $TOKEN" "${API_BASE}/trips/<id>/itinerary/<item_id>?mode=cascade"
bsk screenshot --session <id> --out dogfood-output/c14.26-itinerary-delete-dialog.png
```

Assertions (delete confirmation dialog — R13):
- [ ] `showConfirmDialog` appears with two choices: "级联删除" (cascade) and "仅取消关联" (unlink)
- [ ] Dialog message explains the difference: cascade removes both item + expense; unlink keeps expense as standalone

```
# Test UNLINK: tap "仅取消关联"
bsk snapshot --session <id>
```

Assertions (unlink — AE3):
- [ ] Itinerary card disappears from timeline
- [ ] The linked expense **remains** as a standalone entry on its date (ExpenseTimelineEntry style — visually distinct, R18)
- [ ] Trip's `actual_spend` is **unchanged** (expense still counts)
- [ ] API verification: `GET /api/v1/trips/:id/expenses` still shows the expense, but its `itinerary_item_id` is now null
- [ ] `[console]` zero errors

```
# Test CASCADE: create another item with cost, then delete it with cascade
# Navigate back, create item, then swipe-delete with "级联删除"
bsk snapshot --session <id>
```

Assertions (cascade):
- [ ] Itinerary card disappears from timeline
- [ ] Linked expense is **also removed** (reversed via offsetting ledger entries)
- [ ] Trip's `actual_spend` decreases by the removed expense amount
- [ ] API verification: `GET /api/v1/trips/:id/expenses` no longer shows the expense (or shows reversal entries)
- [ ] `[console]` zero errors

Assertions (delete item WITHOUT cost):
- [ ] Item with `cost_amount=null` → no confirmation dialog, item deleted directly
- [ ] No ledger interaction (no expense to unlink/cascade)
- [ ] `[console]` zero errors

---

## C14.27 — Standalone expense mixed with itinerary on timeline

Reverse-engineered from R14, R18, AE2 (standalone expense on timeline — visually distinct).

```
# On a trip that has itinerary items, add a standalone expense (not via itinerary)
bsk navigate ${BASE}travel/<tripId>/expense/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Fill a manual expense entry (e.g., ¥50 "纪念品" on a date that already has itinerary items)
# Submit → navigates back to trip detail
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.27-standalone-expense-timeline.png
```

Assertions:
- [ ] The date that has both an itinerary item AND the new standalone expense shows both entries
- [ ] Itinerary item renders as a rich card (ItineraryItemCard with type icon, fields)
- [ ] Standalone expense renders as a simpler entry (ExpenseTimelineEntry — smaller, no icon badge, muted style)
- [ ] The two entry types are visually distinct (R18)
- [ ] Standalone expense shows: date, category icon, amount, description
- [ ] Both entries appear in the correct date section
- [ ] `[console]` zero errors

---

## C14.28 — Custom itinerary item type CRUD

Reverse-engineered from R6, KTD3 (family-scoped custom types, mirrors ExpenseCategory pattern).

```
# API-level check + UI verification
# 1. List custom types
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/itinerary-types" | jq .

# 2. Create a custom type
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${API_BASE}/itinerary-types" \
  -d '{"name":"温泉","icon":"hot-tub","sort_order":1}' | jq .

# 3. UI: verify custom type appears in ItineraryItemForm
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Open ItineraryItemForm → type selector should show "温泉" at the bottom
bsk screenshot --session <id> --out dogfood-output/c14.28-custom-type.png
```

Assertions:
- [ ] GET returns family's custom types (demo seed includes 购物 and 温泉)
- [ ] POST creates a new custom type (family-scoped, 201)
- [ ] Custom type has: id, family_id, name, icon, sort_order
- [ ] UI: custom type appears in ItineraryItemForm type selector below the 4 core types
- [ ] "+ 添加自定义类型" option at the bottom of type selector creates ItineraryItemType inline and auto-selects it
- [ ] Create item with `type="custom"` and `custom_type_id` → item shows the custom type's name and icon
- [ ] Delete custom type that is in use → rejected with error (ITINERARY_TYPE_IN_USE)
- [ ] Delete unused custom type → succeeds
- [ ] `[console]` zero errors

---

## C14.29 — Empty day + empty trip states

Reverse-engineered from R16, AE4 (empty day shows "add" prompt).

```
# Navigate to a trip where at least one day has no itinerary items
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.29-empty-day.png
```

Assertions (empty day — R16, AE4):
- [ ] Empty day sections are still displayed (between days with items)
- [ ] Empty day shows a placeholder with "+" button / "添加行程" prompt
- [ ] Clicking the "+" button opens ItineraryItemForm pre-filled with that day's date

```
# For an empty trip (newly created, zero items)
bsk navigate ${BASE}travel/<new_trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.29-empty-trip.png
```

Assertions (trip-level empty state):
- [ ] Trip-level empty state shown: illustration + "规划你的旅程 — 添加第一个活动" guidance text
- [ ] Day sections still rendered (departure_date through return_date) — each with empty state
- [ ] Once at least one item is created (via C14.24), the trip-level empty state disappears and per-day empty states take over
- [ ] `[console]` zero errors

---

## C14.30 — Itinerary ↔ expense ledger sync (API-level)

Reverse-engineered from R11, R12, KTD1 (expense ledger auto-sync via itinerary_item_id).

```
# Create an item with cost via API
ITEM=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${API_BASE}/trips/<trip_id>/itinerary" \
  -d '{"date":"2026-10-15","type":"dining","cost_amount":"280.00","cost_currency":"CNY","location":"测试餐厅"}')
ITEM_ID=$(echo "$ITEM" | jq -r '.data.id')

# Verify expense entries created
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/trips/<trip_id>/expenses" | jq ".data[] | select(.itinerary_item_id == \"$ITEM_ID\")"
```

Assertions (create — R11):
- [ ] Creating item with cost → debit+credit expense entries created with `itinerary_item_id` set
- [ ] Both entries have `ref_type="trip"`, `ref_id=<trip_id>` (so trip.actual_spend updates)
- [ ] Trip's `actual_spend` increases by the cost amount

```
# Update cost via API
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${API_BASE}/trips/<trip_id>/itinerary/$ITEM_ID" \
  -d '{"cost_amount":"350.00"}' | jq .

# Verify expense entries updated
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/trips/<trip_id>/expenses" | jq .
```

Assertions (update cost — R12):
- [ ] Old expense reversed (offsetting entries or deleted)
- [ ] New expense created with updated amount ¥350
- [ ] Trip's `actual_spend` reflects the delta (+¥70)

```
# DELETE without mode param → 400 (when item has linked expense)
curl -s -o /dev/null -w "%{http_code}" -X DELETE -H "Authorization: Bearer $TOKEN" \
  "${API_BASE}/trips/<trip_id>/itinerary/$ITEM_ID"
```

Assertions (delete guard):
- [ ] DELETE without `mode` query param on item with linked expense → returns 400
- [ ] `?mode=cascade` → expense reversed + item deleted
- [ ] `?mode=unlink` → expense entries remain with `itinerary_item_id` nulled + item deleted
- [ ] `[console]` zero errors

---

## C14.31 — Timeline dark mode + accessibility

Reverse-engineered from the plan's Definition of Done items 7–8 (dark mode + a11y).

```
# On a trip with itinerary items
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.31-timeline-dark.png
```

Assertions (dark mode):
- [ ] Cards use CSS variables (`var(--card-bg)`, `var(--text-primary)`) — no inline color styles
- [ ] Type-specific theming via semantic modifier classes (`.timeline-card--accommodation`, etc.), NOT `:nth-child(N)`
- [ ] Dark mode toggle: all cards and timeline elements remain legible

Assertions (accessibility):
- [ ] Timeline container has `role="list"`
- [ ] Day sections have `aria-label` describing the date
- [ ] Itinerary item cards have `aria-label` describing type + time + location
- [ ] All interactive elements (buttons, swipe actions) have touch targets ≥ 44×44px
- [ ] Form inputs in ItineraryItemForm have associated labels
- [ ] `[console]` zero errors

---

## C14.32 — Itinerary item form UX

Reverse-engineered from U4 (ItineraryItemForm UX details).

```
# Open ItineraryItemForm, test submit states
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Open the add-item form
```

Assertions (form validation):
- [ ] Required fields: date and type — submitting without them shows validation error
- [ ] Optional fields: time, location, description, cost — can be left empty
- [ ] Cost amount must be positive (non-positive → validation error)
- [ ] Custom type name max 50 characters

Assertions (submit states):
- [ ] Submit button shows loading spinner while API call in flight
- [ ] Submit button disabled during loading (prevents double-submit)
- [ ] On success: popup closes, success toast shown, timeline refreshes
- [ ] On API error: error toast shown, form stays open with data preserved
- [ ] `[console]` zero errors

Assertions (type switching):
- [ ] Switching type clears type_metadata fields from previous type
- [ ] In edit mode: confirmation dialog before clearing type_metadata
- [ ] "+ 添加自定义类型" option at bottom of type selector → inline form (name + icon) → creates ItineraryItemType → auto-selects
- [ ] `[console]` zero errors

---

## C14.33 — Trip detail page integration (timeline as primary, expense list secondary)

Reverse-engineered from U5 (TravelDetailPage integration — timeline replaces expense list as primary view).

```
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.33-trip-detail-itinerary.png
```

Assertions (page layout — U5):
- [ ] ItineraryTimeline is the primary content below the trip info card
- [ ] ExpenseListPanel moved to a collapsible "详情" section below the timeline (van-collapse)
- [ ] SplitGroupManager also in the collapsible section
- [ ] Existing trip expenses still visible as standalone entries on the timeline
- [ ] FAB / primary action: "添加行程" (add itinerary item) opens ItineraryItemForm
- [ ] FAB secondary action: "添加费用" (add standalone expense) still works (existing C14.6 flow preserved)
- [ ] Page header, status section, and info card unchanged from C14.4
- [ ] Navigation: tab → trip detail → back → tab works without blank screen (Transition/KeepAlive interaction)
- [ ] `onMounted` / `onActivated` loads itinerary data: `fetchItinerary(tripId)` + `fetchItineraryTypes()` in `Promise.all`
- [ ] `[console]` zero errors

---

## C14.34 — Create cross-day itinerary item (end_date + cross-day toggle)

Reverse-engineered from `feat/travel-crossday-itinerary` branch (cross-day toggle,
end_date field, ContinuationHint).
**Critical case:** MUST pass

```
# On a trip detail page
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Tap the "+" add button on a day section
# ItineraryItemForm popup opens
bsk screenshot --session <id> --out dogfood-output/c14.34-crossday-form-toggle.png
```

Assertions (form — cross-day toggle):
- [ ] ItineraryItemForm shows a "跨天" (Multi-day) toggle cell (`van-switch`)
- [ ] Toggle is OFF by default — no end_date picker visible
- [ ] Toggle ON → "结束日期" (End date) picker field appears below the toggle
- [ ] End date picker opens as `van-popup position="bottom"` with `van-date-picker`
- [ ] End date picker min-date = form's start date (cannot pick before start)
- [ ] Select end date (e.g. start=Oct 1, end=Oct 4) → confirm picker

Assertions (accommodation hint — when cross-day ON + type=accommodation):
- [ ] When type is "住宿" and cross-day toggle is ON, a hint text appears: "入住时间为起始日，退房时间为结束日"
- [ ] Hint uses `--text-tertiary` color, 12px font size

```
# Fill form: type "住宿", location, cost ¥1500 CNY, cross-day Oct 1–Oct 4
bsk screenshot --session <id> --out dogfood-output/c14.34-crossday-form-filled.png
# Submit
bsk evaluate --session <id> "(function() {
  const btns = document.querySelectorAll('[role=dialog] button');
  for (let b of btns) { if (b.textContent.trim() === '确认') { b.click(); return 'ok'; } }
  return 'not found';
})()"
bsk wait-ms 2s
```

Assertions (API response):
- [ ] Submit POSTs to `/api/v1/trips/:id/itinerary`, returns 201
- [ ] Response includes `date="2026-10-01"`, `end_date="2026-10-04"`, `type="accommodation"`
- [ ] `cost_amount="1500.00"` (string — Snowflake convention)
- [ ] Success toast shown, popup closes
- [ ] `[console]` zero errors

Assertions (validation — end_date < date):
- [ ] Attempt to set end_date before start_date via API → 422 validation error with message "end_date must be >= date"
- [ ] end_date == date is accepted (treated as single-day, no error)
- [ ] `[console]` zero errors

---

## C14.35 — Cross-day timeline: ContinuationHint + duration badge

Reverse-engineered from `feat/travel-crossday-itinerary` (ContinuationHint component,
duration badge on ItineraryItemCard, timeline bucketing logic).
**Critical case:** MUST pass

**Prerequisite:** C14.34 created a cross-day item (Oct 1–Oct 4).

```
# Navigate to trip detail — timeline shows the cross-day item
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.35-crossday-timeline.png
```

Assertions (start day — Oct 1):
- [ ] ItineraryItemCard renders on Oct 1 (the start date) with full card content
- [ ] Card shows a **duration badge** next to the type name: "10/1-10/4 · 4天" (format: `{start}-{end} · {days}天`)
- [ ] Duration badge styled: 11px, primary color text, semi-transparent primary background, 4px border-radius
- [ ] Card shows type icon + name + location + cost as usual

Assertions (continuation days — Oct 2, Oct 3, Oct 4):
- [ ] Oct 2 day section shows a **ContinuationHint** (NOT the full card): "第2天"
- [ ] Oct 3 day section shows a ContinuationHint: "第3天"
- [ ] Oct 4 day section shows a ContinuationHint: "第4天" (end_date inclusive — last night still a continuation)
- [ ] ContinuationHint shows type-specific icon (hotel-o for accommodation)
- [ ] ContinuationHint styled: flex row, 12px text, `--text-secondary` color, `--bg-secondary` background, 8px border-radius, 0.7 opacity
- [ ] ContinuationHint has `role="button"` and `aria-label` for accessibility

Assertions (end day — Oct 4, inclusive):
- [ ] Oct 4 day section shows a ContinuationHint: "第4天" (end_date is **inclusive** — the last night of a hotel stay still counts as a continuation day; checkout day shows the hint, not the empty placeholder)
- [ ] If end_date + 1 (Oct 5) has no other items, it shows the empty-day placeholder — the item does NOT extend beyond end_date

Assertions (scroll-to-start behavior):
- [ ] Tapping a ContinuationHint → smooth scrolls to the start-day card (Oct 1)
- [ ] Scroll uses `scrollIntoView({ behavior: 'smooth', block: 'center' })`

Assertions (empty day filtering):
- [ ] Days where the item appears as a continuation (Oct 2, Oct 3, Oct 4) do NOT show the "add" (+) button — the item IS present those days as continuations (end_date inclusive)
- [ ] `[console]` zero errors

---

## C14.36 — Edit cross-day item (change/remove end_date)

Reverse-engineered from `feat/travel-crossday-itinerary` (edit mode hydration of
cross-day toggle + end_date).

```
# On the trip detail, tap the cross-day item card body to open edit form
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Tap the card body (description text area) to open edit form
bsk screenshot --session <id> --out dogfood-output/c14.36-crossday-edit.png
```

Assertions (edit form hydration):
- [ ] ItineraryItemForm opens with title "编辑行程项"
- [ ] Cross-day toggle is ON (hydrated from existing end_date)
- [ ] End date field shows the current end_date value (e.g. "2026-10-04")
- [ ] All other fields pre-filled: date, type, location, cost

```
# Change end_date from Oct 4 to Oct 3 via the picker
# Then submit
bsk evaluate --session <id> "(function() {
  const btns = document.querySelectorAll('[role=dialog] button');
  for (let b of btns) { if (b.textContent.trim() === '保存') { b.click(); return 'ok'; } }
  return 'not found';
})()"
bsk wait-ms 2s
```

Assertions (end_date changed):
- [ ] Submit PATCHes to `/api/v1/trips/:id/itinerary/:item_id`
- [ ] Response shows `end_date="2026-10-03"` (updated)
- [ ] Timeline refreshes: ContinuationHint now shows "第2天" (Oct 2) and "第3天" (Oct 3, end_date inclusive), Oct 4 no longer has continuation
- [ ] Duration badge updated: "10/1-10/3 · 3天"
- [ ] `[console]` zero errors

Assertions (remove cross-day — toggle OFF):
- [ ] Open edit form again, toggle cross-day OFF
- [ ] End date field disappears
- [ ] Submit → response shows `end_date=null`
- [ ] Timeline: item appears only on Oct 1, no continuation hints on other days
- [ ] Duration badge disappears from card
- [ ] `[console]` zero errors

---

## C14.37 — Purchase date on itinerary item form

Reverse-engineered from `feat/travel-crossday-itinerary` (purchase_date field,
purchase date picker, accommodation date hint).

```
# Open create form on a trip detail
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Fill cost amount (e.g. ¥500) — purchase date field appears conditionally
bsk screenshot --session <id> --out dogfood-output/c14.37-purchase-date-form.png
```

Assertions (purchase date field — conditional visibility):
- [ ] When cost_amount is empty/zero → no purchase date field visible
- [ ] When cost_amount > 0 → "购买日期" (Purchase date) field appears below the cost section
- [ ] Purchase date field is readonly with `is-link` → clicking opens `van-date-picker` popup
- [ ] Purchase date defaults to the item's start date (form.date)
- [ ] Purchase date picker min-date = trip start, max-date = trip end (or 2030-12-31)

```
# Set purchase date to a date before the trip (e.g. Sep 20 for a Oct trip)
# Submit the form
bsk evaluate --session <id> "(function() {
  const btns = document.querySelectorAll('[role=dialog] button');
  for (let b of btns) { if (b.textContent.trim() === '确认') { b.click(); return 'ok'; } }
  return 'not found';
})()"
bsk wait-ms 2s
```

Assertions (API response):
- [ ] Response includes `purchase_date="2026-09-20"` (the selected date)
- [ ] If purchase_date not explicitly set → `purchase_date` defaults to `date` (start date) in the submission payload
- [ ] If cost_amount is null → `purchase_date` is null in the submission
- [ ] `[console]` zero errors

Assertions (edit mode hydration):
- [ ] Edit an item with purchase_date set → purchase date field shows the stored value
- [ ] Edit an item without purchase_date → defaults to item's start date
- [ ] `[console]` zero errors

---

## C14.38 — Purchase date → expense date sync (API-level)

Reverse-engineered from `feat/travel-crossday-itinerary` (expense_date uses
`purchase_date || date` fallback in `_create_linked_expense`).

```
# Create item with cost + purchase_date via API
ITEM=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${API_BASE}/trips/<trip_id>/itinerary" \
  -d '{"date":"2026-10-10","type":"dining","cost_amount":"280.00","cost_currency":"CNY","purchase_date":"2026-09-25","location":"测试餐厅"}')
ITEM_ID=$(echo "$ITEM" | jq -r '.data.id')

# Verify expense entry created on purchase_date
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/trips/<trip_id>/expenses" | jq ".data[] | select(.itinerary_item_id == \"$ITEM_ID\")"
```

Assertions (create with purchase_date):
- [ ] Linked expense entry `expense_date` = `2026-09-25` (the purchase_date, NOT the trip date Oct 10)
- [ ] Debit+credit pair created with `itinerary_item_id` set

```
# Create item WITHOUT purchase_date — should fallback to date
ITEM2=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${API_BASE}/trips/<trip_id>/itinerary" \
  -d '{"date":"2026-10-15","type":"dining","cost_amount":"150.00","cost_currency":"CNY","location":"无购买日期"}')
ITEM2_ID=$(echo "$ITEM2" | jq -r '.data.id')

curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/trips/<trip_id>/expenses" | jq ".data[] | select(.itinerary_item_id == \"$ITEM2_ID\")"
```

Assertions (create without purchase_date — backward compat):
- [ ] Linked expense entry `expense_date` = `2026-10-15` (the item's date — fallback)

```
# Update purchase_date — expense should be recreated with new date
curl -s -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${API_BASE}/trips/<trip_id>/itinerary/$ITEM_ID" \
  -d '{"purchase_date":"2026-10-01"}' | jq .

curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/trips/<trip_id>/expenses" | jq ".data[] | select(.itinerary_item_id == \"$ITEM_ID\")"
```

Assertions (update purchase_date — expense recreated):
- [ ] Old expense reversed (offsetting entries)
- [ ] New expense created with `expense_date` = `2026-10-01` (the new purchase_date)
- [ ] Trip's `actual_spend` unchanged (same amount, just different date)
- [ ] `[console]` zero errors

---

## C14.39 — Dashboard liability detail popup

Reverse-engineered from `feat/travel-crossday-itinerary` (GET /dashboard/liability-detail,
OverviewStatCard info button + popup).

```
# Navigate to Dashboard
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Find the "总负债" section — info button (ⓘ icon) next to the label
bsk screenshot --session <id> --out dogfood-output/c14.39-dashboard-liability-info-btn.png
# Click the info button
bsk evaluate --session <id> "(function() {
  const btn = document.querySelector('[data-test=liability-info-btn]');
  if (btn) { btn.click(); return 'clicked'; }
  return 'not found';
})()"
bsk wait-ms 1s
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.39-liability-detail-popup.png
```

Assertions (info button):
- [ ] Info button (ⓘ SVG icon) visible next to "总负债" label
- [ ] Button has `data-test="liability-info-btn"` attribute
- [ ] Button has `aria-label="负债明细"` for accessibility
- [ ] Clicking does NOT navigate to liabilities tab (click prevented with `.prevent.stop`)

Assertions (popup content):
- [ ] `van-popup position="bottom"` opens with title "负债明细"
- [ ] Popup is closeable (X button or backdrop tap)
- [ ] **Section 1 — Category breakdown**: "负债剩余总额" label + total amount (MoneyDisplay)
  - Each category shows: color dot, category name, percentage, amount
  - If no liabilities: category list empty, total shows ¥0
- [ ] **Section 2 — Rent** (conditional): visible only if family has active tenant contracts
  - Shows "每月房租" label + monthly rent amount (CNY-converted if needed)
  - If no tenant contracts: section hidden
- [ ] **Section 3 — Travel** (conditional): visible only if travel expenses > 0
  - Shows "旅游支出" section label
  - "上月旅游" row: travel items with `purchase_date` (or `date` fallback) in last month
  - "本月旅游" row: travel items with `purchase_date` (or `date` fallback) in this month
  - If both are 0: section hidden
- [ ] Loading state: `van-loading` shown while API call in flight
- [ ] `[console]` zero errors

Assertions (API verification):
- [ ] `GET /dashboard/liability-detail` returns: `total_liabilities`, `categories[]`, `rent_monthly_expense`, `travel_last_month`, `travel_this_month`
- [ ] `travel_last_month` and `travel_this_month` use `coalesce(purchase_date, date)` for bucketing
- [ ] Travel expenses exclude cancelled/inactive trips (`Trip.is_active == True`)
- [ ] All amounts are floats (not strings — this is a dashboard metric, not a Snowflake ID)
- [ ] `[console]` zero errors

---

## C14.40 — Cross-day + purchase_date combined scenario

Reverse-engineered from `feat/travel-crossday-itinerary` (interaction between
end_date and purchase_date for a multi-day hotel booking purchased in advance).

```
# Create a cross-day accommodation item with purchase_date before the trip
# via API (most reliable for this combined scenario)
ITEM=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${API_BASE}/trips/<trip_id>/itinerary" \
  -d '{"date":"2026-10-10","end_date":"2026-10-13","type":"accommodation","cost_amount":"2400.00","cost_currency":"CNY","purchase_date":"2026-09-15","location":"测试酒店","description":"3晚住宿"}')
echo "$ITEM" | jq .
```

Assertions (combined scenario — API):
- [ ] Response: `date="2026-10-10"`, `end_date="2026-10-13"`, `purchase_date="2026-09-15"`
- [ ] Linked expense entry `expense_date` = `2026-09-15` (purchase_date, NOT Oct 10)
- [ ] Trip's `actual_spend` increased by ¥2400

```
# Verify timeline display
bsk navigate ${BASE}travel/<trip_id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c14.40-crossday-purchase-combined.png
```

Assertions (combined scenario — UI):
- [ ] Oct 10 day section: full ItineraryItemCard with duration badge "10/10-10/13 · 4天"
- [ ] Oct 11, Oct 12 day sections: ContinuationHint ("第2天", "第3天")
- [ ] Oct 13: NOT shown (item ends on this day but card only on start day)
- [ ] Card shows cost ¥2,400.00 with chain-link indicator (🔗)

```
# Dashboard check — travel expense should appear in September (purchase_date bucket)
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/dashboard/liability-detail" | jq .
```

Assertions (dashboard bucketing):
- [ ] `travel_this_month` or `travel_last_month` includes ¥2,400 in the month matching `purchase_date` (September), NOT October (the trip date)
- [ ] This verifies the `coalesce(purchase_date, date)` logic in `get_liability_detail`
- [ ] `[console]` zero errors

---

