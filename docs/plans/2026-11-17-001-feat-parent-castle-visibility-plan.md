---
title: "feat: Parent-side knowledge castle visibility"
type: feat
status: active
date: 2026-11-17
origin: docs/brainstorms/parent-castle-visibility-requirements.md
---

# feat: Parent-side knowledge castle visibility

## Overview

Add a parent-facing view of the child's knowledge castle. Backend exposes the existing `castle_service.get_castle_index()` through a family-scoped endpoint. Frontend adds a compact summary card on `BabyLearningPage` and a dedicated full-castle page adapted to main-app design tokens.

(see origin: `docs/brainstorms/parent-castle-visibility-requirements.md`)

---

## Problem Frame

The knowledge castle is currently only visible in the child app. Parents lack a visual way to see their child's learning progress and miss a bonding opportunity. The backend service is already parent-compatible — the work is exposing it and building the UI.

---

## Requirements Trace

- R1. `GET /family/learning/children/{child_id}/castle/index` endpoint reusing `castle_service`
- R2. Compact card on `BabyLearningPage` with per-tower progress summary
- R3. Card refreshes with `babyStore.selectedChildId` changes
- R4. "View full castle →" navigation from card to dedicated page
- R5. Dedicated full-castle page at `/baby/learning/castle` mirroring child visual with main-app tokens
- R6. Dedicated page inherits child from `babyStore.selectedChildId`
- R7. CastleIndex types and `fetchChildCastle()` in main app `api/learning.ts`
- R8. All user-facing strings i18n-ized in zh-CN and en-US locale files

**Origin actors:** A1 (Parent), A2 (Child — indirect)
**Origin flows:** F1 (Parent views castle from dashboard), F2 (Parent switches child on castle page)

---

## Scope Boundaries

- No review-due alerts or actionable assignment creation from windows
- No child-picker on dedicated castle page — always inherited from `babyStore`
- No changes to child-app castle — purely additive
- No new backend service logic — `castle_service.get_castle_index()` reused as-is
- No shared package extraction — castle visual duplicated with main-app styling
- No `CastleCelebration` animation in parent view (child-only `?new=` feature)

---

## Context & Research

### Relevant Code and Patterns

- `server/apps/backend/app/routers/learning_family.py` — existing parent endpoint pattern (verify child in family, `get_effective_source_taxonomy`)
- `server/apps/backend/app/schemas/learning.py` — `CastleIndexResponse`, `CastleTowerSchema`, `CastleFloorSchema`, `CastleWindowSchema` (lines 649-685)
- `server/apps/backend/app/services/learning/castle_service.py` — `get_castle_index(db, child_id, family_id, language)` — parent-compatible
- `frontend/apps/child/src/components/learning/KnowledgeCastle.vue` — source visual to duplicate
- `frontend/apps/child/src/data/continentThemes.ts` — subject → color/icon mapping (pure data, needs copy)
- `frontend/apps/main/src/pages/BabyLearningPage.vue` — target for compact card module
- `frontend/apps/main/src/router/index.ts` — `baby/learning/*` routes (line ~492)
- `server/tests/backend/test_learning_castle_api.py` — existing test pattern for castle endpoints

### Institutional Learnings

- `docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md` — main app UI patterns
- Dark mode: main app uses `van-config-provider :theme`, child uses `[data-theme='dark']` — CSS must adapt
- Snowflake IDs: castle `topic_id` fields serialized as `string` — frontend types must match

---

## Key Technical Decisions

- **Duplicate KnowledgeCastle.vue, not extract**: Clay tokens (`--color-ink`, `--color-surface-card`, `--color-muted`) are deeply embedded. Adapting in place with main-app tokens (`--text-primary`, `--card-bg`, `--text-secondary`) is simpler than abstracting a shared token layer.
- **Use `van-skeleton` for loading state**: Main app already uses `van-skeleton` in `BabyLearningPage`. No need to port child-app's `RoleShimmer`.
- **Skip CastleCelebration in parent view**: The celebration is tied to `?new=` topic arrival (child just learned something new). Parents viewing retrospectively don't need this animation.
- **Windows are display-only in parent view**: Child app navigates to practice on window click. Parent view shows window info (review-due / recommended topic name) but does not navigate to practice. Could show topic detail as a stretch goal.

---

## Open Questions

### Resolved During Planning

- **Can parent endpoint reuse existing Castle schemas?** Yes — `CastleIndexResponse` is identical for both child and parent views.
- **Does `continentThemes.ts` need to be in main app?** Yes — it's pure data (subject → color/icon mapping), ~100 lines. Copy it.

### Deferred to Implementation

