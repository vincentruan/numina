---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
title: "Knowledge Map v2 — Animated Path Recommendation Highlight - Plan"
date: 2026-10-22
focus: "Add animated path-finding visualization on the child cluster knowledge map, highlighting the recommended learning route through topic nodes"
---

<!-- Product Contract preservation: unchanged. All R-IDs, KTD-IDs, AE-IDs carried forward from requirements-only version. OQ1 and OQ2 resolved in Planning Contract. -->

## Goal Capsule

**Objective:** Add an animated recommendation path overlay to the child app's cluster knowledge map. A flowing gradient trail with subtle pulse dots connects the top 3-5 recommended topics, and a sticky CTA card at the top names the immediate next topic with a tap-to-start action.

**Product authority:** Child app learning map page (`frontend/apps/child/src/pages/learning/LearningMapPage.vue`), extending the existing `ClusterMap.vue` component.

**Open blockers:** None. The recommendation engine (`recommendation_service.py`) already produces a ranked topic path. The v1 cluster map is deployed. This is a visualization and UX layer on top of existing data.

## Product Contract

### Summary

An animated path overlay on the cluster knowledge map that visualizes the child's recommended learning route. A flowing gradient trail (with subtle pulse dots as rhythm accents) connects 3-5 recommended topic nodes in rank order, crossing cluster and domain boundaries as needed. A sticky CTA card below the progress bar shows "Next up: [topic] → Start". Collapsed domain sections display count badges for hidden path topics. The path recomputes live when the child returns from practice.

### Problem Frame

The v1 cluster knowledge map shows territories and topic nodes colored by mastery state, but does not visualize the learning path between them. Children cannot see "where to go next" as a guided route through the knowledge graph. The recommendation engine produces a ranked list of topics (from breakpoint, curriculum gap, and review dimensions), but this ranking is invisible on the map. The only signal is a static frontier banner naming one topic. The child lacks a visual journey — a sense of progression through the knowledge space.

### Requirements

**Path visualization**

- R1. The map renders an animated path connecting the top 5 recommended topics. The path follows the recommendation engine's rank order, not spatial adjacency or prerequisite edges. The backend `limit` parameter allows adjustment if needed.
- R2. The path animation uses a flowing gradient trail (head bright, tail fading) with subtle pulse dots along the path as rhythm accents. The trail flows continuously in the direction of the learning sequence.
- R3. The path is rendered as an SVG overlay on top of the existing CSS/HTML cluster map. It does not alter the v1 rendering of cluster territories, topic nodes, or domain sections.
- R4. The path connects topic nodes across cluster and domain boundaries. Connecting curves use smooth bezier paths that avoid overlapping topic nodes where possible.

**Collapsed domain handling**

- R5. When the recommendation path includes topics in a collapsed domain section, that section displays a count badge showing how many path topics are hidden inside (e.g., "[2]").
- R6. The path is only drawn between visible (expanded-domain) topic nodes. Segments crossing collapsed domains are omitted from the visible path — the count badge indicates their presence.
- R7. Tapping the count badge expands the domain section, revealing the hidden path segments.

**Next-up CTA card**

- R8. A sticky card is displayed below the progress bar, replacing the existing frontier banner (which becomes redundant — the CTA card contains the same information plus an action). The card shows the name of the first recommended topic and a start-practice action.
- R9. Tapping the CTA card starts practice for the named topic directly (same as tapping an available/learning topic node in v1).

**Live refresh**

- R10. When the child returns to the map after completing a practice session, the recommendation path recomputes. The CTA card updates to the new first-recommended topic. The path animation redraws to connect the updated topic set.

**Accessibility and performance**

- R11. The path animation respects `prefers-reduced-motion`. When the user has this preference set, the path renders as a static highlighted line (no flowing animation, no pulse dots).
- R12. Path rendering stays within the 16ms frame budget on mobile. The SVG overlay does not trigger layout reflows on the underlying cluster map.

### Key Decisions

