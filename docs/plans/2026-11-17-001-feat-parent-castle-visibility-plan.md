---
title: "feat: Parent-side knowledge castle visibility"
type: feat
status: active
date: 2026-11-17
origin: docs/brainstorms/parent-castle-visibility-requirements.md
---

# feat: Parent-side knowledge castle visibility

## Overview

Add a parent-facing view of the child's knowledge castle. Backend exposes the existing `castle_service.get_castle_index()` through a family-scoped endpoint. Frontend adds the full castle visualization as a collapse module on `BabyLearningPage`, adapted to main-app design tokens.

(see origin: `docs/brainstorms/parent-castle-visibility-requirements.md`)

---

## Problem Frame

The knowledge castle is currently only visible in the child app. Parents lack a visual way to see their child's learning progress and miss a bonding opportunity. The backend service is already parent-compatible — the work is exposing it and building the UI.

---

## Requirements Trace

- R1. `GET /family/learning/children/{child_id}/castle/index` endpoint reusing `castle_service`
- R2. Full `KnowledgeCastle` component as a new `van-collapse-item` module on `BabyLearningPage`
- R3. Castle module refreshes with `babyStore.selectedChildId` changes
- R4. Window clicks navigate to topic detail page (observer mode)
- R5. CastleIndex types and `fetchChildCastle()` in main app `api/learning.ts`
- R6. All user-facing strings i18n-ized in zh-CN and en-US locale files
- R7. Backend + frontend tests

**Origin actors:** A1 (Parent), A2 (Child — indirect)
**Origin flows:** F1 (Parent views castle on dashboard), F2 (Parent switches child)

---

## Scope Boundaries

- No review-due alerts or actionable assignment creation from windows — parent is observer
- No dedicated separate castle page — full castle is inline as collapse module
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
- `frontend/apps/main/src/pages/BabyLearningPage.vue` — target for castle collapse module
- `server/tests/backend/test_learning_castle_api.py` — existing test pattern for castle endpoints

### Institutional Learnings

- `docs/solutions/best-practices/main-app-ui-design-patterns-2026-08-03.md` — main app UI patterns
- Dark mode: main app uses `van-config-provider :theme`, child uses `[data-theme='dark']` — CSS must adapt
- Snowflake IDs: castle `topic_id` fields serialized as `string` — frontend types must match

---

## Key Technical Decisions

- **Full castle as collapse module**: Parent sees the full castle visualization inline on `BabyLearningPage`, not a compact summary + separate page. Simpler navigation, single-page experience.
- **Duplicate KnowledgeCastle.vue, not extract**: Clay tokens (`--color-ink`, `--color-surface-card`, `--color-muted`) are deeply embedded. Adapting in place with main-app tokens (`--text-primary`, `--card-bg`, `--text-secondary`) is simpler than abstracting a shared token layer.
- **Use `van-skeleton` for loading state**: Main app already uses `van-skeleton` in `BabyLearningPage`. No need to port child-app's `RoleShimmer`.
- **Skip CastleCelebration in parent view**: The celebration is tied to `?new=` topic arrival (child just learned something new). Parents viewing retrospectively don't need this animation.
- **Observer mode for windows**: Child app navigates to practice on window click. Parent view navigates to topic detail — parents observe, they don't drive learning.

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
- Test: `server/tests/backend/test_learning_castle_api.py`

**Approach:**
- Add endpoint following the existing pattern: verify child belongs to family (`User.role == "child"`, `User.family_id == user.family_id`), then call `castle_service.get_castle_index(db, child_id, user.family_id, user.language)`.
- Reuse existing `CastleIndexResponse` schema from `schemas/learning.py`. The `_tower_to_schema` and `_window_to_schema` helpers already exist in `learning_child.py` — they need to be either shared or duplicated. Check if they can be imported or if they're module-private.
- Follow the same error handling: `AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)` when child not found.

**Patterns to follow:**
- `learning_family.py:get_child_map` — same child-verification + taxonomy-filter pattern
- `learning_child.py:my_castle_index` — same castle_service call pattern

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

**Requirements:** R5