- **Exact CSS token mapping**: Which Clay tokens map to which main-app tokens needs to be determined while adapting the component. The main candidates: `--color-ink` → `--text-primary`, `--color-muted` → `--text-secondary`, `--color-surface-card` → `--card-bg`, `--color-border` → main-app border variable.

---

## Implementation Units

- U1. **Backend: Parent castle index endpoint**

**Goal:** Expose `GET /family/learning/children/{child_id}/castle/index` for parent access to child's castle data.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `server/apps/backend/app/routers/learning_family.py`
- Test: `server/tests/backend/test_learning_castle_api.py` (or new `test_learning_family_castle_test.py`)

**Approach:**
- Add endpoint following the existing pattern: verify child belongs to family (`User.role == "child"`, `User.family_id == user.family_id`), then call `castle_service.get_castle_index(db, child_id, user.family_id, user.language)`.
- Reuse existing `CastleIndexResponse` schema from `schemas/learning.py`. The `_tower_to_schema` and `_window_to_schema` helpers already exist in `learning_child.py` — they need to be either shared or duplicated. Check if they can be imported or if they're local to `learning_child.py`.
- Follow the same error handling: `AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)` when child not found.

**Patterns to follow:**
- `learning_family.py:get_child_map` (lines 147-176) — same child-verification + taxonomy-filter pattern
- `learning_child.py:my_castle_index` (lines 191-206) — same castle_service call pattern

**Test scenarios:**
- Happy path: authenticated parent requests castle for their child → returns valid `CastleIndexResponse` with towers, windows, streak_days
- Edge case: child with zero progress → returns empty towers skeleton (200, not 404)
- Error path: parent requests castle for child not in their family → `AUTH_CHILD_NOT_FOUND`
- Error path: unauthenticated request → 401

**Verification:**
- `uv run pytest tests/backend/ -v -k castle` passes
- Endpoint visible in OpenAPI docs at `/docs`

---

- U2. **Frontend: Castle API client and types**

**Goal:** Add `CastleIndex` types and `fetchChildCastle(childId)` function to main app API layer.

**Requirements:** R7

**Dependencies:** None (parallel with U1)

**Files:**
- Modify: `frontend/apps/main/src/api/learning.ts`

**Approach:**
- Copy `CastleFloor`, `CastleTower`, `CastleWindow`, `CastleIndex` interfaces from child app's `api/learning.ts` (lines 484-515).
- Add `fetchChildCastle(childId: string)` function calling `GET /family/learning/children/${childId}/castle/index`.
- All ID fields typed as `string` (Snowflake serialization convention).

**Patterns to follow:**
- Child app `api/learning.ts` lines 482-520 (castle types + `fetchCastle`)
- Main app `api/learning.ts` existing functions like `getChildMap(childId)`

**Test expectation:** none — pure type definitions and HTTP wrapper, verified by U3/U4 usage.

**Verification:**
- TypeScript compiles: `pnpm -r typecheck` passes
- Function follows existing patterns (returns `res.data`, uses `http.get`)

---

- U3. **Frontend: Castle data module and dedicated page**

**Goal:** Create the `continentThemes` data file, the parent-adapted `KnowledgeCastle` component, and the dedicated `ParentCastlePage` with route.

**Requirements:** R5, R6

**Dependencies:** U2

