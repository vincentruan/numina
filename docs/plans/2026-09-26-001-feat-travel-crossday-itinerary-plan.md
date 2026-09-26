---
title: Travel Cross-Day Itinerary - Plan
type: feat
date: 2026-09-26
topic: travel-crossday-itinerary
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

# Travel Cross-Day Itinerary - Plan

## Goal Capsule

- **Objective:** Extend the travel itinerary system to support items that span multiple days (e.g., multi-night hotel stays, multi-day car rentals), while preserving the existing single-day behavior as the default.
- **Authority:** Brainstorm Product Contract — 4 Key Decisions from dialogue
- **Stop conditions:** All Requirements satisfied; Acceptance Examples pass; no P0/P1 open questions
- **Execution profile:** Full-stack — ORM model change (add `end_date` column) → Alembic migration → Pydantic schemas → Frontend form + timeline display updates

---

## Product Contract

### Summary

Add optional cross-day support to the existing itinerary system. Any itinerary item can optionally have an `end_date`, making it span multiple days. The timeline shows the full item card on the start date with a duration badge, and collapsed continuation hints on subsequent days. Cost is recorded as a total on the start date. Single-day items (no `end_date`) remain unchanged.

### Problem Frame

The current itinerary model ties each item to a single date. Multi-day scenarios — hotel stays, car rentals, charter transport — require users to create one item per day as a workaround. This is tedious and misrepresents the data: a 3-night hotel stay is one reservation, not three independent entries. The expense ledger also fragments a single payment across multiple dates.

### Key Decisions

**Universal cross-day over type-specific.** Any itinerary item type can have an optional `end_date`. No per-type logic gates whether cross-day is available. Rationale: simpler data model, future-proof for unexpected cross-day scenarios (multi-day events, exhibitions), zero impact on single-day UI. (user-directed) — Governs R1, R2, R4

**Total cost on start date.** A cross-day item with a cost records the total amount as a single expense entry on the start date. No per-day splitting. Rationale: matches how users actually pay (one hotel bill, one rental invoice), consistent with "enter total price" mental model, simpler implementation. (user-directed) — Governs R11, R12, R13

**Start-date full card + continuation hints.** The timeline shows the complete item card on the start date with a duration badge (e.g., "9/25-9/28 · 3晚"). Subsequent days show a collapsed hint (e.g., "← 酒店续住第2天"). Rationale: keeps timeline scannable while conveying the span; avoids noise from repeating full cards. (user-chosen from 3 options) — Governs R7, R8, R9

**Backward-compatible optional field.** `end_date` is nullable. Items without `end_date` behave exactly as today. No migration of existing data needed; no behavioral change to single-day items. (structural decision) — Governs R1, R10

Product Contract preservation: unchanged from brainstorm. All R-IDs, A-IDs, F-IDs, AE-IDs preserved verbatim. Added `Governs R…` links to Key Decisions.

### Requirements

**Data Model**

R1. `ItineraryItem` gains an optional `end_date: Date` field (nullable, default null). When null, the item is single-day (existing behavior). When set, `end_date >= date` (start date).

R2. Validation: `end_date` must be >= `date`. If equal, treat as single-day (same as null).

R3. No changes to `type_metadata` semantics. Accommodation's `check_in_time`/`check_out_time` remain time-of-day fields on the start/end dates respectively.

**Form Interaction**

R4. The itinerary item form gains an optional "跨天" toggle (default off). When off, only a single date picker is shown (existing behavior). When on, a second date picker appears for the end date.

R5. The end date picker enforces `end_date >= start_date`.

R6. For accommodation type with cross-day enabled, the form shows check-in time (for start date) and check-out time (for end date) — existing fields, relabeled for clarity.

R16. When the item has a cost, the form shows a "购买日期" (purchase date) field. It defaults to the item's start date and is editable via a date picker. The selected value is sent as `purchase_date` in the API payload.

**Timeline Display**

R7. A cross-day item displays its full card on the start date, with a duration badge showing the date range and count (e.g., "🏨 9/25-9/28 · 3晚" or "🚗 9/25-9/28 · 4天").

