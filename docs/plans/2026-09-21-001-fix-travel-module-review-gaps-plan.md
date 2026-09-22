---
title: "fix: Travel module review gap fixes (P0 bugs + P1 features + standards)"
type: fix
date: 2026-09-21
topic: travel-module-review-fixes
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
origin: docs/plans/2026-09-20-001-feat-family-travel-module-plan.md
---

# fix: Travel Module Review Gap Fixes (P0 + P1 + Standards)

## Summary

Code review of `feat/family-travel-module` vs `main` (16 commits, 69 files, ~7000 lines) found **2 logic bugs**, **4 missing P1 features**, and **3 standards violations**. This plan fixes all of them in one batch. Larger features (offline sync R2, timezone display R3, scheduler auto-transitions R5) are deferred to a follow-up batch.

## Problem Frame

The travel module implementation covers U1–U15 of the origin plan structurally, but several requirements have incorrect or incomplete implementations:

- **R7a**: `actual_spend` adds 100% of shared expense amounts instead of the family's proportional share — financial data is wrong for any trip with split groups.
- **R15**: `travel_float` unsettled component sums `SplitSettlement.amount` without CNY conversion — dashboard metric is wrong for multi-currency trips.
- **R7**: Split type segmented control (均摊/按人头/自定义金额) missing from expense UI.
- **R17**: Receipt endpoint only uploads file, returns `confidence="pending"` — no AI extraction happens.
- **R19**: Graduation trigger ("转化为行程") not wired on wishes tab.
- **R20**: "拍照记账" shows hardcoded toast instead of opening ReceiptScanButton.
- **Standards**: `formatAmount` duplicated in 5 Vue files; `_coerce_money_str`/`_coerce_to_decimal` duplicated in 3 schema files; `routers/shared.py` bypasses service layer.

---

## Implementation Units

### U1. Fix R7a: actual_spend proportional share for shared expenses

- **Goal:** When an expense is recorded for a trip with an active split group, `actual_spend` should reflect only the family's proportional share (1 / num_family_participants), not 100% of the amount.
- **Requirements:** R7a
- **Dependencies:** none
- **Files:**
  - `server/apps/backend/app/services/expense_ledger.py` (modify)
  - `server/tests/backend/test_travel_expenses.py` (modify — add proportional share test)
- **Approach:**
  1. In `create_expense()`, after determining the trip, check if the trip has an active split group
  2. If active split group exists, count total participants (both family members via `family_id IS NOT NULL` and external participants)
  3. Calculate family share: if N total participants and the family is 1 of them, share = `amount_cny / N`
  4. Update `trip.actual_spend` with the proportional share instead of full `amount_cny`
  5. In `delete_expense()`, apply the same proportional logic when reverting
- **Patterns to follow:** `services/split_group.py` — `SplitParticipant` query pattern with `family_id` filter
- **Test scenarios:**
  - Covers AE3. Trip with 4 families, equal split: expense of ¥3000 → `actual_spend` increases by ¥750 (not ¥3000)
  - Trip without split group: expense → `actual_spend` increases by full `amount_cny` (100%)
  - Delete shared expense → `actual_spend` decreases by proportional share
- **Verification:** `cd server && uv run pytest tests/backend/test_travel_expenses.py -v -k "proportional"` passes

### U2. Fix R15: travel_float unsettled CNY conversion

- **Goal:** `travel_float` unsettled component must convert settlement amounts to CNY before summing.
- **Requirements:** R15, KTD5
- **Dependencies:** none
- **Files:**
  - `server/apps/backend/app/services/dashboard.py` (modify)
  - `server/tests/backend/test_travel_dashboard.py` (modify — add multi-currency settlement test)
- **Approach:**
  1. Replace `func.sum(SplitSettlement.amount)` with a query that fetches each unsettled settlement's `amount` and `currency`
  2. For each settlement, convert to CNY via `ExchangeRateService.convert()`
  3. Sum the converted amounts
  4. When all settlements are already CNY, behavior is unchanged
- **Patterns to follow:** `dashboard.py` existing prepaid component (which correctly uses `ExpenseEntry.amount_cny`)
- **Test scenarios:**
  - All CNY settlements → same result as before
  - Mixed JPY/CNY settlements → correct CNY sum
  - No unsettled settlements → `travel_float` = prepaid only
- **Verification:** `cd server && uv run pytest tests/backend/test_travel_dashboard.py -v` passes

### U3. Standards: Extract shared schema money helpers