- KTD1. **Recommendation rank over spatial adjacency** (session-settled: user-directed — chose "follow recommendation rank" over "prerequisite-chain first" and "cluster-aware hybrid"): the path connects topics in the engine's priority order, even when this produces long connecting lines across clusters. This gives the child an honest view of the recommended learning sequence rather than a spatially curated route. Governs R1, R4.

- KTD2. **Sticky CTA card as separate element** (session-settled: user-directed — chose "sticky CTA card" over "enhanced first path node" and "path-only, no separate CTA"): the "next up" indicator is an independent card at the top of the map, not just a visual treatment on the first path node. This separates the actionable call-to-action from the informational path visualization. Governs R8, R9.

- KTD3. **Count badges on collapsed domains** (session-settled: user-directed — chose "show indicators on collapsed" over "auto-expand path domains" and "floating overlay path"): collapsed domain sections show how many path topics they contain, rather than auto-expanding (which causes layout jumps) or rendering a floating overlay (which adds visual complexity). Governs R5, R6, R7.

- KTD4. **Live refresh on practice return** (session-settled: user-directed — chose "live refresh on return" over "per-session snapshot"): the path recomputes whenever the child returns from practice and mastery state changes. The child always sees the freshest recommendation. Governs R10.

- KTD5. **B1 animation style — gradient trail + pulse dots** (session-settled: user-directed — chose B1 mix over pure A/B/C): the flowing gradient trail is the primary visual element (direction and flow), with subtle pulse dots as secondary rhythm accents. Dots are small and soft, not dominant. Governs R2.

- KTD6. **SVG overlay on existing CSS map** (Governs R3). The path is a new SVG layer positioned over the existing HTML cluster map. The v1 territory/node rendering stays untouched.

### Acceptance Examples

- AE1. A child with 3 mastered topics in "加减法" opens the learning map. The CTA card reads "下一步: 50以内加法 →". Below, a flowing blue gradient trail pulses from the "20以内加法" node (gold, mastered) through "50以内加法" (blue, frontier), continuing to "进位加法" and "连续进位" in the next cluster. The trail flows from left to right, bright at the head.

- AE2. The same child has collapsed the "乘法" domain. The "乘法" section header shows a badge "[1]" indicating one path topic is hidden inside. The visible path skips from the last "加减法" path node to the next visible path node in an expanded domain.

- AE3. The child taps the CTA card. Practice starts for "50以内加法". After completing the practice, the child returns to the map. The node "50以内加法" is now gold. The CTA card updates to "下一步: 进位加法 →". The path redraws, starting from "进位加法" and connecting 4 more recommended topics.

- AE4. A child with `prefers-reduced-motion` enabled sees the same path, but as a static blue line (no flowing animation, no pulse dots). The CTA card and count badges work identically.

- AE5. A child with no progress sees the path starting from the first available topic in the first cluster. All path nodes are purple (available). The CTA card names the first topic.

- AE6. A child's path includes a locked topic in a cluster they haven't reached yet. Tapping the locked node shows the prerequisite guidance sheet (v1 behavior). The path line still connects through the locked node, showing it is part of the recommended route.

- AE7. A child with 100% mastery in the current subject sees no path overlay and no CTA card. The existing "all mastered" celebration message is shown. The map displays all nodes in gold.

### Scope Boundaries