R8. On each subsequent day within the range (start_date < day <= end_date), the timeline shows a collapsed continuation hint referencing the item (e.g., "← 续住第2天" with the item type icon).

R9. The continuation hint is tappable — tapping it scrolls to or expands the full card on the start date.

R10. Single-day items (no `end_date` or `end_date == date`) display identically to today. No visual change.

**Expense Integration**

R11. A cross-day item with a cost creates one expense entry on the start date (`date`), for the full `cost_amount`. No per-day splitting.

R12. Editing the cost on a cross-day item updates the single linked expense entry, same as single-day behavior.

R13. Deleting a cross-day item with a linked expense follows the existing cascade/unlink confirmation dialog, unchanged from single-day behavior.

R15. Itinerary item cost supports an optional `purchase_date` field — the actual date payment was made. Defaults to the item's start `date` when not explicitly set. The linked expense entry uses `purchase_date` as its `expense_date`. This allows spending statistics to reflect real payment timing (e.g., booked hotel on 9/20 for a 9/25 stay), not trip activity timing. User can select/change it in the form.

**Trip Boundary**

R14. If `end_date` extends beyond the trip's `return_date`, the timeline shows the item through `return_date`. The full `end_date` is preserved in the data but the timeline clips to the trip range.

### Actors

A1. **Family member** — creates, edits, and deletes cross-day itinerary items. The cross-day toggle is available on the existing item form; no new page or flow.

### Key Flows

F1. Create a cross-day accommodation item
- **Trigger:** User opens the add-item form on a trip timeline, toggles "跨天" on
- **Steps:** User selects start date (9/25) → toggles "跨天" → end date picker appears → selects end date (9/28) → fills check-in time (14:00) and check-out time (12:00) → enters total cost (¥1500) → purchase date defaults to 9/25 → submits
- **Result:** One ItineraryItem with `date=9/25, end_date=9/28, cost_amount=1500, purchase_date=9/25`. Timeline shows full card on 9/25 with "3晚" badge, continuation hints on 9/26 and 9/27. One expense entry of ¥1500 with expense_date=9/25 (from purchase_date).
- **Covers R1, R4-R8, R11, R15, R16.**

F2. View cross-day item across multiple days
- **Trigger:** User scrolls the timeline past the start date of a cross-day item
- **Steps:** On 9/26, user sees "← 🏨 续住第2天" hint → taps it → timeline scrolls to 9/25 full card
- **Covers R8, R9.**

F3. Edit cross-day item to single-day
- **Trigger:** User edits a cross-day hotel item, toggles "跨天" off
- **Steps:** `end_date` is cleared. The continuation hints disappear from the timeline. The expense entry is unchanged (still on start date, same amount).
- **Covers R2, R10.**

### Acceptance Examples

AE1. Multi-night hotel stay
- **Covers R1, R4-R8, R11.**
- **Given:** A trip from 2026-09-25 to 2026-09-28
- **When:** User creates accommodation with start=9/25, end=9/28, cost=¥1500, check-in=14:00, check-out=12:00
- **Then:** Timeline shows full card on 9/25 with "🏨 9/25-9/28 · 3晚" badge. 9/26 shows "← 🏨 续住第2天". 9/27 shows "← 🏨 续住第3天". 9/28 has no continuation (checkout day). Expense ledger has one ¥1500 entry on 9/25.

AE2. Multi-day car rental
- **Covers R1, R7.**
- **Given:** A trip from 2026-10-01 to 2026-10-05
- **When:** User creates transport (rental) with start=10/01, end=10/04, cost=¥800
- **Then:** Timeline shows full card on 10/01 with "🚗 10/01-10/04 · 4天" badge. 10/02, 10/03 show continuation hints. 10/04 is the last rental day (no checkout concept for transport, just the last day of the range).

AE3. Single-day item unchanged
- **Covers R2, R10.**
- **Given:** A dining item on 10/02 with no end_date
- **Then:** Displays exactly as before. No duration badge, no continuation hints.