- **Goal:** Deduplicate `_coerce_money_str` and `_coerce_to_decimal` from 3 schema files into one canonical location.
- **Requirements:** coding standards (import dedup, DRY)
- **Dependencies:** none
- **Files:**
  - `server/apps/backend/app/schemas/base.py` (modify — add shared helpers)
  - `server/apps/backend/app/schemas/trip.py` (modify — import from base, remove local defs)
  - `server/apps/backend/app/schemas/expense_entry.py` (modify — same)
  - `server/apps/backend/app/schemas/split_group.py` (modify — same)
- **Approach:**
  1. Add `_coerce_to_decimal()` and `_coerce_money_str()` to `schemas/base.py`
  2. Replace local definitions in trip.py, expense_entry.py, split_group.py with `from apps.backend.app.schemas.base import _coerce_to_decimal, _coerce_money_str`
  3. Check if `schemas/liability.py` or `schemas/rental_contract.py` also have their own copies and consolidate those too
- **Test scenarios:**
  - Test expectation: none — pure refactor, existing tests cover behavior
- **Verification:** `cd server && uv run pytest tests/backend/test_travel_*.py -v` passes (no regressions)

### U4. Standards: Extract shared formatAmount composable

- **Goal:** Replace 5 duplicated `formatAmount` functions in Vue files with a single composable that respects currency.
- **Requirements:** coding standards (DRY, composables for shared logic)
- **Dependencies:** none
- **Files:**
  - `frontend/apps/main/src/composables/useTravelMoney.ts` (new)
  - `frontend/apps/main/src/pages/TravelDetailPage.vue` (modify)
  - `frontend/apps/main/src/components/travel/TravelTripCard.vue` (modify)
  - `frontend/apps/main/src/pages/SplitSettlementPage.vue` (modify)
  - `frontend/apps/main/src/pages/SharedExpensePage.vue` (modify)
  - `frontend/apps/main/src/pages/ExpenseFormPage.vue` (modify — if it has formatAmount)
- **Approach:**
  1. Create `useTravelMoney()` composable with `formatAmount(amount: string | null, currency?: string): string`
  2. Default currency to "CNY" when not provided; use `Intl.NumberFormat` with the currency code
  3. Replace all 5 inline `formatAmount` definitions with `const { formatAmount } = useTravelMoney()`
  4. Pass `trip.currency` from parent contexts so JPY/USD/etc. display correctly
- **Patterns to follow:** existing composables in `frontend/apps/main/src/composables/`
- **Test scenarios:**
  - CNY amount → `¥1,234.56`
  - JPY amount → `¥1,235` (no decimals for JPY)
  - null amount → empty string
- **Verification:** `cd frontend && pnpm -r typecheck` 0 errors

### U5. Standards: Refactor shared router to use service layer

- **Goal:** Move raw `db.query()` calls from `routers/shared.py` into the `split_group` service.
- **Requirements:** coding standards (routers call services)
- **Dependencies:** none
- **Files:**
  - `server/apps/backend/app/services/split_group.py` (modify — add shared view function)
  - `server/apps/backend/app/routers/shared.py` (modify — delegate to service)
- **Approach:**
  1. Add `get_shared_expense_view(db, invite_code)` to `services/split_group.py` that encapsulates all the queries (SplitGroup lookup, Trip lookup, ExpenseEntry list, User display names)
  2. Replace the 5 `db.query()` calls in the router with a single service call
  3. Return a dict or dataclass the router can serialize directly
- **Patterns to follow:** existing service functions in `split_group.py` (e.g., `get_group_with_participants`)
- **Test scenarios:**
  - Test expectation: none — refactor only, existing shared endpoint tests cover behavior
- **Verification:** `cd server && uv run pytest tests/backend/test_travel_split.py -v` passes

### U6. Fix R7: Split type segmented control UI

