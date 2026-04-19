---
title: "fix: Asset form category picker — popup + icon display + type linkage"
type: fix
status: completed
date: 2026-04-08
---

# fix: Asset form category picker — popup + icon display + type linkage

## Overview

The asset form's category selector currently renders as an always-visible inline grid (`CategoryGrid`). Two issues need fixing:

1. **Interaction**: The category field should behave like other picker fields in the form — show a readonly `van-field` that opens a popup on tap, rather than an always-expanded grid.
2. **Icon display**: Category icons (SVG sprite `icon-*` IDs) are not rendered in the current picker UI. The popup must show each category with its icon alongside its name.
3. **Type linkage**: The categories shown in the popup must be filtered to match the currently selected asset type (`physical` or `financial`), and must re-filter when the type toggle changes.

## Problem Frame

The form passes `assetType` into `CategoryGrid`, which does split categories into physical and financial groups — but renders both groups unconditionally regardless of the current type. The real issues are layout/interaction (the grid is always expanded, taking up significant vertical space) and icon rendering (SVG icons are not shown in the current picker context). Users expect a tap-to-open picker consistent with the date and status fields above it.

## Requirements Trace

- R1. Category field shows as a tappable `van-field` row (readonly, is-link) displaying the selected category name (name only; icon shown in popup) or a placeholder.
- R2. Tapping opens a bottom popup listing only categories matching the current `asset_type`.
- R3. When `asset_type` changes, the selected `category_id` is cleared if it no longer belongs to the new type.
- R4. Each category option in the popup shows its icon (SVG sprite for system categories, emoji fallback for custom) and name.
- R5. Selecting a category closes the popup and updates the field display.

## Scope Boundaries

- No changes to backend, category data model, or API.
- `CategoryGrid.vue` is only used in `AssetForm.vue` (confirmed by grep). After the swap, the component file may be deleted or left as-is (unused). The import in `AssetForm.vue` must be removed.
- No redesign of other form fields.

## Context & Research

### Relevant Code and Patterns

- `frontend/src/components/asset/CategoryGrid.vue` — current inline grid; renders SVG icons via `<use :href="`#${getIconId(cat.icon)}`">` and falls back to `icon-other` for non-`icon-` prefixed icons (emoji custom categories).
- `frontend/src/components/asset/AssetForm.vue:46-51` — current usage: `<van-cell title="分类" />` + `<CategoryGrid v-model="form.category_id" :categories="categories" :asset-type="form.asset_type" />`.
- `frontend/src/components/asset/AssetForm.vue:88-103` — date picker pattern to follow: `van-field` (is-link, readonly) + `van-popup` (position="bottom", round) + `van-date-picker`.
- `frontend/src/components/asset/AssetForm.vue:106-122` — status picker pattern: same structure with `van-picker`.
- `AssetForm.vue:264-279` — `onTypeChange()` already clears type-specific fields; category clear should be added here.
- `frontend/src/types/index.ts:25-34` — `Category` interface: `id`, `name`, `icon` (string, either `icon-*` or emoji), `asset_type: 'physical' | 'financial'`.

### Institutional Learnings

- `docs/solutions/` — SVG icon system documented in `2026-04-05-003-feat-svg-icon-system-plan.md`; `getIconId()` pattern is the established way to resolve icon strings.

## Key Technical Decisions

- **Replace `CategoryGrid` with a popup picker in `AssetForm.vue`**: The `CategoryGrid` component itself can remain unchanged (it may be used elsewhere). The change is in `AssetForm.vue` — swap the cell+grid block for a field+popup block.
- **Inline the popup in `AssetForm.vue` rather than extracting a new component**: The pattern is already established by date/status pickers in the same file. A new component would be premature abstraction for a single use.
- **Use a plain `div` grid inside `van-popup` (not `van-picker`)**: Vant 4's `van-picker` does not expose an `option` slot for individual item customization, making SVG icon rendering inside it impractical. A plain div grid mirrors the existing `CategoryGrid` visual style and allows direct SVG rendering. `van-picker` is not used for this popup.
- **Filter categories by `assetType` reactively**: Use a `filteredCategories` computed that filters `props.categories` by `form.value.asset_type`. The popup displays a flat grid of only the filtered categories (matching current asset type), without group headers — unlike `CategoryGrid` which shows both groups.
- **Display value in field**: Compute the selected category object from `form.category_id` + **all** `props.categories` (not just filtered) to show the name in the field. Searching only `filteredCategories` would produce a blank label in edit mode when `asset_type` initialises before `categories` prop arrives, or during the brief window before the `initialData` watch fires.
- **`CategoryGrid` is only used in `AssetForm.vue`** (confirmed by grep) — remove the import after the swap.