**Deferred for later:**
- Parent-side path visualization (DnaGraph2D.vue) → [#137](https://github.com/vincentruan/numina/issues/137)
- Cross-subject bridge visualization enhancement → [#136](https://github.com/vincentruan/numina/issues/136)
- Path narrative labels ("Master this first → Then bridge to Science") between segments
- Haptic or audio feedback on path interactions

**Outside this product's identity:**
- Recommendation algorithm changes — this feature visualizes the existing engine output
- Free-form graph exploration (pinch-to-zoom, force-directed layout) → [#135](https://github.com/vincentruan/numina/issues/135)
- Teacher/instructor view

### Outstanding Questions

- OQ1. **Tap on locked path node.** Resolved: path membership is sufficient visual context. Locked path nodes retain v1 tap behavior (prerequisite guidance sheet). No additional "Why recommended" indicator — the path membership itself communicates recommendation.
- OQ2. **Path segment routing across distant clusters.** Deferred to implementation: use direct bezier curves, accepting visual overlap with intermediate nodes. Validate in first implementation pass whether overlap is acceptable before adding waypoint routing complexity.

---

## Planning Contract

### High-Level Technical Design

**Data flow:**

```
Backend (existing)
  GET /family/learning/children/{child_id}/recommendations
    → RecommendationPathResponse { topics: [RecommendedTopicItem] }
        ↓
Frontend API (new)
  useRecommendationPath(childId) composable
    → fetchRecommendationPath() → reactive { pathTopics, nextTopic }
        ↓
LearningMapPage (modify)
  → calls composable, passes pathTopics + nextTopic as props
        ↓
ClusterMap (modify)
  → receives pathTopicIds, nextTopic
  → forwards to PathOverlay and NextUpCard
  → computes pathCountPerDomain for DomainSection badges
        ↓
PathOverlay (new)         NextUpCard (new)      DomainSection (modify)
  SVG overlay               Sticky CTA card       Count badge prop
```

**SVG overlay positioning:**

The `.cluster-map` div serves as the positioning container. The PathOverlay component renders an `<svg>` with `position: absolute; inset: 0; pointer-events: none;` inside `.cluster-map`. It measures topic node positions via `getBoundingClientRect()` on TopicNode DOM elements, computing coordinates relative to the `.cluster-map` container. `pointer-events: none` ensures the overlay doesn't intercept taps — they pass through to the underlying topic nodes.

**Risk: CSS transform clipping.** If any ancestor of `.cluster-map` applies `transform` (GPU acceleration), it creates a new containing block that clips `position: absolute` descendants (see `docs/solutions/ui-bugs/action-sheet-clipped-in-transformed-container.md`). The current `.cluster-map` container has no transformed ancestors, so this is safe for now. If a future change introduces transforms on ancestors, the fix is `<Teleport to="body">` with scroll-synchronized positioning.

**Animation via CSS keyframes:**

```
Gradient trail: stroke-dasharray + animated stroke-dashoffset
  → creates flowing highlight effect moving along the path
Pulse dots: animated r (radius) + opacity with staggered animation-delay
  → creates sequential pulsing rhythm along the path
```

Both animations follow existing codebase patterns (CSS `@keyframes` + `animation:` property — see `RoleShimmer.vue`, `ProgressRing.vue`). No GSAP, canvas, or requestAnimationFrame.

### Implementation Units

#### U1. Recommendation path frontend integration

**Goal:** Create a child-facing recommendation API endpoint on the backend and a frontend composable that fetches the recommendation path, making it available as reactive data for the map components.

**Requirements:** R1, R10

**Dependencies:** None (backend recommendation service already exists)

**Files:**
- `server/apps/backend/app/routers/learning_child.py` — add child-facing recommendation endpoint
- `frontend/apps/child/src/api/learning.ts` — add `fetchRecommendationPath(childId)` function
- `frontend/apps/child/src/composables/useRecommendationPath.ts` — new composable
- `frontend/apps/child/src/types/learning.ts` — add `RecommendedTopic`, `RecommendationPath` types
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — add path-related i18n keys
- `frontend/apps/child/src/i18n/locales/en-US.ts` — add English translations

**Approach:**
1. **Backend: child-facing endpoint.** The existing endpoint at `learning_family.py` uses `require_adult` dependency — the child app cannot call it (403). Add a new endpoint in `learning_child.py` at `GET /learning/children/me/recommendations` that uses child authentication (same pattern as other `learning_child.py` endpoints). It calls the existing `generate_recommendation_path(db, child_id, limit=5)` service internally.
2. **Frontend API wrapper.** Add `fetchRecommendationPath(childId: string)` to the learning API module using the existing axios wrapper. The actual response schema is nested: `response.path.topics` (not `response.topics`) — the `RecommendationPathResponse` wraps a `RecommendationPathDetail` object.
3. **Composable.** Create `useRecommendationPath(childId)` composable that wraps the API call with loading state, returns `{ allPathTopics, nextTopic, isLoading, refresh }`. The composable returns ALL path topics (unfiltered) — subject filtering is done by the consumer (LearningMapPage/ClusterMap) based on the currently selected subject. This avoids refetching on every tab switch.
4. **Types.** Define TypeScript types matching the backend schema. topic_id as string per SnowflakeBase convention. Fields: `topic_id, topic_name, reasons, centrality, prerequisites_met, suggested_position`.
5. **i18n keys.** Add: `learning.path.nextStep`, `learning.path.startPractice`, `learning.path.hiddenTopics`, `learning.path.pathA11yLabel`, `learning.path.noRecommendations`.
6. **Loading behavior.** While `isLoading` is true, the composable returns empty arrays. Components render nothing during loading (the v1 map without path overlay is the loading state — no skeleton needed since the API call is fast).

**Patterns to follow:**
- Existing API wrapper pattern in `frontend/apps/child/src/api/learning.ts`
- `useReducedMotion.ts` composable pattern for reactive state
- Snowflake ID as string in TypeScript types (frontend AGENTS.md invariant)

**Test scenarios:**
- Child-facing endpoint returns typed data matching backend schema (with child auth)
- Endpoint rejects unauthenticated requests (401)
- Composable sets loading state during fetch, clears on completion
- Composable handles API error gracefully (empty path, no crash)
- Response schema correctly accesses nested `response.path.topics`

**Verification:** Child-facing backend endpoint works with child auth; frontend composable fetches and returns the recommendation path; types align with backend schema; i18n keys defined for both locales.

---

#### U2. PathOverlay SVG component with animation

**Goal:** Create a new Vue component that renders an SVG overlay connecting recommended topic nodes with an animated flowing gradient trail and subtle pulse dots.

**Requirements:** R1, R2, R3, R4, R6, R11, R12

**Dependencies:** U1

**Files:**
- `frontend/apps/child/src/components/learning/TopicNode.vue` — add `data-topic-id` attribute
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — add `position: relative` to `.cluster-map`
- `frontend/apps/child/src/components/learning/PathOverlay.vue` — new component
- `frontend/apps/child/src/components/learning/__tests__/PathOverlay.spec.ts` — tests

**Approach:**
1. **Prerequisite: `data-topic-id` attribute.** TopicNode components currently have no data attribute for DOM querying. Add `:data-topic-id="item.topic.id"` to the topic node element in `TopicNode.vue` (or `ClusterTerritory.vue` where nodes are rendered). This allows PathOverlay to locate nodes via `document.querySelector('[data-topic-id="..."]')`.
2. **Prerequisite: `position: relative` on `.cluster-map`.** Add `position: relative` to the `.cluster-map` CSS class in `ClusterMap.vue`. This establishes the positioning context for the SVG overlay.
3. Component receives props: `pathTopicIds: string[]` (ordered), `allItems: ProgressWithTopic[]`, `expandedDomains: Set<string>`
4. On mount and on data change (watch), measure topic node positions:
   - For each path topic ID, find its DOM element via `document.querySelector('[data-topic-id="..."]')`
   - Call `getBoundingClientRect()` and compute position relative to `.cluster-map` container
   - Skip topics in collapsed domains (not visible in DOM)
   - Use `nextTick()` before measuring to ensure layout has settled after data changes
5. Generate SVG path: connect measured positions with cubic bezier curves
   - Control points: offset horizontally for smooth S-curves between nodes
   - Direct connection (no waypoint routing) per OQ2 resolution
6. Render SVG elements:
   - `<svg>` root with `role="img"` and `aria-hidden="true"` (the path is decorative — CTA card and count badges convey all information accessibly)
   - `<defs>` with `<linearGradient>` for the trail gradient
   - `<path>` for the gradient trail (thicker, animated `stroke-dashoffset`)
   - `<circle>` elements for pulse dots at midpoint intervals along the path (staggered `animation-delay`)
7. Use `useReducedMotion()` composable: when true, render static path (no `stroke-dashoffset` animation, no pulse dots, just a solid highlighted line)
8. SVG container: `position: absolute; inset: 0; pointer-events: none; overflow: visible; z-index: 1;` — overlay sits above nodes visually but doesn't intercept taps. z-index must be below any modal/bottom-sheet layer (PrerequisiteGuidance, van-popup).
9. Recompute on window resize via `ResizeObserver` on the `.cluster-map` container, debounced to avoid visual jitter during rotation/resize.

**Technical design (directional):**
```
Template:
  <svg class="path-overlay" v-if="visibleSegments.length > 0">
    <defs>
      <linearGradient :id="gradientId">
        <stop offset="0%" stop-color="var(--color-path-trail-start)" />
        <stop offset="100%" stop-color="var(--color-path-trail-end)" />
      </linearGradient>
    </defs>
    <path :d="trailPath" class="path-overlay__trail" />
    <circle v-for="dot in pulseDots" :key="dot.i"
      :cx="dot.x" :cy="dot.y" :r="dot.r"
      class="path-overlay__dot"
      :style="{ animationDelay: dot.delay }" />
  </svg>

CSS animations:
  .path-overlay__trail:
    stroke: url(#gradient); stroke-width: 4;
    stroke-dasharray: 80 120;
    animation: path-flow 2.5s linear infinite;
  @keyframes path-flow { to { stroke-dashoffset: -200; } }

  .path-overlay__dot:
    fill: var(--color-path-dot);
    animation: dot-pulse 1.8s ease-in-out infinite;
  @keyframes dot-pulse:
    0%, 100% { r: 3; opacity: 0.4; }
    50% { r: 5; opacity: 0.9; }

  @media (prefers-reduced-motion: reduce):
    .path-overlay__trail: animation: none; stroke-dasharray: none;
    .path-overlay__dot: animation: none; opacity: 0.6;
```

**Patterns to follow:**
- CSS `@keyframes` pattern from `RoleShimmer.vue`, `ProgressRing.vue`
- `useReducedMotion()` composable usage from `HackerGreeting.vue`
- Component-local state pattern (no Pinia) from `ClusterMap.vue`

**Test scenarios:**
- Covers AE4: SVG renders with correct number of path segments for visible topics
- SVG path coordinates match measured node positions (within tolerance)
- Covers AE2: topics in collapsed domains are skipped — no SVG segment drawn for them
- Covers R11: reduced motion → no CSS animation classes applied, static path rendered
- Empty path (no recommended topics) → no SVG rendered
- Window resize triggers position re-measurement

**Verification:** SVG overlay renders animated path connecting recommended topic nodes; animation matches B1 style (gradient trail + pulse dots); reduced motion produces static path; `pointer-events: none` confirmed on overlay.

---

#### U3. NextUpCard CTA component

**Goal:** Create a sticky CTA card displayed below the progress bar, replacing the existing frontier banner. Shows the next recommended topic with a tap-to-start action.

**Requirements:** R8, R9

**Dependencies:** U1

**Files:**
- `frontend/apps/child/src/components/learning/NextUpCard.vue` — new component
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — remove frontier banner, add NextUpCard
- `frontend/apps/child/src/components/learning/__tests__/NextUpCard.spec.ts` — tests

**Approach:**
1. Props: `topic: ProgressWithTopic | null` (the first recommended topic for current subject), `topicName: string`, `loading: boolean`
2. **Replaces the frontier banner.** The existing `cluster-map__frontier-banner` div in `ClusterMap.vue` is removed; NextUpCard takes its place. The frontier banner's information (current frontier topic name) is subsumed by the CTA card.
3. **States:**
   - **Loading:** render nothing (map shows v1 layout without card)
   - **Empty (topic is null):** render nothing — the existing "all mastered" celebration message (already in ClusterMap) handles this case
   - **Loaded:** show topic name + start-practice arrow/button
4. Render as a card styled with clay.css tokens (`--color-surface-card`, `--color-ink`, `--color-primary`). No inline styles.
5. Tap action: navigate to practice route (same as `onTopicTap` for available/learning topics in `ClusterMap.vue:470-487`)
6. Touch target: ≥ 44×44px per child app invariant

**Patterns to follow:**
- Card styling from existing `cluster-map__frontier-banner` in `ClusterMap.vue`
- Tap navigation from `ClusterMap.vue:onTopicTap` (lines 470-487)
- Dark mode: clay.css tokens, no inline styles (per `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`)

**Test scenarios:**
- Card displays topic name when topic is provided
- Card is hidden when topic is null
- Tap navigates to practice route with correct topic ID
- Touch target meets 44×44px minimum

**Verification:** CTA card renders below progress bar; tap navigates to practice; card updates when topic changes; dark mode styling correct.

---

#### U4. DomainSection path count badge

**Goal:** Add a count badge to collapsed DomainSection headers showing how many recommendation path topics are hidden inside.

**Requirements:** R5, R7

**Dependencies:** U1

**Files:**
- `frontend/apps/child/src/components/learning/DomainSection.vue` — add `pathCount` prop + badge rendering
- `frontend/apps/child/src/components/learning/__tests__/DomainSection.spec.ts` — tests

**Approach:**
1. Add optional `pathCount?: number` prop to DomainSection
2. When `pathCount > 0` and section is collapsed, render a small badge (e.g., `[2]`) in the section header
3. Badge styling: small pill shape, accent color to draw attention without overwhelming
4. Tapping the badge triggers the existing `@toggle` event (expanding the section) — no separate handler needed, the badge is part of the clickable header area
5. Badge disappears when section is expanded (path topics become visible in the overlay)

**Patterns to follow:**
- Existing header layout in `DomainSection.vue` (lines 1-23)
- Badge styling similar to bridge badges in `ClusterTerritory.vue` (pill-shaped)

**Test scenarios:**
- Badge renders when pathCount > 0 and collapsed
- Badge hidden when section is expanded
- Badge hidden when pathCount is 0 or undefined
- Tap on badge area triggers section expand (existing toggle behavior)

**Verification:** Collapsed domain sections show count badges for path topics; tapping expands the section.

---

#### U5. LearningMapPage integration and live refresh

**Goal:** Wire all new components together in LearningMapPage and ClusterMap. Integrate the recommendation composable, add live refresh on practice return, and ensure the path overlay and CTA card update correctly.

**Requirements:** R1, R5, R6, R7, R8, R9, R10

**Dependencies:** U1, U2, U3, U4

**Files:**
- `frontend/apps/child/src/pages/learning/LearningMapPage.vue` — integrate composable, pass data
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — receive and distribute path data

**Approach:**
1. In `LearningMapPage.vue`:
   - Import and call `useRecommendationPath(childId)` composable
   - Pass `allPathTopics`, `nextTopic` (computed from allPathTopics filtered by current subject), `isLoading` as props to `ClusterMap`
   - Subject filtering: compute `nextTopic` as the first topic in `allPathTopics` whose subject matches `selectedSubject`. This is a computed property in LearningMapPage — no refetch on tab switch.
   - On `onRefresh()` (lines 227-237): also refresh recommendation data via composable's `refresh()` method
   - On `onActivated()`: re-fetch recommendation data (live refresh after practice return per KTD4)
2. In `ClusterMap.vue`:
   - Accept new props: `pathTopicIds: string[]` (filtered to current subject), `nextTopic: ProgressWithTopic | null`, `isLoading: boolean`
   - **Remove the existing frontier banner** (`cluster-map__frontier-banner` div) — replaced by NextUpCard
   - Render `NextUpCard` between progress bar and domain sections, passing `nextTopic` and `isLoading`
   - Render `PathOverlay` inside `.cluster-map` container
   - **Track expanded domain state:** DomainSection already emits `@toggle` events. ClusterMap maintains a reactive `Set<string>` of expanded domain keys, updated on each toggle event. Pass this set to PathOverlay as the `expandedDomains` prop.
   - Compute `pathCountByDomain`: for each territory, count how many path topics (from `pathTopicIds`) belong to its domain AND the domain is currently collapsed
   - Pass `pathCount` to each `DomainSection` component
3. Wire CTA tap to existing practice navigation flow
4. Wire count badge tap to existing domain expand flow (already handled by DomainSection's `@toggle`)

**Test scenarios:**
- Covers AE3: after practice completion and page re-activation, recommendation path updates
- Subject tab switch filters path topics correctly
- ClusterMap distributes path data to PathOverlay, NextUpCard, and DomainSections
- Collapsed domain sections receive correct pathCount values

**Verification:** Full integration works end-to-end; recommendation data loads and displays; live refresh works on practice return; subject switching filters path; all child components receive correct data.

---

#### U6. Accessibility: reduced motion and dark mode

**Goal:** Ensure the path animation, CTA card, and badges work correctly under `prefers-reduced-motion` and dark mode.

**Requirements:** R11, R12

**Dependencies:** U2, U3

**Files:**
- `frontend/apps/child/src/components/learning/PathOverlay.vue` — reduced motion styles
- `frontend/apps/child/src/components/learning/NextUpCard.vue` — dark mode styles
- `frontend/apps/child/src/assets/clay.css` — add path animation CSS variables for both themes

**Approach:**
1. **Reduced motion** (R11):
   - `PathOverlay.vue`: use `useReducedMotion()` composable; when active, render trail as solid `stroke` (no `stroke-dasharray`, no `stroke-dashoffset` animation) and omit pulse dots entirely
   - `NextUpCard.vue`: no animation on card appearance
   - CSS fallback: also include `@media (prefers-reduced-motion: reduce)` query as safety net in case composable doesn't catch all cases
2. **Dark mode** (R12):
   - Define CSS variables in `clay.css` for both themes:
     - `--color-path-trail-start`, `--color-path-trail-end` — gradient stops
     - `--color-path-dot` — pulse dot fill color
     - `--color-path-badge-bg`, `--color-path-badge-text` — count badge colors
   - PathOverlay and NextUpCard use these variables, not hardcoded colors
   - Verify: no inline `style` attributes for theme-sensitive properties (per `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`)
3. **Performance** (R12):
   - SVG uses `will-change: transform` only on the animated path element, not the whole SVG
   - No `getBoundingClientRect()` calls inside animation frames — measurements happen on data change, not per-frame
   - Verify on mobile: path rendering stays under 16ms per frame during animation

**Patterns to follow:**
- `useReducedMotion()` composable pattern from `HackerGreeting.vue`
- Dark mode CSS variable pattern from `clay.css` (`:root` + `[data-theme="dark"]`)
- Animation performance: CSS animations over JS, `will-change` sparingly

**Test scenarios:**
- Covers AE4: reduced motion → static path, no animation classes
- Dark mode: path gradient visible against dark background (warm clay tokens)
- Light mode: path gradient visible against warm cream background
- Performance: no layout thrashing during animation (measurements decoupled from render loop)

**Verification:** Reduced motion produces static path; dark mode colors correct via CSS variables; no inline styles; animation performance acceptable on mobile.

---

### Verification Contract

**Functional gates:**
- `pnpm --filter ./apps/child typecheck` passes
- `pnpm --filter ./apps/child lint` passes
- `pnpm --filter ./apps/child test:run` passes

**Integration validation:**
- Full flow: recommendation data loads → path renders → CTA card displays → tap navigates to practice
- Live refresh: after practice completion and page re-activation, path updates
- Collapsed domains show correct count badges
- Subject tab switch filters path topics

**Accessibility validation:**
- `prefers-reduced-motion`: path renders as static line
- Dark mode: path visible with warm clay tokens
- Touch targets ≥ 44×44px on CTA card and badges

**Performance validation:**
- Path rendering under 16ms frame budget on mobile
- No layout reflows triggered by SVG overlay during animation
- Path overlay tested at 375px width (minimum mobile); SVG overflow does not clip or overlap adjacent UI elements

### Definition of Done

- All R-IDs satisfied (R1-R12)
- All AEs validated (AE1-AE5)
- 6 implementation units implemented and verified
- Backend endpoint confirmed working (no backend changes needed)
- Frontend tests passing for all new components
- Type checking and linting clean
- Dark mode validated for all new UI elements
- Accessibility validated (reduced motion, touch targets)
- No regression on existing cluster map functionality (v1 features intact)