**Dependencies:** None (parallel with U1)

**Files:**
- Modify: `frontend/apps/main/src/api/learning.ts`

**Approach:**
- Copy `CastleFloor`, `CastleTower`, `CastleWindow`, `CastleIndex` interfaces from child app's `api/learning.ts`.
- Add `fetchChildCastle(childId: string)` function calling `GET /family/learning/children/${childId}/castle/index`.
- All ID fields typed as `string` (Snowflake serialization convention).

**Patterns to follow:**
- Child app `api/learning.ts` castle types + `fetchCastle`
- Main app `api/learning.ts` existing functions like `getChildMap(childId)`

**Test expectation:** none — pure type definitions and HTTP wrapper, verified by U3 usage.

**Verification:**
- TypeScript compiles: `pnpm -r typecheck` passes
- Function follows existing patterns (returns `res.data`, uses `http.get`)

---

- U3. **Frontend: Parent castle component + collapse module integration**

**Goal:** Create the parent-adapted `KnowledgeCastle` component and integrate it as a collapse module on `BabyLearningPage`.

**Requirements:** R2, R3, R4, R6, R7

**Dependencies:** U2

**Files:**
- Create: `frontend/apps/main/src/data/continentThemes.ts`
- Create: `frontend/apps/main/src/components/learning/ParentKnowledgeCastle.vue`
- Modify: `frontend/apps/main/src/pages/BabyLearningPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`
- Test: `frontend/apps/main/src/components/learning/__tests__/ParentKnowledgeCastle.spec.ts` (optional)

**Approach:**
1. Copy `continentThemes.ts` from child app — pure data (subject → color/icon mapping), no adaptation needed.
2. Create `ParentKnowledgeCastle.vue` by copying child's `KnowledgeCastle.vue` with these changes:
   - Replace `RoleShimmer` loading state with `van-skeleton`
   - Remove `CastleCelebration` import and celebration logic
   - Remove `?new=` animation props (`newTopicId`, `newSubject`, `newDomain`) — not needed for parent view
   - Change `windowSelect` emit behavior: navigate to topic detail (`/learning/topics/{topic_id}`) instead of practice mode
   - Adapt CSS: replace Clay tokens with main-app tokens:
     - `--color-ink` → `--text-primary`
     - `--color-muted` → `--text-secondary`
     - `--color-surface-card` → `--card-bg`
     - `--color-border` → main-app border variable
     - `--color-primary` → `--van-primary-color`
   - Dark mode: use `van-config-provider` theme, not `[data-theme='dark']` selectors
3. Add a new `van-collapse-item` module on `BabyLearningPage` titled "Knowledge Castle":
   - Load castle data via `fetchChildCastle(babyStore.selectedChildId)` when module expands (lazy load)
   - Render `ParentKnowledgeCastle` component inside the collapse item
   - Refresh data when `babyStore.selectedChildId` changes (watch, same pattern as existing child-dependent modules)
   - Default state: collapsed (like DNA Graph module)
4. Add i18n keys: `learning.castle.*` (module title, subtitle, streak, tower summary, empty, window labels, a11y)

**Patterns to follow:**
- `BabyLearningPage.vue` Module 5 (DNA Graph collapse-item) — same collapse pattern
- `BabyLearningPage.vue` `loadClusterMap()` lazy-load pattern (load on expand, cache until child changes)
- Child's `KnowledgeCastle.vue` — base component to adapt
- Main app's dark mode pattern: `van-config-provider` theme

**Test scenarios:**
- Happy path: collapse module expands → loads and renders castle with towers and windows
- Happy path: switching child tabs refreshes the castle data
- Edge case: child with zero progress → renders empty castle (foundation + empty floors)
- Edge case: API failure → module shows error or empty gracefully (doesn't break page)
- Happy path: window click navigates to topic detail page
- Dark mode: all elements readable in dark theme (no Clay token leakage)

**Verification:**
- Castle module appears as a collapse item on `BabyLearningPage`
- Dark mode works correctly (no Clay token leakage — all colors use main-app variables)
- Switching children updates the castle
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