AE4. Trip boundary clip
- **Covers R14.**
- **Given:** A trip with `return_date=10/05`, an accommodation with `end_date=10/07`
- **Then:** Timeline shows the item through 10/05 (the trip end). Continuation hints appear on 10/03, 10/04, 10/05. 10/06 and 10/07 are not shown on the timeline (outside trip range). The data preserves end_date=10/07.

### Scope Boundaries

**In scope (this plan):**
- Data model: add `end_date` and `purchase_date` to ItineraryItem
- Form: cross-day toggle + end date picker + purchase date picker
- Timeline: full card on start date + continuation hints
- Expense: single entry on start date, expense_date driven by purchase_date (no splitting)

**Deferred for later:**
- Per-day cost breakdown display (show daily average on continuation hints)
- Drag-and-drop of cross-day items across dates
- Cross-day item editing from a continuation hint (must go to start date)
- Multi-day items that span across different trips (out of scope by definition)
- Recurring/templated multi-day items

### How This Work Fits Together

This plan extends the itinerary planning feature established in `docs/plans/2026-09-21-002-feat-travel-itinerary-planning-plan.md`. It is a minimal, backward-compatible addition — no existing behavior changes, no new entity types, no new API endpoints.

- **Depends on:** Existing ItineraryItem model, ItineraryTimeline component, ItineraryItemForm component, expense linking service
- **Modifies:** ItineraryItem ORM model (add column), Pydantic schemas (add field), frontend form (add toggle), frontend timeline (add continuation rendering)
- **Does not modify:** Trip model, expense ledger logic, split groups, existing single-day item behavior

### Outstanding Questions

**Resolved during planning:**
- Continuation hint i18n: use generic "第N天" phrasing with item type icon, not accommodation-specific "续住". Covers all item types uniformly. (KTD4)
- Duration badge unit: use "天" (days) for all types including accommodation. Simpler than per-type logic; the difference between "晚" and "天" is marginal. (KTD4)
- Form auto-suggest for accommodation: skip. The user explicitly picks dates; auto-suggesting adds complexity without clear value. (deferred)
- `end_date > return_date` form warning: silently allow in form, clip on timeline per R14. Adding form warnings for a valid data scenario creates unnecessary friction. (KTD5)

---

## Planning Contract

### Key Technical Decisions

KTD1. **Follow RentalContract's date range pattern.** The `RentalContract` model (`server/packages/db/models/rental_contract.py:41-42`) already uses `start_date: Date` + `end_date: Date | None`. ItineraryItem's `date` field is the start date; the new `end_date` mirrors RentalContract's nullable end pattern. Schema validation follows the same `@field_validator` approach. (Governs R1, R2)

KTD2. **Idempotent Alembic migration with fresh-DB guard.** The migration uses `sa.inspect(op.get_bind())` to check column existence before `add_column`, matching the pattern in `c7d2e1f8a3b5_add_itinerary_planning_tables.py`. Fresh installs create the column via `Base.metadata.create_all()` from the ORM model; the guard skips `add_column` when it already exists. No `server_default` needed (nullable column). (Governs R1)

KTD3. **Expense date uses `purchase_date` with fallback to start date.** `_create_linked_expense` in `server/apps/backend/app/services/itinerary.py:189-207` currently sets `expense_date=item.date`. Change to `expense_date=item.purchase_date or item.date`. The `purchase_date` column on `ItineraryItem` is nullable; when null (items without explicit purchase date), behavior is unchanged. When set, the expense reflects the real payment date. Update path (`update_item`) already reverses and recreates expenses on cost change, so `purchase_date` changes flow through automatically. (Governs R11, R12, R13, R15)

KTD4. **Generic continuation hint text with type icon.** Use i18n key pattern `travel.itinerary.continuationDay` = "第{day}天" with the item type icon prefix. The same template works for all types. Duration badge format: "{icon} {date_range} · {n}天" for all types (not "晚" for accommodation). (Governs R7, R8)

KTD5. **Timeline clips to trip range; form allows any end_date >= date.** The timeline's day-generation loop already walks `departure_date` to `return_date`, so continuation hints naturally stop at the trip boundary (R14). The form does not validate `end_date <= return_date` — users may have data that extends beyond the planned return. (Governs R14)

