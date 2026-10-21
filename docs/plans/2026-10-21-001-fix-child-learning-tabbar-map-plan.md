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

The `.child-layout` already has `padding-bottom: calc(var(--van-tabbar-height) + env(safe-area-inset-bottom))`, but this doesn't reliably prevent individual page content from scrolling behind the fixed TabBar. Each page that has scrollable content needs its own `padding-bottom` to guarantee clearance. This is consistent with how Vant's fixed-tabbar pattern works — the layout reserves space, but scroll containers inside the layout must also account for the fixed element.

**Known tension with `frontend/CLAUDE.md`.** §Mobile H5 Patterns states "**Safe area**: Bottom handled globally in layout; pages don't add own padding". Every learning page already sets `min-height: 100vh` inside `.child-layout`, which is itself `min-height: 100vh` + bottom padding — so the route content is already one tabbar taller than the viewport, and the page-level padding adds a second tabbar of dead space. The original #140 report of obstruction is nonetheless real; the most likely mechanism is mobile viewport overshoot (a `100vh` element is taller than the visual viewport while browser chrome is showing), which page-level padding does not address either. **This remains unverified** — it needs a real device. The rule in `frontend/CLAUDE.md` was not amended by this fix; see §Follow-up.

### KTD2. Territory = one card per domain; matching by domain only

As originally written this decision proposed a three-tier fallback ending in a *subject-only* match, so that topics with a null or unknown domain would never land in `__other__`. Implementation and review showed that tier is harmful: cluster rows come back ordered by `(subject, domain)` (`topic_service.py:153`), so the "first cluster with the same subject" is the subject's alphabetically-first domain. History's 61 Ancient Greece / Medieval Times / Historical Thinking topics were rendered inside the *Ancient Egypt* card, and 15 Probability topics inside *Addition & Subtraction*.

The matching that shipped instead:

- **Territory key is the domain.** `clusters.json` stores one row per `(domain, age_group)`; keying cards on the cluster row produced several cards per domain. Cards are now built from the child's own progress and grouped by domain, with nodes ordered by `AGE_GROUP_ORDER` (`low → mid → high`). This is what R3 and issue #140's "每个 domain 一个卡片" ask for.
- **A known domain matches exactly.** No age-group or subject fallback is needed — the domain alone determines the card.
- **A null domain falls back to the subject's first cluster.** A null domain carries no signal at all, so this is arbitrary; it is retained deliberately so the node stays visible rather than disappearing into `__other__`.
- **An unknown domain goes to `__other__`.** Guessing a sibling domain would mis-attribute the topic.


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
1. Change `.learning-path-page` `padding-bottom` from `env(safe-area-inset-bottom)` to `calc(var(--van-tabbar-height) + env(safe-area-inset-bottom))` to match the TabBar height used in `ChildLayout`.

**Patterns to follow:** The `calc(var(--van-tabbar-height) + env(safe-area-inset-bottom))` formula is already used in `ChildLayout.vue:51` and `.install-prompt` at `ChildLayout.vue:69`.

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
1. For each page, add a root-element `padding-bottom: calc(var(--van-tabbar-height) + env(safe-area-inset-bottom))` rule to the page's scoped CSS.
2. If the page already has some `padding-bottom`, replace it with the correct formula (e.g., `PracticeSessionPage.vue` has `padding-bottom: 24px` — change to `calc(var(--van-tabbar-height) + env(safe-area-inset-bottom))`).
3. Pages that are inherently non-scrollable (e.g., single-screen interaction pages) may skip this. The padding is **not** harmless whitespace: it stacks on `.child-layout`'s existing bottom padding, so every page that receives it ends up one tabbar's height short of the viewport. See KTD1's note on the `frontend/CLAUDE.md` conflict.

**Patterns to follow:** Same `calc(var(--van-tabbar-height) + env(safe-area-inset-bottom))` formula from `ChildLayout.vue:51`.

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
- `frontend/apps/child/src/components/learning/ClusterMap.test.ts` — cover per-domain merging and the `__other__` paths

**Approach:**

1. **Remove `content-visibility: auto`** from `.cluster-territory` in `ClusterTerritory.vue`. Remove the `contain-intrinsic-size: auto 200px` rule alongside it. These rules are lines 90-91. The cards are always visible when the parent is rendered, so `content-visibility` provides negligible benefit and risks rendering issues.

