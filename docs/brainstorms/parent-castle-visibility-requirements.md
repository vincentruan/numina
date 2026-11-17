---
date: 2026-11-17
topic: parent-castle-visibility
---

# Parent Castle Visibility — 亲子场景知识城堡

## Problem Frame

The knowledge castle (知识城堡) is currently only visible in the child app. Parents have no way to see their child's castle — the towers, floors, and progress visualization that represents learning progress. This misses a key parent-child bonding opportunity: parents can't share in the child's excitement about their growing castle, and they lack a quick visual summary of per-subject progress.

The backend `castle_service.get_castle_index()` already accepts `child_id` + `family_id` and is inherently parent-compatible. The parent-side `learning_family.py` router already has a well-established pattern of `/family/learning/children/{child_id}/...` endpoints. The work is primarily: expose the existing service through a parent endpoint, and build the parent-side UI.

---

## Actors

- A1. **Parent**: Views their child's knowledge castle to understand learning progress and bond with the child over their achievements.
- A2. **Child** (indirect): The child whose castle data is displayed. Does not interact with the parent view directly.

---

## Key Flows

- F1. **Parent views castle from dashboard**
  - **Trigger:** Parent taps "View Castle" card/entry on `BabyLearningPage`
  - **Actors:** A1
  - **Steps:**
    1. Parent is on `BabyLearningPage` with a child selected (via existing child-tabs + `babyStore`)
    2. Parent sees the compact castle summary card (tower counts per subject, headline stats)
    3. Parent taps "View full castle →" to navigate to the dedicated castle page
    4. The dedicated page loads the full visual castle for the currently selected child
  - **Outcome:** Parent sees both the visual castle and per-tower progress summary
  - **Covered by:** R1, R2, R3, R4, R5

- F2. **Parent switches child on castle page**
  - **Trigger:** Parent navigates back to `BabyLearningPage` and switches child tabs
  - **Actors:** A1
  - **Steps:**
    1. Parent returns to `BabyLearningPage` and taps a different child tab
    2. `babyStore.selectedChildId` updates
    3. The compact castle card refreshes with the new child's data
    4. If parent navigates to the full castle page, it reflects the new child
  - **Outcome:** Castle view always reflects the currently selected child
  - **Covered by:** R3, R6

---

## Requirements

**Backend API**

- R1. Expose `GET /family/learning/children/{child_id}/castle/index` returning the same `CastleIndexResponse` schema as the child endpoint (towers, windows, streak_days). The endpoint verifies `child_id` belongs to the parent's family and reuses `castle_service.get_castle_index()` unchanged.

**Frontend — Compact card on BabyLearningPage**

- R2. Add a compact castle summary card on `BabyLearningPage` showing per-tower progress (subject name + mastered/total counts, e.g. "数学 5/12"). The card is a new collapsible module, consistent with existing modules (DNA Graph, Smart Tutor, etc.).
- R3. The compact card reads `babyStore.selectedChildId` and refreshes when the selected child changes, following the same data-loading pattern as existing child-dependent modules on the page.
- R4. The compact card includes a "View full castle →" action that navigates to the dedicated castle page.

**Frontend — Dedicated castle page**

- R5. Create a dedicated full-castle page (route: `/baby/learning/castle`) that displays the complete visual castle — towers with floors, brick counts, windows (review-due + recommended), streak decoration. The visual should closely mirror the child-app castle but adapted to main-app design tokens (`--card-bg`, `--text-primary`, etc.) for dark-mode consistency.
- R6. The dedicated castle page inherits the selected child from `babyStore.selectedChildId` — no separate child-picker on this page. If `selectedChildId` is null (no child selected), redirect back to `BabyLearningPage` or show an appropriate prompt.

**Frontend — API client**

- R7. Add `CastleIndex`, `CastleTower`, `CastleFloor`, `CastleWindow` types and a `fetchChildCastle(childId: string)` function to `apps/main/src/api/learning.ts`, following the existing parent-side API patterns (Snowflake IDs as `string`).

**i18n**

- R8. All new user-facing strings (module title, compact card labels, page title, etc.) defined in both `zh-CN.ts` and `en-US.ts` locale files, referenced via `t('key')`. No hardcoded Chinese strings in `.vue` or `.ts` files.

---

## Success Criteria

- Parent can see a compact per-subject progress summary on `BabyLearningPage` for each child.
- Parent can navigate to a dedicated full-castle page that visually mirrors the child's castle experience.
- Switching child on the dashboard automatically updates the castle view (compact card and dedicated page).
- The backend endpoint reuses `castle_service` without modification — no new service logic.
- Main-app dark-mode works correctly on the dedicated castle page (no Clay token leakage).

---

## Scope Boundaries

- No review-due alerts or actionable "create assignment" from castle windows — stats layer is limited to per-tower progress summary.
- No child-picker on the dedicated castle page — child selection is always inherited from `babyStore`.
- No changes to the child-app castle — this is additive only.
- No new backend service logic — `castle_service.get_castle_index()` is reused as-is.
- No shared package extraction — the castle visual is duplicated and adapted for main-app tokens.

---

## Key Decisions

- **Duplicate, not extract**: `KnowledgeCastle.vue` is tightly coupled to Clay design tokens in the child app. Rather than extracting to `@numina/shared` (which would require token abstraction), duplicate the visual in main app with adapted CSS. This keeps both apps independently evolvable.
- **Two-tier entry**: Compact card on dashboard for quick glance + dedicated page for full visual. Avoids adding a 7th heavy module to `BabyLearningPage`.
- **Inherit child selection**: `babyStore.selectedChildId` is the single source of truth. No new child-switching UI on the castle page.
- **Stats = tower progress only**: Per-tower mastered/total counts on the compact card. No review-due alerts, no assignment creation actions from windows.

---

## Dependencies / Assumptions

- `castle_service.get_castle_index()` returns empty tower skeletons for zero-progress children (already verified: `U5` requirement in child castle). The parent view inherits this behavior — no special empty-state handling needed beyond what the service already provides.
- Main-app router already supports nested routes under `/baby/learning/*` (confirmed: `BabyLearningPage.vue` exists with child routes like `/baby/learning/recommendations`).

---

## Next Steps

-> `/ce-plan` for structured implementation planning.