KTD6. **Timeline bucketing: spans-day test with start-day flag.** Replace exact `i.date === dateStr` match with a spans-day check: item appears in a day bucket if `i.date <= dateStr <= effective_end_date`. A computed `is_start_day` flag distinguishes full-card rendering (start day) from continuation-hint rendering (subsequent days). Items with no `end_date` or `end_date == date` behave identically to today. (Governs R7, R8, R10)

### Patterns to Follow

- **ORM model field addition:** `server/packages/db/models/rental_contract.py:41-42` — nullable `end_date: Date | None`
- **Alembic migration:** `server/apps/backend/alembic/versions/c7d2e1f8a3b5_add_itinerary_planning_tables.py` — idempotent column-existence guard
- **Pydantic validation:** `server/apps/backend/app/schemas/rental_contract.py` — `@field_validator` for date range
- **Form date picker:** `frontend/apps/main/src/components/travel/ItineraryItemForm.vue:29-37` — `van-date-picker` in `van-popup position="bottom"`. Use `:model-value` (Vant 4 requirement).
- **Timeline day bucketing:** `frontend/apps/main/src/components/travel/ItineraryTimeline.vue:114-146` — `days` computed with `DayBucket[]`
- **Item card rendering:** `frontend/apps/main/src/components/travel/ItineraryItemCard.vue` — `ICON_MAP`, `typeMetaSummary` computed
- **Frontend types:** `frontend/apps/main/src/types/travel.ts:146-191` — `date: string` pattern, add `end_date: string | null`
- **i18n:** `frontend/apps/main/src/i18n/locales/zh-CN.ts` and `en-US.ts` — add keys under `travel.itinerary.*`

---

## Implementation Units

### U1. Backend Model and Migration

**Goal:** Add `end_date` and `purchase_date` columns to the `itinerary_items` table and ORM model.

**Requirements:** R1, R2, R3, R15

**Dependencies:** none

**Files:**
- `server/packages/db/models/itinerary_item.py` — add `end_date` and `purchase_date` mapped columns
- `server/apps/backend/alembic/versions/<new>_add_end_date_purchase_date_to_itinerary_items.py` — idempotent migration
- `server/tests/backend/test_models_itinerary.py` — model tests for new fields

**Approach:**
1. Add two nullable columns to the ORM model:
   - `end_date: Mapped[date | None] = mapped_column(Date, nullable=True)` after `date`
   - `purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)` after `cost_currency`
2. Create a single Alembic migration with fresh-DB guard for both columns. Downgrade: `drop_column` for each
3. Add model tests for both fields

**Patterns to follow:** `server/packages/db/models/rental_contract.py:41-42` for nullable date field; `c7d2e1f8a3b5` for migration guard pattern.

**Test scenarios:**
- Create ItineraryItem with `end_date` set, verify it persists and reads back correctly
- Create ItineraryItem without `end_date`, verify it's null (backward compatibility)
- Create ItineraryItem with `purchase_date` set, verify it persists
- Create ItineraryItem without `purchase_date`, verify it's null
- Create item with `end_date == date`, verify stored correctly

**Verification:** `cd server && uv run pytest tests/backend/test_models_itinerary.py -v` passes

---

### U2. Backend Schemas, Service, and Validation

**Goal:** Add `end_date` and `purchase_date` to Pydantic schemas with cross-field validation. Update service to use `purchase_date` for expense date.

