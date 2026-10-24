---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
title: "Learning Map Domain Grouping - Plan"
date: "2026-10-21"
type: feat
topic: learning-domain-grouping
---

## Goal Capsule

**Objective:** Add collapsible domain-level sections to the child app's ClusterMap so children can navigate high-density subjects (e.g., Mathematics with 50+ clusters) without endless scrolling.

**Product authority:** Child app `ClusterMap.vue` and its immediate children. ClusterTerritory, TopicNode, and LearningMapPage internals are adjusted only as needed to support the grouping wrapper.

**Open blockers:** None. The cluster API already returns `domain` on every `ClusterResponse`. No backend changes needed.

**Product Contract preservation:** Unchanged. All R-IDs, AE-IDs, and Key Decisions preserved verbatim.

---

## Product Contract

### Summary

Wrap the existing flat list of `ClusterTerritory` cards inside collapsible domain-level sections. Clusters sharing the same `domain` within a subject tab form one section with a tappable header showing the domain name and mastery progress. Progress counts aggregate all topics across all clusters (age_group variants) within the domain. Sections auto-expand when they contain active learning and auto-collapse when the child has no progress there. Collapse state persists globally across subject tab switches.

### Problem Frame

The v1 cluster knowledge map (PR #132) renders every cluster as a territory card in a flat vertical list. Mathematics alone has ~503 topics across 50+ clusters. Scrolling through all territory cards on a 375px screen is long and disorienting — children cannot quickly find the domain they are working on or skip domains they have not reached. The parent-side DnaGraph2D already provides zoomable overview, but the child's primary navigation surface needs a way to compress unexplored territory while keeping active learning front and center.

### Requirements

**Grouping and structure**

- R1. Cluster territories within each subject tab are grouped by `cluster.domain`. All clusters sharing the same domain (regardless of `age_group`) fold into one collapsible domain section.
- R2. Each domain section has a header displaying the domain name and a mastery progress summary (e.g., "加减法 · 3/12 已掌握"). Progress counts aggregate all topics across all clusters within the domain. The header is tappable to toggle expand/collapse.
- R3. The "其他" (Other) synthetic bucket for unmatched topics follows the same collapsible section pattern, with its own header.

**Collapse behavior**

- R4. Default state on first visit to a subject: domains containing at least one topic with mastery level `learning`, `assessing`, `available`, or `review` (mastered with due review) auto-expand. Domains where all topics are `locked` or `mastered` (not due for review) auto-collapse.
- R5. Collapse state persists globally — it survives subject tab switches. If the child manually collapses "分数" in Math, switches to Science, then returns to Math, "分数" remains collapsed.
- R6. When the frontier cluster or a bridge navigation target falls inside a collapsed domain section, that section auto-expands before scrolling. The expand must complete (section visible in DOM) before `scrollIntoView` fires.

**Animation and layout**

- R7. Expand/collapse uses a smooth CSS height transition (no layout jump). The animation respects `@media (prefers-reduced-motion: reduce)`. Implementation must account for the existing `content-visibility: auto` on ClusterTerritory cards — the chosen technique must not conflict with the browser's rendering skip for off-screen content.
- R8. The grouped layout works at 375px viewport width. Domain headers meet the 44×44px minimum touch target.

### Key Decisions

- KTD0. **Data hierarchy: subject > domain > cluster > topic.** Mastery is tracked per topic. Clusters group topics by `subject + domain + age_group`. Domain sections group clusters by `subject + domain`. Progress counts in domain headers aggregate across all topics within all clusters of that domain.
- KTD1. **Domain as grouping key, not domain+age_group.** Multiple clusters for the same domain (e.g., low/mid/high age groups for "加减法") merge into one section. The age_group distinction remains visible inside the section as separate territory cards. Governs R1.
- KTD2. **Global persistence over per-subject reset.** (session-settled: user-directed — chosen over per-subject reset and per-domain tracking: child builds a stable mental model of the map; simpler state shape than per-domain tracking) Governs R5.
- KTD3. **Active-learning signal for auto-expand.** A domain auto-expands when it contains any topic in `learning`, `assessing`, `available`, or review-due `mastered` state. This balances "show me where I'm working" against "hide what I haven't reached." Governs R4.
- KTD4. **No backend changes.** The existing `GET /clusters` endpoint already returns `domain` on every cluster. Grouping is computed entirely in the frontend from data already loaded.

### Acceptance Examples

- AE1. **Covers R1, R2.** A child opens the Math subject tab. Instead of 50+ territory cards scrolling endlessly, they see ~10 collapsible domain sections: "加减法 · 8/24 已掌握", "乘法 · 2/18 已掌握", "分数 · 0/15 已掌握", etc. Each section header shows the domain name and progress count.
- AE2. **Covers R4.** The child has been practicing addition. The "加减法" section is expanded (it contains `learning` topics). The "乘法" section is also expanded (contains `available` topics). The "分数" section is collapsed (all topics `locked`).
- AE3. **Covers R5.** The child collapses "乘法", switches to Science tab, then switches back to Math. "乘法" is still collapsed. "加减法" is still expanded.
- AE4. **Covers R6.** The child taps a bridge badge pointing to a Math cluster in the "分数" domain. The map switches to Math tab, auto-expands "分数", and scrolls to the target cluster.
- AE5. **Covers R7, R8.** Tapping a domain header smoothly animates the section open or closed. At 375px width, the header text and progress count fit on one line without wrapping. The tap area is at least 44×44px.

### Scope Boundaries

**In scope:**
- Collapsible domain section wrapper in ClusterMap.vue
- Domain section header with name, progress summary, expand/collapse chevron
- Smart default collapse/expand logic
- Global collapse state persistence (in-component reactive state)
- CSS expand/collapse animation
- Auto-expand for frontier and bridge targets
- Responsive layout at 375px+

**Deferred for later:**
- Domain-level progress bars or detailed analytics → parent-side DnaGraph2D territory ([#137](https://github.com/vincentruan/numina/issues/137))
- Persistent cross-session collapse state (localStorage) — v1 uses in-memory reactive state; resets on page reload
- Domain search or filter within subject

**Outside this product's identity:**
- Changes to ClusterTerritory or TopicNode visual rendering or internal layout logic (structural wrapping to insert the domain-grouping container is in scope per Product Authority)
- Backend API changes
- Parent-side view changes

---

## Planning Contract

### Key Technical Decisions

- KTD5. **CSS grid template-rows for collapse animation.** Use `display: grid; grid-template-rows: 0fr → 1fr` with an inner `overflow: hidden; min-height: 0` wrapper. This handles unknown content heights without estimation and animates smoothly. The grid wrapper isolates `content-visibility: auto` on child ClusterTerritory cards from the collapse boundary — `min-height: 0` prevents the grid from forcing intrinsic-size computation during collapse. Resolves OQ1. Governs R7.
- KTD6. **Composite key `{subject}:{domain}` for collapse state.** Collapse state is a `Set<string>` keyed by `subject:domain` composite. This preserves global persistence (R5) across subject switches without needing per-subject reset, and avoids collisions if two subjects share a domain name (unlikely but safe). Resolves the state shape for KTD2.
- KTD7. **"其他" bucket follows same collapsible pattern, no cap.** The synthetic "其他" domain section uses the identical DomainSection wrapper. No initial display cap — the bucket rarely accumulates enough clusters to warrant pagination in practice. If it grows large, a follow-up can add progressive disclosure. Resolves OQ2. Governs R3.
- KTD8. **`nextTick`-based expand-before-scroll.** When frontier or bridge navigation targets a collapsed domain, the implementation adds the domain key to the expanded set, then awaits `nextTick()` before calling `scrollIntoView`. This ensures the DOM has rendered the section content before scroll fires. Governs R6.

---

## Implementation Units

### U1. DomainSection collapsible wrapper component

**Goal:** Create a reusable collapsible section component that wraps domain-grouped territory cards with a tappable header and smooth expand/collapse animation.

**Requirements:** R2, R3, R7, R8

**Dependencies:** None

**Files:**
- Create: `frontend/apps/child/src/components/learning/DomainSection.vue`
- Create: `frontend/apps/child/src/components/learning/DomainSection.test.ts`

**Approach:**
1. Props: `domainKey` (string), `domainLabel` (string), `masteredCount` (number), `totalCount` (number), `expanded` (boolean). Emit: `toggle`.
2. Header: flex row with domain label, progress summary (`{masteredCount}/{totalCount} 已掌握`), and a chevron icon (rotates 180° when expanded). Min-height 44px for touch target (R8).
3. Collapse animation: outer wrapper uses `display: grid; grid-template-rows: 0fr` (collapsed) or `1fr` (expanded) with `transition: grid-template-rows 0.3s ease`. Inner wrapper has `overflow: hidden; min-height: 0` to clip content during collapse.
4. `@media (prefers-reduced-motion: reduce)`: set `transition: none` on the grid wrapper.
5. Header is a `<button>` with `type="button"` for a11y. `aria-expanded` reflects the `expanded` prop.
6. The `data-cluster-domain` attribute lives on the outer section element (not on ClusterTerritory) so existing `scrollIntoView` queries can target it.

**Patterns to follow:**
- ClusterTerritory.vue's header layout (flex, Inter font, color tokens)
- Child app Clay design tokens (`--color-surface-card`, `--color-hairline`, `--radius-lg`)
- `aria-expanded` pattern from BalanceHero.vue

**Test scenarios:**
- Renders header with domain label and progress count
- Header tap emits `toggle` event
- Chevron rotates when `expanded` prop changes
- Content is hidden (grid row 0fr) when `expanded` is false
- Content is visible (grid row 1fr) when `expanded` is true
- `aria-expanded` attribute matches `expanded` prop
- `data-cluster-domain` attribute is set on outer element
- Touch target is ≥ 44px height
- Respects `prefers-reduced-motion`: no transition when media query matches

**Verification:** Component mounts, toggles, and animates correctly in isolation. `pnpm -C frontend/apps/child test:run -- DomainSection` passes.

---

### U2. Domain grouping logic in ClusterMap

**Goal:** Refactor ClusterMap to group territories by domain and render them inside DomainSection wrappers.

**Requirements:** R1, R2, R3

**Dependencies:** U1

**Files:**
- Modify: `frontend/apps/child/src/components/learning/ClusterMap.vue`
- Modify: `frontend/apps/child/src/components/learning/ClusterMap.test.ts`

**Approach:**
1. Add a `DomainGroup` interface: `{ domain: string; territories: Territory[]; items: ProgressWithTopic[] }`.
2. Replace the `territories` computed with a `domainGroups` computed that:
   - Reuses the existing territory-matching logic (subject filter, cluster matching, "其他" bucket)
   - Groups resulting territories by `cluster.domain`
   - Each group aggregates all items across its territories for progress counting
3. Template: replace the flat `v-for` over territories with a `v-for` over domainGroups. Each group renders a `<DomainSection>` wrapping its territories.
4. The existing progress bar, celebration, frontier banner, empty state, and PrerequisiteGuidance remain unchanged (they operate on `subjectItems`, not territories).
5. Move `domainLabel()` and add `progressSummary()` helpers into ClusterMap (they're needed for the DomainSection props). ClusterTerritory keeps its own `domainLabel` for the bridge badge labels.
6. The `data-cluster-domain` attribute on ClusterTerritory is preserved for backward compatibility but the DomainSection also carries it on its outer element for scroll targeting.

**Patterns to follow:**
- Existing `territories` computed's matching logic (exact 3-key match → domain-only fallback → "其他")
- i18n key pattern: `t('learning.domains.' + domain)` with fallback to raw domain string

**Test scenarios:**
- Covers AE1. Multiple clusters with same domain render inside one DomainSection
- "其他" bucket renders as its own DomainSection with translated label
- Domain groups aggregate items from multiple age_group clusters
- Progress bar and celebration banner still render correctly above domain groups
- Empty state still shows when no territories exist
- Frontier banner still renders when frontier topic exists

**Verification:** `pnpm -C frontend/apps/child test:run -- ClusterMap` passes. Manual: Math subject shows grouped domains instead of flat list.

---

### U3. Collapse state management and smart defaults

**Goal:** Add reactive collapse state with global persistence and active-learning-based auto-expand defaults.

**Requirements:** R4, R5

**Dependencies:** U2

**Files:**
- Modify: `frontend/apps/child/src/components/learning/ClusterMap.vue`

**Approach:**
1. Add `expandedDomains = reactive(new Set<string>())` — keyed by `{subject}:{domain}` composite.
2. Add `initializeDomainDefaults()` function called after `domainGroups` first computes for a subject:
   - For each domain group, check if any item has mastery level `learning`, `assessing`, `available`, or review-due `mastered`
   - If yes → add to `expandedDomains`
   - If no → do not add (collapsed by default)
   - Only run for domains not already in the set (preserves manual toggles — R5)
3. Watch `selectedSubject` + `domainGroups`: on change, call `initializeDomainDefaults()`. Domains already in the set keep their state; new domains get their default.
4. Add `toggleDomain(domain)` handler: adds/removes from `expandedDomains`.

**Patterns to follow:**
- Mastery status classification already exists in `masteryStatus()` — reuse the logic (extract to a helper if needed)
- Review-due check: `mastery_level === 'mastered' && next_review_at && new Date(next_review_at) <= new Date()`

**Test scenarios:**
- Covers AE2. Domain with `learning` topics auto-expands on first visit
- Domain with only `locked` topics stays collapsed on first visit
- Domain with review-due `mastered` topics auto-expands
- Covers AE3. Manually collapsed domain stays collapsed after subject switch and back
- Manually expanded domain stays expanded after subject switch and back
- New domain appearing after data load gets correct default without disturbing existing state

**Verification:** `pnpm -C frontend/apps/child test:run -- ClusterMap` passes. Manual: verify AE2 and AE3 behaviors.

---

### U4. Frontier and bridge auto-expand

**Goal:** Auto-expand collapsed domain sections when frontier scroll or bridge navigation targets them.

**Requirements:** R6

**Dependencies:** U2, U3

**Files:**
- Modify: `frontend/apps/child/src/components/learning/ClusterMap.vue`

**Approach:**
1. In the existing `watch(territories, ...)` handler (now `watch(domainGroups, ...)` or equivalent):
   - Before querying for the scroll target element, check if the target domain's key is in `expandedDomains`
   - If not, add it and `await nextTick()` to let the DOM render the expanded content
   - Then proceed with `scrollIntoView`
2. For bridge navigation (`onBridgeTap`): after `emit('switchSubject', ...)`, the watcher on `selectedSubject` triggers data reload. The existing watch on territories/domainGroups handles the scroll — just ensure the expand happens there.
3. Move the `data-cluster-domain` scroll target from ClusterTerritory to DomainSection's outer element, or keep it on both (DomainSection for the outer anchor, ClusterTerritory for backward compat within the section).

**Patterns to follow:**
- Existing frontier scroll pattern: `watch(..., { flush: 'post' })` + `scrollIntoView({ behavior: 'smooth', block: 'center' })`
- `scrollTargetDomain` ref for bridge targets

**Test scenarios:**
- Covers AE4. Bridge tap on collapsed domain auto-expands it before scrolling
- Frontier topic in collapsed domain auto-expands that domain
- Auto-expand does not interfere with already-expanded domains (no double-animation)
- After auto-expand, the target territory is scrolled into view

**Verification:** `pnpm -C frontend/apps/child test:run -- ClusterMap` passes. Manual: test AE4 bridge navigation scenario.

---

### U5. i18n keys

**Goal:** Add i18n keys for the domain section progress summary and chevron aria labels.

**Requirements:** R2

**Dependencies:** None (can be done in parallel with U1-U2)

**Files:**
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/child/src/i18n/locales/en-US.ts`

**Approach:**
1. Add keys under `learning.domainSection`:
   - `progress`: `'{mastered}/{total} 已掌握'` (zh-CN), `'{mastered}/{total} mastered'` (en-US)
   - `expandSection`: `'展开'` / `'Expand'` (aria-label)
   - `collapseSection`: `'收起'` / `'Collapse'` (aria-label)
2. The domain label itself uses existing `learning.domains.{domain}` pattern — no new keys needed for domain names.

**Test scenarios:**
- Test expectation: none — i18n keys are data, not behavior. Verify via component tests that reference them.

**Verification:** `pnpm -C frontend/apps/child typecheck` passes. Keys resolve in component tests.

---

## Verification Contract

| Gate | Scope | Command |
|------|-------|---------|
| Unit tests | DomainSection + ClusterMap | `pnpm -C frontend/apps/child test:run -- --reporter=verbose` |
| Typecheck | Child app | `pnpm -C frontend/apps/child typecheck` |
| Lint | Child app | `pnpm -C frontend/apps/child lint` |
| Full workspace | All frontend | `pnpm -r test:run && pnpm -r typecheck` |

## Definition of Done

1. All R-IDs (R1–R8) implemented and covered by test scenarios
2. All AE-IDs (AE1–AE5) pass manual verification
3. Unit tests pass for DomainSection and ClusterMap
4. Typecheck and lint pass for child app
5. No backend changes made
6. No changes to ClusterTerritory or TopicNode visual rendering
7. `@media (prefers-reduced-motion: reduce)` disables collapse animation
8. Touch targets ≥ 44×44px on domain headers