## Open Questions

### Resolved During Planning

- **Is `CategoryGrid` used outside `AssetForm.vue`?** — Confirmed by grep: only `AssetForm.vue` imports it. The component file can be left as-is (unused) or deleted; the import in `AssetForm.vue` must be removed.
- **How to show icon in `van-field` display value?** — Show only the category name as text in the field value. SVG icons cannot be embedded in a `van-field` value string. The popup grid shows full icon+name.
- **Should `selectedCategoryName` search `filteredCategories` or all categories?** — All `props.categories`. Searching only filtered categories would produce a blank label in edit mode during the window before `initialData` watch fires or before `categories` prop arrives asynchronously.

### Deferred to Implementation

- Exact CSS for popup inner container (max-height, overflow-y) — implement as ~60vh with scroll to handle 13 physical categories on small screens.
- Whether to show a title bar in the popup (e.g. "选择分类") — match the visual convention of other popups in the form at implementation time.

## Implementation Units

- [x] **Unit 1: Verify `CategoryGrid` usage scope**

**Goal:** Confirm whether `CategoryGrid.vue` is referenced outside `AssetForm.vue`.

**Requirements:** Scope boundary — no unintended breakage.

**Dependencies:** None.

**Files:**
- Read: `frontend/src/components/asset/CategoryGrid.vue`

**Approach:**
- Grep confirmed: `CategoryGrid` is only imported in `AssetForm.vue`. The component file can be left as-is; the import in `AssetForm.vue` must be removed after the swap.

**Test scenarios:**
- Test expectation: none — read-only verification step, no behavioral change.

**Verification:**
- Confirmed: `CategoryGrid` referenced only in `AssetForm.vue`.

---

- [ ] **Unit 2: Replace inline `CategoryGrid` with popup picker in `AssetForm.vue`**

**Goal:** Swap the `<van-cell title="分类" />` + `<CategoryGrid .../>` block with a `van-field` (is-link, readonly) that opens a `van-popup` containing a category list with icons.

**Requirements:** R1, R2, R4, R5.

**Dependencies:** Unit 1 (scope confirmed).

**Files:**
- Modify: `frontend/src/components/asset/AssetForm.vue`

**Approach:**
- Add `showCategoryPicker` ref (boolean).
- Add `filteredCategories` computed: `props.categories.filter(c => c.asset_type === form.value.asset_type)`.
- Add `selectedCategoryName` computed: find category by `form.value.category_id` in **all** `props.categories` (not `filteredCategories`) — searching only filtered categories would produce a blank label in edit mode before `initialData` watch fires or while `categories` prop is still loading.
- Replace the `<van-cell>` + `<CategoryGrid>` block with:
  ```
  van-field (is-link, readonly, label="分类", :value="selectedCategoryName", placeholder="请选择分类", @click → showCategoryPicker=true)
  van-popup (v-model:show="showCategoryPicker", position="bottom", round)
    → grid of filteredCategories, each item: SVG icon + name
    → item click handler: set form.value.category_id AND set showCategoryPicker=false
  ```
