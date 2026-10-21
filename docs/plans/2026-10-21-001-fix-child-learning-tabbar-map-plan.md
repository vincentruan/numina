---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
plan_type: fix
origin: https://github.com/vincentruan/numina/issues/140
product_contract_source: ce-plan-bootstrap
created: 2026-10-21
---

# fix(child/learning): TabBar 底部遮挡 + 知识地图节点布局异常

## Summary

Two child/learning UI bugs reported in issue #140:

1. **LearningPathPage** (`/baby/learning/recommendations`) — bottom content hidden behind the fixed-position ChildTabBar because `padding-bottom` only covers `env(safe-area-inset-bottom)`, not the 50px TabBar height.
2. **Knowledge Map** (`/baby/learning/map`) — territory cards not rendering per-domain; nodes appear as a scattered single group instead of organized ClusterTerritory cards. Root cause: `ClusterMap`'s topic-to-cluster matching fails for topics whose `domain` is `null` or doesn't match any cluster, and `ClusterTerritory`'s `content-visibility: auto` may compound rendering issues.

## Problem Frame

Both bugs degrade the learning experience on the child app. The TabBar overlap makes the path page's last items and action buttons inaccessible. The knowledge map fails its core purpose — showing knowledge organized by domain territory — when matching doesn't resolve correctly.

## Requirements

- **R1.** LearningPathPage list content and action buttons must not be obscured by the ChildTabBar.
- **R2.** Other learning subpages with scrollable content must also have adequate bottom clearance.
- **R3.** Knowledge map must render one ClusterTerritory card per matched domain, with topic nodes grouped inside each card.
- **R4.** Topics whose `domain` is null or whose `age_group` doesn't match any cluster should still be placed in the correct domain territory when a same-domain cluster exists, rather than falling into `__other__`.

---

## Key Technical Decisions

### KTD1. Per-page `padding-bottom` over layout-only approach

The `.child-layout` already has `padding-bottom: calc(50px + env(safe-area-inset-bottom))`, but this doesn't reliably prevent individual page content from scrolling behind the fixed TabBar. Each page that has scrollable content needs its own `padding-bottom` to guarantee clearance. This is consistent with how Vant's fixed-tabbar pattern works — the layout reserves space, but scroll containers inside the layout must also account for the fixed element.

### KTD2. Three-tier matching fallback in ClusterMap

Current matching: (1) exact 3-key `(subject, domain, age_group)` → (2) `(subject, domain)`. The fix adds: (3) `(subject)` only — matches the first cluster with the same subject when no domain match exists. This catches topics with null domains and ensures they don't all fall into `__other__`.

### KTD3. Remove `content-visibility: auto` from ClusterTerritory