- **Goal:** Add split type selection (均摊/按人头/自定义金额) to the expense form when recording a shared expense.
- **Requirements:** R7
- **Dependencies:** none
- **Files:**
  - `frontend/apps/main/src/pages/ExpenseFormPage.vue` (modify — add split type selector)
  - `frontend/apps/main/src/types/travel.ts` (modify — add SplitType enum)
  - `frontend/apps/main/src/stores/travel.ts` (modify — pass split config to API)
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add split type labels)
  - `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — same)
  - `server/apps/backend/app/schemas/expense_entry.py` (modify — add split_type, participant_names fields to ExpenseEntryCreate)
- **Approach:**
  1. Add `split_type` field ("equal" | "per_person" | "custom") and `participant_names` (list of names sharing this expense) to `ExpenseEntryCreate`
  2. Add `van-segmented` or `van-radio-group` with three options in ExpenseFormPage, visible only when trip has a split group
  3. "自定义金额" expands per-participant amount inputs
  4. Store `split_type` + participant names on the expense entry (add fields to DB model + migration if needed, or store as JSON in description — prefer model fields)
- **Test scenarios:**
  - Shared expense with "均摊" → split_type="equal" stored
  - "按人头" → split_type="per_person" stored
  - "自定义金额" → split_type="custom" with individual amounts
  - Non-shared trip → split type selector hidden
- **Verification:** typecheck 0 errors; split type visible on shared-expense trips

### U7. Fix R17: Implement actual receipt AI extraction

- **Goal:** Receipt endpoint should perform AI extraction (via import-parse) and return structured data, not just upload the file.
- **Requirements:** R17, R20
- **Dependencies:** none
- **Files:**
  - `server/apps/backend/app/routers/travel_receipt.py` (modify — add extraction logic)
  - `server/apps/agent/skills/builtin/public/import-parse/SKILL.md` (modify — add travel receipt section)
  - `frontend/apps/main/src/components/travel/ReceiptScanButton.vue` (modify — handle extraction result)
  - `frontend/apps/main/src/pages/TravelDetailPage.vue` (modify — connect ReceiptScanButton, remove hardcoded toast)
- **Approach:**
  1. In `travel_receipt.py`, after saving the image, call the import-parse pipeline with the travel receipt prompt
  2. Use `AgentClient` to dispatch to import-parse with `travel_receipt_prompt.md` context
  3. Return structured extraction result (vendor, amount, currency, date, category, confidence)
  4. If extraction confidence is low, return partial data with `confidence="low"`
  5. Update SKILL.md to document the travel receipt extraction path
  6. Frontend: connect ReceiptScanButton to the extraction endpoint, pre-fill ExpenseFormPage on success
  7. Remove "拍照记账功能开发中" hardcoded toast from TravelDetailPage
- **Patterns to follow:** existing import-parse dispatch in `apps/agent/routers/import_parse.py`
- **Test scenarios:**
  - Valid receipt image → structured extraction returned
  - Invalid file type → 400
  - Low-confidence extraction → partial data with `confidence="low"`
  - "拍照记账" action opens camera/file picker, not toast
- **Verification:** endpoint returns structured JSON; frontend connects scan → prefill flow

### U8. Fix R19: Add graduation trigger to wishes tab

- **Goal:** Travel wishes (converts_to_asset=False) show a "转化为行程" button that calls the graduation API.
- **Requirements:** R19, R12
- **Dependencies:** none
- **Files:**
  - `frontend/apps/main/src/pages/FinanceHubPage.vue` (modify — or wish list component)
  - `frontend/apps/main/src/components/travel/TravelTripPanel.vue` (modify — or wish list component)
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify — add graduation strings)
  - `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — same)
- **Approach:**
  1. Find the wish list component that renders wishes on the wishes tab
  2. For wishes where `converts_to_asset=False` and `status='pending'`, show a "转化为行程" button
  3. On tap: show confirmation dialog ("将心愿转化为行程？心愿状态将变为'已实现'。")
  4. On confirm: call `graduateWish(wishId)` API
  5. On success: toast "行程已创建" with deep link to the new trip
- **Patterns to follow:** existing wish action buttons, `showConfirmDialog` pattern from TravelDetailPage
- **Test scenarios:**
  - Travel wish (converts_to_asset=False, pending) → "转化为行程" button visible
  - Non-travel wish (converts_to_asset=True) → button hidden
  - Already realized wish → button hidden
  - Tap → confirm dialog → API call → toast + navigate to trip
- **Verification:** graduation flow works end-to-end from wishes tab

---

## Verification Contract

| Gate | Command | Scope |
|------|---------|-------|
| Backend travel tests | `cd server && uv run pytest tests/backend/test_travel_*.py -v` | U1, U2, U3, U5 |
| Backend lint (touched) | `cd server && uv run ruff check apps/backend/app/services/expense_ledger.py apps/backend/app/services/dashboard.py apps/backend/app/schemas/ apps/backend/app/routers/shared.py` | U1-U3, U5 |
| Frontend typecheck | `cd frontend && pnpm -r typecheck` | U4, U6-U8 |
| Frontend tests | `cd frontend && pnpm -r test:run` | U4, U6-U8 |

---

## Definition of Done

- R7a: shared expense `actual_spend` reflects family's proportional share (AE3 scenario passes)
- R15: `travel_float` unsettled component correctly converted to CNY
- R7: split type segmented control visible and functional on shared-expense trips
- R17: receipt endpoint returns structured extraction data; "拍照记账" opens scan flow
- R19: "转化为行程" button on wishes tab triggers graduation
- Standards: `formatAmount` in 1 composable, schema helpers in 1 file, shared router delegates to service
- All existing travel tests still pass (no regressions)
- `pnpm -r typecheck` 0 errors