2. **Group cards by domain** in `ClusterMap.vue`'s `territories` computed. The previous code keyed the territory map on `cluster.id`, and the API returns one row per `(subject, domain, age_group)` — several cards per domain. Build the map keyed by domain instead, pick one representative cluster row per domain for the card's summary/age range (lowest `age_range_start`), and sort each card's nodes by `AGE_GROUP_ORDER`.

3. **Match by domain only.** Drop the age-group and subject-only fallback tiers:
   - Known domain → that domain's card. Exact by construction, since cards are keyed by domain.
   - `domain === null` → fall back to the subject's first cluster. A null domain carries no signal; the fallback keeps the node visible rather than hiding it in `__other__`.
   - Unknown domain → `__other__`. Do not attribute it to a sibling domain.

4. **Add dev-mode diagnostic logging.** When items fall into `__other__`, log a `console.warn` in development mode listing the unmatched topic IDs and their domain/age_group values. Guard with `import.meta.env.DEV`. Note the log now fires only for unknown domains, not for every unresolved age-group key — which is the case it was meant to diagnose.

5. **Update tests** in `ClusterMap.test.ts`:
   - Add: "keeps topics in their own domain and sends unknown domains to other".
   - Add: "merges the age groups of one domain into a single territory".
   - Rename/repurpose the null-domain test so it asserts the node actually lands in the card (node count), not on text that cannot appear either way.
   - The `__other__` test must exercise a real path: a same-subject cluster exists but the topic's domain is null and the subject has no cluster — otherwise a `mockResolvedValue([])` makes the assertion vacuous.
   - Existing test "falls back to the domain when no cluster matches the age_group" continues to pass.

**Patterns to follow:** The test structure in `ClusterMap.test.ts` (mocks, fixtures, mountMap helper).

**Test scenarios:**
- Two domains, each with its own cluster → two cards, one per domain.
- One domain with clusters at two age groups → a single card holding both nodes, ordered low → mid.
- Topic with a domain that has no cluster → `__other__`.
- Topic with null `domain` and a same-subject cluster → lands in that cluster's card, not `__other__`.
- Topic with null `domain` and no same-subject cluster → `__other__`.

**Verification:** Run `pnpm --filter @numina/child test:run` — all existing tests pass, new test passes. Open `/baby/learning/map` in the child app and verify territory cards render per-domain with nodes grouped inside each card, not as a scattered single group.

---

## Verification Contract

| Gate | What it proves |
|------|---------------|
| `pnpm --filter @numina/child test:run` | ClusterMap groups by domain and routes null/unknown domains correctly |
| `pnpm --filter @numina/child typecheck` | No type errors introduced |
| Visual: `/baby/learning/recommendations` | Last path item visible above TabBar |
| Visual: `/baby/learning/map` | Territory cards render per-domain |
| Visual: each learning subpage | Bottom content not obscured by TabBar |

## Definition of Done

- [x] LearningPathPage bottom padding uses `calc(var(--van-tabbar-height) + env(safe-area-inset-bottom))`
- [x] All other learning subpages have matching bottom padding
- [x] ClusterTerritory no longer uses `content-visibility: auto`
- [x] ClusterMap renders one territory per domain, with nodes ordered by age group
- [x] Unknown domains go to `__other__`; null domains fall back to the subject's first cluster
- [x] Dev-mode diagnostic logging for unmatched items
- [x] Tests cover per-domain merging, unknown-domain and null-domain routing
- [x] All existing ClusterMap tests still pass (216 tests, 31 files)
- [x] typecheck passes for child app
- [ ] Visual verification on all affected pages — **not done; needs a real device**

## Scope Boundaries

### Not in scope

- Backend cluster API or seed data changes
- Non-learning pages TabBar audit (out of issue scope)

### Deferred to follow-up

- **Resolve the page-vs-layout padding contradiction.** `frontend/CLAUDE.md` says pages must not add bottom padding; every learning page now does, because #140 reported obstruction anyway. Establish the real mechanism (device test of `100vh` overshoot is the leading hypothesis) and either amend the rule or move the clearance back into the layout.
- `--van-tabbar-height` is now used instead of a literal `50px`, so the duplicated *formula* is the remaining DRY candidate, not the magic number.
- If many items still land in `__other__`, investigate the os-taxonomy seed data (separate issue).