The `content-visibility: auto` + `contain-intrinsic-size: auto 200px` optimization on `.cluster-territory` risks rendering issues when the territory's actual content doesn't match the estimated intrinsic size. Since ClusterTerritory cards are always visible when their parent ClusterMap is rendered (they're in a vertical list, not a long scrollable document), the performance benefit of content-visibility is negligible. Remove it to eliminate a potential rendering contributor.

---

## Implementation Units

### U1. Fix LearningPathPage bottom padding for TabBar clearance

**Goal:** Ensure the LearningPathPage's bottom content and action area are fully visible above the ChildTabBar.

**Requirements:** R1

**Dependencies:** none

**Files:**
- `frontend/apps/child/src/pages/learning/LearningPathPage.vue`

**Approach:**
1. Change `.learning-path-page` `padding-bottom` from `env(safe-area-inset-bottom)` to `calc(50px + env(safe-area-inset-bottom))` to match the TabBar height used in `ChildLayout`.

**Patterns to follow:** The `calc(50px + env(safe-area-inset-bottom))` formula is already used in `ChildLayout.vue:51` and `.install-prompt` at `ChildLayout.vue:69`.

**Test scenarios:**
- Test expectation: none — CSS-only change, verify visually in browser that the last path item and any action buttons are fully visible above the TabBar.

**Verification:** Open `/baby/learning/recommendations` in the child app. Scroll to the bottom. The last `.path-item` must be fully visible above the TabBar. The bottom of the items-section must not be obscured.

---

### U2. Audit and fix TabBar bottom padding on other learning subpages

**Goal:** Ensure all learning subpages with scrollable content have adequate bottom clearance for the TabBar.

**Requirements:** R2

**Dependencies:** none

**Files:**
- `frontend/apps/child/src/pages/learning/LearningMapPage.vue`
- `frontend/apps/child/src/pages/learning/LearningTopicPage.vue`
- `frontend/apps/child/src/pages/learning/LearningProgressPage.vue`
- `frontend/apps/child/src/pages/learning/LearningSessionPage.vue`
- `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue`
- `frontend/apps/child/src/pages/learning/LearningOnboardingPage.vue`

**Approach:**
1. For each page, add a root-element `padding-bottom: calc(50px + env(safe-area-inset-bottom))` rule to the page's scoped CSS.
2. If the page already has some `padding-bottom`, replace it with the correct formula (e.g., `PracticeSessionPage.vue` has `padding-bottom: 24px` — change to `calc(50px + env(safe-area-inset-bottom))`).
3. Pages that are inherently non-scrollable (e.g., single-screen interaction pages) may skip this — but add the padding defensively anyway; it's harmless whitespace when there's no scroll.

**Patterns to follow:** Same `calc(50px + env(safe-area-inset-bottom))` formula from `ChildLayout.vue:51`.

**Test scenarios:**
- Test expectation: none — CSS-only changes across multiple pages. Verify each page visually in the browser.

**Verification:** Navigate to each learning subpage in the child app. Confirm that the bottom-most content on each page is visible above the TabBar without being obscured.

---

### U3. Fix knowledge map territory matching and rendering

**Goal:** Ensure the knowledge map groups topic nodes into per-domain territory cards rather than collapsing them into a single `__other__` group.

**Requirements:** R3, R4

**Dependencies:** none

**Files:**
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — matching logic in `territories` computed
- `frontend/apps/child/src/components/learning/ClusterTerritory.vue` — remove `content-visibility: auto`
- `frontend/apps/child/src/components/learning/ClusterMap.test.ts` — add test for subject-only fallback

**Approach:**

1. **Remove `content-visibility: auto`** from `.cluster-territory` in `ClusterTerritory.vue`. Remove the `contain-intrinsic-size: auto 200px` rule alongside it. These rules are lines 90-91. The cards are always visible when the parent is rendered, so `content-visibility` provides negligible benefit and risks rendering issues.

2. **Strengthen matching fallback** in `ClusterMap.vue` `territories` computed. After the existing two-tier fallback (exact 3-key → subject+domain), add a third tier:
   - Tier 3: match by `subject` only — find any cluster with `c.subject === item.topic.subject`.
   - For topics with `domain === null`, the fallback chain becomes: exact → domain-empty-match → subject-only → `__other__`.
   
   Implementation direction: extend the `??` chain in the matchingCluster resolution, or add an explicit loop for the third tier after the existing `find` calls fail.

3. **Add dev-mode diagnostic logging.** When items fall into `__other__`, log a `console.warn` in development mode listing the unmatched topic IDs and their domain/age_group values. This helps diagnose data-level issues without affecting production behavior. Guard with `import.meta.env.DEV`.

4. **Update tests** in `ClusterMap.test.ts`:
   - Add test: "falls back to subject-only match when no domain cluster exists" — create items with null domain, verify they match a same-subject cluster instead of going to `__other__`.
   - Existing test "falls back to the domain when no cluster matches the age_group" continues to pass.
   - Existing test "collects unmatched topics into an 'other' territory" — update if needed to reflect the new fallback tier (a topic with a truly non-existent subject should still go to `__other__`).

**Patterns to follow:** The existing two-tier fallback pattern in `ClusterMap.vue:145-154`. The test structure in `ClusterMap.test.ts` (mocks, fixtures, mountMap helper).

**Test scenarios:**
- Topics with null `domain` and a cluster existing for the same `subject` → matched to that cluster (not `__other__`).
- Topics with `domain` that matches a cluster's domain but different `age_group` → matched via tier 2 (subject+domain) — existing behavior, must not regress.
- Topics whose `subject` has no clusters at all → still go to `__other__`.
- Mixed: some topics match exactly, some via tier 2, some via tier 3, some to `__other__` — all placed correctly.

**Verification:** Run `pnpm --filter @numina/child test:run` — all existing tests pass, new test passes. Open `/baby/learning/map` in the child app and verify territory cards render per-domain with nodes grouped inside each card, not as a scattered single group.

---

## Verification Contract

| Gate | What it proves |
|------|---------------|
| `pnpm --filter @numina/child test:run` | ClusterMap matching logic works across all fallback tiers |
| `pnpm --filter @numina/child typecheck` | No type errors introduced |
| Visual: `/baby/learning/recommendations` | Last path item visible above TabBar |
| Visual: `/baby/learning/map` | Territory cards render per-domain |
| Visual: each learning subpage | Bottom content not obscured by TabBar |

## Definition of Done

- [ ] LearningPathPage bottom padding uses `calc(50px + env(safe-area-inset-bottom))`
- [ ] All other learning subpages have matching bottom padding
- [ ] ClusterTerritory no longer uses `content-visibility: auto`
- [ ] ClusterMap matching has 3-tier fallback (3-key → subject+domain → subject-only)
- [ ] Dev-mode diagnostic logging for unmatched items
- [ ] New test for subject-only fallback passes
- [ ] All existing ClusterMap tests still pass
- [ ] typecheck passes for child app
- [ ] Visual verification on all affected pages

## Scope Boundaries

### Not in scope

- Backend cluster API or seed data changes
- Non-learning pages TabBar audit (out of issue scope)
- Introducing a shared CSS variable for the TabBar height (the formula is repeated in 2-3 places; a variable is a nice-to-have but not required by this fix)

### Deferred to follow-up

- If the subject-only fallback still leaves many items in `__other__`, a data-level investigation of the os-taxonomy seed data may be warranted (separate issue)
- Consider a shared `--child-tabbar-height` CSS variable to DRY the repeated `calc(50px + env(safe-area-inset-bottom))` formula across the child app