**Files:**
- Create: `frontend/apps/main/src/data/continentThemes.ts`
- Create: `frontend/apps/main/src/components/learning/ParentKnowledgeCastle.vue`
- Create: `frontend/apps/main/src/pages/ParentCastlePage.vue`
- Modify: `frontend/apps/main/src/router/index.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**
1. Copy `continentThemes.ts` from child app — pure data, no adaptation needed.
2. Create `ParentKnowledgeCastle.vue` by copying child's `KnowledgeCastle.vue` with these changes:
   - Replace `RoleShimmer` loading state with `van-skeleton`
   - Remove `CastleCelebration` import and celebration logic
   - Remove `?new=` animation props (`newTopicId`, `newSubject`, `newDomain`) — not needed for parent view
   - Remove `windowSelect` emit — windows are display-only (show topic name in tooltip/title attribute)
   - Adapt CSS: replace Clay tokens with main-app tokens:
     - `--color-ink` → `--text-primary`
     - `--color-muted` → `--text-secondary`
     - `--color-surface-card` → `--card-bg`
     - `--color-border` → main-app border (check existing components for the right variable)
     - `--color-primary` → `--van-primary-color`
   - Dark mode: use `van-config-provider` theme, not `[data-theme='dark']` selectors
3. Create `ParentCastlePage.vue`:
   - Reads `babyStore.selectedChildId` — if null, redirect to `/baby/learning`
   - Loads castle data via `fetchChildCastle(childId)`
   - Manages `loading` / `error` / `content` states
   - Wraps `ParentKnowledgeCastle` in `van-pull-refresh`
   - Adds `PageHeader` with title
4. Add route `baby/learning/castle` in `router/index.ts` (after existing `baby/learning/*` routes)
5. Add i18n keys: `learning.castle.*` (title, subtitle, streak, tower summary, empty, error, window labels, a11y)

**Patterns to follow:**
- `BabyLearningPage.vue` — pull-refresh + loading/error/content state pattern
- Child's `LearningCastlePage.vue` — castle page structure (simplified)
- Main app `PageHeader` component for page title
- Main app's dark mode pattern: `van-config-provider` theme

**Test scenarios:**
- Happy path: page loads with valid selectedChildId → renders castle with towers and windows
- Edge case: child with zero progress → renders empty castle (foundation + empty floors)
- Edge case: no child selected (selectedChildId null) → redirects to BabyLearningPage
- Error path: API failure → shows error state with retry button
- Happy path: pull-to-refresh → reloads castle data
- Dark mode: all elements readable in dark theme (no invisible text, no missing backgrounds)

**Verification:**
- Page renders at `/baby/learning/castle` when child is selected
- Dark mode works correctly (no Clay token leakage — all colors use main-app variables)
- `pnpm -r typecheck` and `pnpm -r lint` pass

---

- U4. **Frontend: Compact castle card on BabyLearningPage**

**Goal:** Add a compact castle summary module to `BabyLearningPage` with per-tower progress counts and navigation to the full castle page.

**Requirements:** R2, R3, R4, R8

**Dependencies:** U2, U3

**Files:**
- Modify: `frontend/apps/main/src/pages/BabyLearningPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

**Approach:**
- Add a new `van-collapse-item` module (like DNA Graph, Smart Tutor) named "castle".
- Load castle data via `fetchChildCastle(babyStore.selectedChildId)` when the module expands (lazy load, like cluster map pattern).
- Compact card content:
  - Per-tower row: subject icon + subject name + "mastered/total" progress bar or fraction (e.g., "📐 数学 5/12")
  - "View full castle →" button linking to `/baby/learning/castle`
- Refresh data when `babyStore.selectedChildId` changes (watch, same pattern as existing child-dependent modules).
- Default state: collapsed (like DNA Graph module).

**Patterns to follow:**
- `BabyLearningPage.vue` Module 5 (DNA Graph collapse-item) — same collapse pattern
- `BabyLearningPage.vue` `loadChildDependentData()` — child-dependent data loading pattern
- `loadClusterMap()` lazy-load pattern (load on expand, cache until child changes)

**Test scenarios:**
- Happy path: module shows per-tower summary for selected child's castle
- Happy path: "View full castle →" navigates to `/baby/learning/castle`
- Happy path: switching child tabs refreshes the card data
- Edge case: child with zero progress → shows empty state or minimal summary
- Edge case: API failure → module shows error or empty gracefully (doesn't break page)

**Verification:**
- Compact card appears as a collapse module on `BabyLearningPage`
- Tower counts match the full castle page data
- Switching children updates the card
- Navigation to dedicated page works
- `pnpm -r typecheck` and `pnpm -r lint` pass

---

## System-Wide Impact

- **Interaction graph:** New endpoint at `/family/learning/children/{child_id}/castle/index` — no existing endpoints affected
- **Error propagation:** Standard `AppError` pattern — `AUTH_CHILD_NOT_FOUND` for invalid child_id
- **State lifecycle risks:** None — castle data is read-only, no mutations
- **API surface parity:** Child endpoint `GET /child/learning/castle/index` and parent endpoint return identical schema — no divergence risk since both call the same service
- **Unchanged invariants:** Child-app castle page, castle_service, all existing parent learning endpoints remain untouched

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| CSS token mismatch in duplicated castle component | Systematic token mapping: audit every `var(--color-*)` in child component, replace with main-app equivalent. Test both light and dark mode. |
| `continentThemes.ts` drift between child and main app | Acceptable for now — data is small and stable. If it changes frequently, consider extracting to `@numina/shared` later. |
| `_tower_to_schema` / `_window_to_schema` helpers in `learning_child.py` may be module-private | Check import accessibility. If private, either make them importable or duplicate the thin conversion logic in `learning_family.py`. |

---

## Sources & References

- **Origin document:** [docs/brainstorms/parent-castle-visibility-requirements.md](docs/brainstorms/parent-castle-visibility-requirements.md)
- Child castle page: `frontend/apps/child/src/pages/learning/LearningCastlePage.vue`
- Child castle component: `frontend/apps/child/src/components/learning/KnowledgeCastle.vue`
- Castle service: `server/apps/backend/app/services/learning/castle_service.py`
- Parent learning router: `server/apps/backend/app/routers/learning_family.py`
- Castle schemas: `server/apps/backend/app/schemas/learning.py` (lines 649-685)