- For the popup list, use a plain `div` grid (not `van-picker`) to allow SVG icon rendering. Mirror the visual style of `CategoryGrid` (icon above name, 4-column grid). The popup inner container must have a max-height (~60vh) and `overflow-y: auto` to handle 13 physical categories on small screens without clipping. The grid is a flat list of filtered categories — no group headers.
- Copy `getIconId()` helper from `CategoryGrid.vue` into `AssetForm.vue` (or inline it).
- Each grid item applies an `.selected` visual state (border + background tint, matching `CategoryGrid`'s existing `.selected` style) when its `id === form.value.category_id` — so the current selection is highlighted when the popup opens in edit mode.
- When `filteredCategories` is empty (e.g. categories still loading), the popup shows a short text placeholder "暂无分类" instead of a blank grid.
- Remove `CategoryGrid` import (confirmed unused after Unit 1).

**Patterns to follow:**
- Date picker pattern: `AssetForm.vue:88-103` for field+popup structure.
- `CategoryGrid.vue:12-16` for SVG icon rendering (`<svg><use :href="..."/></svg>`).
- `CategoryGrid.vue:64-70` for `getIconId()` — copy or import this helper.

**Test scenarios:**
- Happy path: user selects physical type → taps category field → popup opens showing only physical categories with icons → taps one → popup closes, field shows selected category name.
- Happy path: user selects financial type → popup shows only financial categories (no physical categories visible).
- Happy path (popup close): tapping a category item sets `form.category_id` AND sets `showCategoryPicker = false` in the same handler — popup dismisses immediately.
- Happy path (selected highlight): opening popup in edit mode with a pre-selected category → that item shows `.selected` visual state (border + background tint).
- Edge case: no category selected → field shows placeholder text "请选择分类".
- Edge case: `categories` prop is empty or still loading → popup opens showing "暂无分类" text, no crash.
- Integration (edit mode): `initialData` with `asset_type='financial'` and a valid `category_id` → `selectedCategoryName` shows the correct category name even before the popup is opened, because it searches all `props.categories` not just `filteredCategories`.

**Verification:**
- `npm run build` passes with no type errors.
- Field row visible in form with placeholder when no category selected.
- Tapping field opens popup; tapping a category closes popup and updates field.
- Popup only shows categories matching current asset type.

---

- [ ] **Unit 3: Clear category on asset type change**

**Goal:** When the user switches between physical/financial, clear `form.category_id` if the currently selected category doesn't belong to the new type.

**Requirements:** R3.

**Dependencies:** Unit 2.

**Files:**
- Modify: `frontend/src/components/asset/AssetForm.vue` — `onTypeChange()` function.

**Approach:**
- In `onTypeChange(type)`, after setting `form.value.asset_type = type`, unconditionally set `form.value.category_id = ''`. No lookup into `props.categories` is needed — a category from the wrong type is never valid after a type switch, and the unconditional clear is consistent with how `onTypeChange` already clears `location`, `institution`, and other type-specific fields. Conditional lookup would also fail silently if `props.categories` is still loading when the type switch occurs.
- This is a one-liner addition inside the existing `onTypeChange` function.

**Patterns to follow:**
- `AssetForm.vue:264-279` — existing `onTypeChange` that already clears other type-specific fields.

**Test scenarios:**
- Happy path: user picks a physical category, then switches to financial → `form.category_id` is cleared, field shows placeholder.
- Happy path: user picks a financial category, then switches to physical → `form.category_id` is cleared, field shows placeholder.
- Edge case: no category selected when switching type → `form.category_id` stays `''`, no error.
- Edge case: switching to the same type (guard already exists at line 265) → no-op, category unchanged.

**Verification:**
- After switching type, category field shows placeholder.
- After switching type, re-opening popup shows only the new type's categories.

## System-Wide Impact

- **Interaction graph:** Only `AssetForm.vue` is modified. `CategoryGrid.vue` is untouched (may become unused import).
- **Unchanged invariants:** `form.category_id` binding, `onSubmit` data shape, and all other form fields are unaffected.
- **API surface parity:** No API changes; `category_id` is still submitted as before.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Popup grid clips content on small screens (13 physical categories) | Popup inner container must have max-height (~60vh) and `overflow-y: auto` — specified in Unit 2 approach |
| `CategoryGrid` import left in `AssetForm.vue` after swap | Remove import as part of Unit 2; TypeScript build will catch unused imports |
| Type change clears a valid category the user intended to keep | Acceptable UX — switching asset type is a fundamental change; unconditional clear is consistent with how other type-specific fields are cleared in `onTypeChange` |

## Sources & References

- Related code: `frontend/src/components/asset/AssetForm.vue`, `frontend/src/components/asset/CategoryGrid.vue`
- Vant 4 Picker docs: https://vant-ui.github.io/vant/#/en-US/picker
- Vant 4 Popup docs: https://vant-ui.github.io/vant/#/en-US/popup