**Requirements:** R1, R2, R11, R12, R13, R15

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/schemas/itinerary_item.py` — add `end_date`, `purchase_date` to Create/Update/Response
- `server/apps/backend/app/services/itinerary.py` — change `_create_linked_expense` to use `purchase_date or date`
- `server/tests/backend/test_itinerary_service.py` — service tests for cross-day items and purchase_date

**Approach:**
1. Add to schemas:
   - `end_date: _date_type | None = None` on Create/Update/Response
   - `purchase_date: _date_type | None = None` on Create/Update/Response
2. Add `@field_validator` on Create: `end_date >= date` when both set
3. Update `_create_linked_expense` (line ~198): change `expense_date=item.date` to `expense_date=item.purchase_date or item.date`
4. `update_item` already reverses+recreates expenses on cost change — also handle `purchase_date` change: if `purchase_date` changes, reverse old expense entries and recreate with new date

**Test scenarios:**
- Create cross-day item via API with valid `end_date > date`, verify response includes `end_date`
- Create item with `end_date < date`, verify 422 validation error
- Create cross-day item with cost and `purchase_date` set, verify expense entry created on purchase_date (Covers R15)
- Create cross-day item with cost, no `purchase_date`, verify expense entry created on start date (backward compatible)
- Update item's `purchase_date`, verify expense entries recreated with new date
- Delete cross-day item with cascade/unlink modes, verify expense handling unchanged (Covers R13)

**Verification:** `cd server && uv run pytest tests/backend/test_itinerary_service.py tests/backend/test_models_itinerary.py -v` passes

---

### U3. Frontend Types, API, and i18n

**Goal:** Extend TypeScript types, i18n keys, and verify API layer compatibility.

**Requirements:** R1, R4, R7, R8, R15, R16

**Dependencies:** U2

**Files:**
- `frontend/apps/main/src/types/travel.ts` — add `end_date`, `purchase_date` to interfaces
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add cross-day and purchase date i18n keys
- `frontend/apps/main/src/i18n/locales/en-US.ts` — add cross-day and purchase date i18n keys

**Approach:**
1. Add to TypeScript interfaces:
   - `ItineraryItem`: `end_date: string | null`, `purchase_date: string | null`
   - `ItineraryItemCreate`: `end_date?: string | null`, `purchase_date?: string | null`
   - `ItineraryItemUpdate`: `end_date?: string | null`, `purchase_date?: string | null`
2. Add i18n keys under `travel.itinerary`:
   - `crossDay`: "跨天" / "Multi-day"
   - `endDate`: "结束日期" / "End date"
   - `purchaseDate`: "购买日期" / "Purchase date"
   - `continuationDay`: "第{day}天" / "Day {day}"
3. No API layer changes needed — existing calls pass the full data object

**Test scenarios:**
- Verify `vue-tsc --noEmit` passes with the new type definitions

**Verification:** `cd frontend && pnpm -r typecheck` passes

---

### U4. Frontend Form — Cross-Day Toggle and Purchase Date

**Goal:** Add the "跨天" toggle, end date picker, and purchase date picker to the itinerary item form.

**Requirements:** R4, R5, R6, R16

**Dependencies:** U3

**Files:**
- `frontend/apps/main/src/components/travel/ItineraryItemForm.vue` — add toggle + end date picker + purchase date picker

**Approach:**
1. Add to form `ref` state: `end_date: string | null`, `purchase_date: string | null`, `showCrossDay: boolean` (default false)
2. Add `van-switch` labeled "跨天" below the date picker. When on, show end date picker
3. Add end date `van-date-picker` in `van-popup position="bottom"`, following existing pattern. `min-date` = start date, `max-date` = trip return_date. Use `:model-value`
4. Add purchase date picker: shown when cost_amount > 0 (only relevant when item has a cost). Defaults to start date. User can change to reflect actual payment date
5. On form init/edit: if item has `purchase_date`, use it; otherwise default `purchase_date` to the start `date`
6. Include `end_date` and `purchase_date` in `handleSubmit` payload. Include in `resetForm` and `watch(editItem)` hydration
7. When toggle is turned off, clear `end_date`. When editing an item with `end_date`, auto-enable the toggle
8. For accommodation type: keep existing `check_in_time` / `check_out_time` fields as-is (R6)

**Patterns to follow:** Existing date picker block in `ItineraryItemForm.vue:29-37, 189-197`. Use `:model-value` (Vant 4 requirement).

**Test scenarios:**
- Toggle "跨天" on → end date picker appears
- Select end date before start date → not possible (min-date constraint)
- Toggle off → end_date cleared
- Cost entered → purchase date picker appears, defaults to start date
- Change purchase date → different date selected
- Edit existing cross-day item → toggle auto-enabled, end_date and purchase_date pre-filled
- Submit with cross-day + purchase_date → both in API payload
- Submit without cross-day, with cost → purchase_date defaults to start date

**Verification:** Manual UI test on dev server; `pnpm -r typecheck` passes

---

### U5. Frontend Timeline — Cross-Day Display

**Goal:** Update the timeline to show full card on start date and continuation hints on subsequent days for cross-day items.

**Requirements:** R7, R8, R9, R10, R14

**Dependencies:** U3

**Files:**
- `frontend/apps/main/src/components/travel/ItineraryTimeline.vue` — update day bucketing logic
- `frontend/apps/main/src/components/travel/ItineraryItemCard.vue` — add duration badge
- `frontend/apps/main/src/components/travel/ContinuationHint.vue` — new component for continuation hints

**Approach:**
1. In `ItineraryTimeline.vue` `days` computed (lines 114-146), change the item bucketing filter from exact `i.date === dateStr` to a spans-day test:
   - An item belongs to a day bucket if `i.date <= dateStr <= effectiveEndDate` where `effectiveEndDate = i.end_date ?? i.date`
   - The timeline loop already walks `departure_date` to `return_date`, so items naturally clip at trip boundary (R14, KTD5)
2. Add a `isStartDay` flag per item per bucket: `true` when `dateStr === i.date`, `false` otherwise
3. In the template, render `ItineraryItemCard` when `isStartDay` (existing rendering, unchanged for single-day items)
4. Render `ContinuationHint` when `!isStartDay` — a simple row with type icon, "第N天" text, tappable to scroll to the start date's card
5. In `ItineraryItemCard.vue`, add a duration badge when `item.end_date && item.end_date !== item.date`: show date range and day count next to the item type icon
6. Create `ContinuationHint.vue` component: small inline element with type icon + "第N天" text + optional scroll-to-start-date behavior (R9). Use `scrollIntoView` or emit event to parent

**Patterns to follow:** Existing `days` computed structure in `ItineraryTimeline.vue:114-146`. `ICON_MAP` from `ItineraryItemCard.vue:74-80` for type icons.

**Test scenarios:**
- Covers AE1. 3-night hotel: full card on 9/25 with "3天" badge, continuation hints on 9/26, 9/27, nothing on 9/28
- Covers AE2. 4-day car rental: full card on 10/01, hints on 10/02, 10/03, 10/04
- Covers AE3. Single-day dining item: no badge, no hints, unchanged rendering
- Covers AE4. Trip boundary clip: item with end_date beyond return_date shows only through return_date
- Tap continuation hint → scrolls to start date card (R9)
- Mixed timeline: cross-day item + single-day items + standalone expenses on same day render correctly

**Verification:** Manual UI test on dev server with test data matching AE1-AE4; `pnpm -r typecheck` passes

---

## Verification Contract

**Backend quality gates:**
```bash
cd server
uv run pytest tests/backend/test_models_itinerary.py tests/backend/test_itinerary_service.py -v
uv run pytest tests/backend/ -k "itinerary or travel" -v
```

**Frontend quality gates:**
```bash
cd frontend
pnpm -r typecheck
pnpm -r lint
```

**Integration verification:**
- Start dev server, create a trip, add a cross-day accommodation item, verify timeline display matches AE1
- Add a cross-day transport item, verify AE2
- Verify single-day items render unchanged (AE3)
- Test form: toggle cross-day on/off, edit existing items, submit with/without end_date
- Verify expense ledger shows single entry on start date for cross-day items with cost

---

## Definition of Done

**Global:**
- All R-IDs (R1-R16) satisfied
- All AEs (AE1-AE4) pass manual verification
- Backend tests pass (model + service)
- Frontend typecheck and lint pass
- No regression in existing single-day itinerary behavior
- i18n keys added for both zh-CN and en-US

**Per-unit:**
- U1: Model test passes, migration applies cleanly on fresh and existing DB (both `end_date` and `purchase_date`)
- U2: Schema validation rejects `end_date < date`, service tests pass for cross-day create/update/delete with expense linking, purchase_date drives expense_date
- U3: TypeScript compiles, i18n keys present
- U4: Form toggle works, date constraints enforced, edit mode hydrates correctly
- U5: Timeline shows full card + continuation hints per AE1-AE4, tap-to-scroll works
