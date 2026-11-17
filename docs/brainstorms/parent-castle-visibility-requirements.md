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

- F1. **Parent views castle on dashboard**
  - **Trigger:** Parent navigates to `BabyLearningPage` with a child selected
  - **Actors:** A1
  - **Steps:**
    1. Parent is on `BabyLearningPage` with a child selected (via existing child-tabs + `babyStore`)
    2. Parent expands the "Knowledge Castle" collapse module
    3. The full castle visualization loads — towers, floors, windows, streak
  - **Outcome:** Parent sees the same visual castle the child sees
  - **Covered by:** R1, R2, R3, R4

- F2. **Parent switches child**
  - **Trigger:** Parent switches child tabs on `BabyLearningPage`
  - **Actors:** A1
  - **Steps:**
    1. Parent taps a different child tab
    2. `babyStore.selectedChildId` updates
    3. The castle module refreshes with the new child's data (same pattern as other child-dependent modules)
  - **Outcome:** Castle always reflects the currently selected child
  - **Covered by:** R3

---

## Requirements

**Backend API**

- R1. Expose `GET /family/learning/children/{child_id}/castle/index` returning the same `CastleIndexResponse` schema as the child endpoint (towers, windows, streak_days). The endpoint verifies `child_id` belongs to the parent's family and reuses `castle_service.get_castle_index()` unchanged.

**Frontend — Castle module on BabyLearningPage**

- R2. Add the full `KnowledgeCastle` component as a new `van-collapse-item` module on `BabyLearningPage`, titled "Knowledge Castle". The module is collapsed by default, consistent with existing modules (DNA Graph, Smart Tutor, etc.).
- R3. The castle module reads `babyStore.selectedChildId` and refreshes when the selected child changes, following the same data-loading pattern as existing child-dependent modules on the page.
- R4. Window clicks in the parent castle navigate to the topic detail page (parent is an observer, not a learner — no practice mode navigation).

**Frontend — API client**

- R5. Add `CastleIndex`, `CastleTower`, `CastleFloor`, `CastleWindow` types and a `fetchChildCastle(childId: string)` function to `apps/main/src/api/learning.ts`, following the existing parent-side API patterns (Snowflake IDs as `string`).

**i18n**

- R6. All new user-facing strings (module title, castle section labels) defined in both `zh-CN.ts` and `en-US.ts` locale files, referenced via `t('key')`. No hardcoded Chinese strings in `.vue` or `.ts` files.

**Tests**

- R7. Backend: Add test for `GET /family/learning/children/{child_id}/castle/index` covering happy path, child-not-in-family (404), and zero-progress child (empty towers). Frontend: Add component test for the castle module data loading and child-switch refresh.

---

## Success Criteria

- Parent can see the full knowledge castle visualization for each child directly on `BabyLearningPage`.
- Switching child on the dashboard automatically refreshes the castle module.
- The backend endpoint reuses `castle_service` without modification — no new service logic.
- Main-app dark-mode works correctly for the castle module (CSS variable adaptation from Clay tokens).
- Backend and frontend tests pass.

---

## Scope Boundaries

- No review-due alerts or actionable "create assignment" from castle windows — parent is an observer.
- No dedicated separate castle page — full castle is inline as a collapse module.
- No changes to the child-app castle — this is additive only.
- No new backend service logic — `castle_service.get_castle_index()` is reused as-is.
- No shared package extraction — the castle visual is duplicated and adapted for main-app tokens.

---

## Key Decisions

- **Full castle as collapse module**: Parent sees the full castle visualization inline on `BabyLearningPage`, not a compact summary + separate page. Simpler navigation, single-page experience.
- **Duplicate, not extract**: `KnowledgeCastle.vue` is tightly coupled to Clay design tokens in the child app. Rather than extracting to `@numina/shared` (which would require token abstraction), duplicate the visual in main app with adapted CSS. This keeps both apps independently evolvable.
- **Inherit child selection**: `babyStore.selectedChildId` is the single source of truth. No new child-switching UI needed.
- **Observer mode**: Window clicks navigate to topic detail, not practice mode — parents observe, they don't drive learning.

---

## Dependencies / Assumptions

- `castle_service.get_castle_index()` returns empty tower skeletons for zero-progress children (already verified: `U5` requirement in child castle). The parent view inherits this behavior — no special empty-state handling needed beyond what the service already provides.
- Main-app router already supports nested routes under `/baby/learning/*` (confirmed: `BabyLearningPage.vue` exists with child routes like `/baby/learning/recommendations`).

---

## Next Steps

-> `/ce-plan` for structured implementation planning.
