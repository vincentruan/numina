---
title: Learning OS Playful Exploration Upgrade - Plan
type: feat
date: 2026-10-26
topic: learning-playful-exploration-upgrade
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Upgrade the children's Learning OS from a functional curriculum interface to a playful "knowledge exploration continent" where exploration itself is the reward, hands-on manipulation replaces read-then-quiz, and growth is measured in discovered understanding rather than accumulated points.
- **Authority:** Product Contract in this document. Extends existing Learning OS (cluster map, practice system, mastery tracking, AI tutor). Does not replace underlying knowledge graph or mastery calculation engine.
- **Execution profile:** Full-stack — child frontend pages and components, backend learning API adjustments, AI tutor skill prompt refinement. Reuses existing ClusterMap, GraphMap, practice progress, and mastery systems.
- **Open blockers:** None identified. Existing infrastructure supports the upgrade without new platform dependencies.
- **Tail ownership:** Implementer owns test quality, verification gate, and PR. Code review required before merge.

---

## Product Contract

### Summary

Transform the children's learning experience into a "knowledge exploration continent" — a spatial, discovery-driven world where knowledge territories grow clearer as the child explores, hands-on manipulation challenges replace passive quizzes, and rewards are subtle acknowledgments of growth rather than the primary motivation engine. One reusable interaction pattern (manipulate-observe-reflect) works across subjects. Parents share the same map with a different perspective overlay.

### Problem Frame

The current Learning OS functions correctly but motivation is inverted. XP/Coins/Blind Box rewards dominate the child's attention over knowledge discovery. Practice is read-then-quiz with no hands-on interaction. The result page leads with score percentage and reward counts. Children can complete practice without genuine understanding by gaming the answer pattern.

Meanwhile, the knowledge map (ClusterMap, GraphMap) is a functional navigation tool, not an experience a child would choose for its own sake. The child enters the map to find tasks, not to explore. The parent view is a separate dashboard disconnected from the child's visual world.

Evidence from current code:
- `PracticeResultSummary.vue` displays `scorePercent` prominently, followed by `+XP` and `+coins` reward items
- `PracticeQuestionCard.vue` shows only stem text and answer input — no manipulation, comparison, or observation
- XP and coins are awarded on mastery change (backend `practice.py:368-401`) — the rule is correct, but the frontend presentation amplifies reward salience over understanding
- The Blind Box system uses bonus draws as random rewards, competing with curiosity as a motivation driver

The core problem is not that rewards exist — it is that the experience is structured so rewards are the most salient feedback, drowning out the intrinsic satisfaction of understanding.

### Key Decisions

**D1. Exploration IS the reward.** XP/Coins become background signals. The knowledge continent itself — its growing clarity, expanding territory, and visible connections — is the primary motivational loop. (session-settled: user-directed — chosen over mastery-earned rewards, activity-driven engagement, and portfolio/growth model: the user wants the world itself to be compelling enough that children explore for discovery, not points)

**D2. Exploration Continent metaphor.** Each subject is a territory on a shared knowledge continent. Explored areas are vivid and detailed; unexplored areas are obscured by fog. Cross-domain connections appear as bridges. This extends the existing ClusterMap/ClusterTerritory components. (session-settled: user-directed — chosen over Knowledge Constellation and Knowledge Garden: continent provides the strongest sense of adventure and spatial progression while reusing existing infrastructure)
Governs R1, R2, R3, R8.

**D3. One reusable interaction pattern.** A single "manipulate-observe-reflect" pattern works across subjects — the child operates on visual objects representing concepts, observes the result, and reflects on what changed. The objects and rules are data-driven; the interaction shell is consistent. (session-settled: user-directed — chosen over pattern toolkit by type and custom per knowledge point: scalability through reusability, not variety)
Governs R4, R5.

**D4. Same map, parent perspective.** Parents see the same continent map the child sees, with a different overlay showing mastery depth, learning evidence, and family practice suggestions anchored to specific territories. No separate parent dashboard. (session-settled: user-directed — chosen over independent dashboard and map + dashboard combo: shared visual language creates natural parent-child conversation starters)
Governs R9.

### Actors

- A1. **Child learner** (age 6-12, MVP focus on 8-10): explores the knowledge continent, engages with hands-on challenges, builds understanding through manipulation and reflection.
- A2. **Parent**: views the same continent map with a parent overlay, understands child's learning evidence, receives family practice suggestions.
- A3. **AI tutor** (existing): guides exploration through age-appropriate dialogue, asks leading questions, provides hints. Must not expose technical tool-call information or internal system messages to the child.
- A4. **Knowledge continent** (system): the shared map world that grows clearer as the child explores. Not a character or agent, but the persistent spatial environment both child and parent navigate.

### Requirements

**Core learning experience**

- R1. The knowledge map presents subjects as distinct territories on a shared continent. Each territory contains knowledge point landmarks. Territory visual clarity corresponds to the child's mastery depth in that area. Unexplored territories are partially obscured (fog), not hidden or locked. Covers original R02.
- R2. Territory entry points present knowledge as discoverable challenges with a curiosity-provoking question or scenario, not as curriculum labels with "start practice" buttons. The entry communicates what the child will discover, not what they must complete. Covers original R01, R03.
- R3. Cross-domain connections (bridges) are visible on the map when the child has explored topics in adjacent territories. Bridges reveal themselves naturally through exploration, not through a separate "connections" view. Covers original R02.
- R4. At least one complete hands-on learning challenge exists where the child manipulates visual objects to explore a concept. The P1 sample uses the "fair distribution" math topic (fractions). The child can distribute, compare, and observe whether outcomes are equal. The manipulation directly serves the learning goal — it is not decoration attached to a text explanation. Covers original R04.
- R5. The hands-on interaction pattern is reusable: the same "manipulate-observe-reflect" shell works for different subjects by swapping the objects and rules. The interaction supports tap-select and tap-place as an alternative to drag-and-drop, ensuring accessibility for children with fine motor difficulties. Covers original R04, R11.
- R6. After completing a challenge, feedback emphasizes what the child discovered or understood ("You found that 1/2 and 2/4 cover the same amount"), not the score or rewards earned. Rewards if shown are subtle and secondary. Covers original R08.

**Motivation and growth**

- R7. XP and coins remain in the system but are repositioned as background signals. They do not appear as the primary content on result screens. The child's first visual after completing a challenge is their discovery, not their reward count. Covers original R10.
- R8. The knowledge continent grows visually as the child explores — territories become clearer, paths become more defined, bridges appear. This growth is the primary visible record of learning progress, replacing progress bars and score accumulation as the main growth indicator. Covers original R02, R08.
- R9. The Blind Box random reward system does not appear as a learning motivation mechanism. Blind Box remains accessible as a separate activity but is not linked to practice completion or learning milestones. Covers original R10.

**Trust and navigation**

- R10. All learning navigation entry points lead to valid destinations. No dead-end routes, no buttons that navigate to empty or placeholder pages. Each entry communicates what the child will find before they commit to entering. Covers original R07.
- R11. When a child answers incorrectly during a challenge, the response provides a progressive hint and a chance to try again. The system never shows shaming language, never reveals the correct answer before the child has attempted to reason, and never removes the opportunity to think. Covers original R05.
- R12. The AI tutor dialogue does not expose technical tool-call information, raw API responses, internal logs, or system prompts to the child. AI responses use age-appropriate language and guide thinking through questions rather than providing direct answers. Covers original R06, R12.
- R13. The child's learning interface does not expose family financial data, other members' private information, or any content outside the learning domain. Role boundaries are enforced at both the frontend and API level. Covers original R12.

**Parent side**

- R14. Parents can view the same knowledge continent map the child sees, with an overlay showing: mastery depth per territory, recent exploration activity, and knowledge connections the child has built. Covers original R09.
- R15. The parent map overlay includes family practice suggestions anchored to specific territories the child is exploring. Suggestions are actionable in daily life (e.g., "Your child is exploring fractions — try letting them help measure ingredients while cooking"). Covers original R09.

### How This Work Fits Together

<!-- ce-section: work-relationships -->
This plan owns the children's learning experience upgrade: the knowledge continent map, the hands-on interaction pattern, the motivation rebalancing, and the parent map perspective.

The surrounding areas, as currently understood:
- **P2 — Reusable interaction pattern expansion:** Depends on this plan's P1 sample. Once the "manipulate-observe-reflect" shell is proven for the fractions sample, it can be extended to other knowledge points by configuring objects and rules per topic. Can proceed independently of P3.
- **P3 — Family practice and cross-domain transfer:** Depends on R14/R15 (parent map perspective) being operational. Uses learning evidence generated by the core experience. Can proceed independently of P2.
- **AI tutor skill refinement:** Shares the AI tutor infrastructure. Prompt adjustments for age-appropriate guidance and technical information filtering can proceed in parallel with the map upgrade.

These relationships are the current understanding, not a committed roadmap. A later plan may revise, split, merge, or discard them.

### Key Flows

- F1. **Child enters the knowledge continent**
  - **Trigger:** Child taps the learning entry point from the home screen or tab bar.
  - **Steps:** The continent map loads showing all territories. Explored territories are vivid with visible landmarks. The child's current focus territory has a subtle indicator. Unexplored territories show through fog with hints of what lies within. The child can tap any visible territory to explore its contents.
  - **Covered by:** R1, R2, R8

- F2. **Child engages a hands-on challenge**
  - **Trigger:** Child taps a knowledge point landmark within a territory that offers a hands-on challenge.
  - **Steps:** The challenge presents a scenario with a curiosity-provoking question. The child sees manipulable objects representing the concept. The child taps to select objects and taps locations to place them (or drags, if preferred). The system observes the arrangement and provides real-time visual feedback. When the child's arrangement demonstrates understanding, the challenge completes with a discovery statement.
  - **Covered by:** R4, R5, R6

- F3. **Child answers incorrectly during a challenge**
  - **Trigger:** The child's manipulation does not demonstrate understanding.
  - **Steps:** The system does not show "wrong" in a shaming way. Instead, it highlights the specific aspect that doesn't work and offers a progressive hint. The child can try again without penalty. After two attempts, the system may suggest asking the AI tutor for guidance. The child always retains the option to exit the challenge and return to the map.
  - **Covered by:** R6, R11

- F4. **Parent views the continent map**
  - **Trigger:** Parent opens the learning section from their view.
  - **Steps:** The same continent map renders, but with a parent overlay. Territories show mastery depth (not just explored/unexplored). Recent activity is highlighted. The parent can tap a territory to see: what the child has learned, what they're currently exploring, and family practice suggestions. The parent does not see XP/coin counts as primary information.
  - **Covered by:** R14, R15

### Acceptance Examples

- AE1. **First-time child explores fractions territory**
  - **Covers R1, R2, R4, R5, R6.**
  - **Given:** A child who has never used the learning system enters the continent map.
  - **When:** They see the math territory with fog partially obscuring it, tap it, and find the "fair distribution" challenge about sharing food equally at a picnic.
  - **Then:** They can tap food items and tap plates to distribute them. They observe whether portions look equal. When they achieve equal distribution, the system says something like "You divided it so everyone gets the same amount — that's what 1/2 means!" XP/coins are not shown on the completion screen, or appear only as a subtle secondary line.

- AE2. **Child encounters a prerequisite they haven't explored**
  - **Covers R2, R3, R10.**
  - **Given:** A child tries to access "comparing fractions" but hasn't explored "understanding fractions" yet.
  - **When:** They see the landmark for "comparing fractions" but it shows a clear indicator that it builds on a foundation they haven't explored yet.
  - **Then:** The system explains what they need first in child-friendly language ("To compare portions, you'll want to understand how portions work first"). The child can choose to go explore the prerequisite or choose a different challenge. They are not silently blocked.

- AE3. **Parent checks learning progress**
  - **Covers R14, R15.**
  - **Given:** A parent wants to understand what their child has been learning.
  - **When:** They open the learning map view.
  - **Then:** They see the same continent their child sees, with the math territory showing deeper clarity where the child has explored fractions. They tap the math territory and see: "Understands equal distribution. Currently exploring fraction comparison." Below that: "Try this at home: let your child help divide snacks fairly among family members."

- AE4. **AI tutor session with safety boundary**
  - **Covers R12.**
  - **Given:** A child asks the AI tutor a question during a learning session.
  - **When:** The AI processes the request using internal tools.
  - **Then:** The child sees only age-appropriate guidance text. No tool-call names, API responses, JSON structures, or system prompts are visible. If the AI cannot answer, it says something like "I'm not sure about that — let's think about it together" rather than showing an error or technical failure.

- AE5. **Child exits and returns to a challenge**
  - **Covers R10, R11.**
  - **Given:** A child is mid-challenge and navigates away (back button, home, or session timeout).
  - **When:** They return to the learning map and tap the same knowledge point.
  - **Then:** The challenge resumes from where they left off, with their previous attempts preserved. If the session expired, the system offers to restart the challenge without penalty. No contradictory state appears (e.g., showing "completed" when it wasn't).

### Scope Boundaries

**In scope for this plan (P0 + P1):**
- P0: Verify and fix confirmed experience defects (navigation dead-ends, answer pre-exposure, AI technical information leakage, reward-over-emphasis on result screens).
- P1: One complete vertical learning flow — continent map entry → territory exploration → one hands-on challenge (fair distribution / fractions) → discovery feedback → map growth → parent map view.

**Deferred for later (P2):**
- Extending the hands-on interaction pattern to additional knowledge points beyond the P1 sample.
- Additional subject territories with hands-on challenges.

**Deferred for later (P3):**
- Family practice suggestions expanded beyond map-anchored text to include linked household activities.
- Cross-subject transfer exercises.

**Outside this product's identity:**
- Per-topic custom interactive games — the approach uses one reusable pattern, not bespoke mini-games.
- Independent parent analytics dashboard — the parent view shares the child's map.
- New gamification mechanics (leaderboards, streaks-as-pressure, daily login rewards, loot boxes tied to learning).
- Knowledge graph reconstruction — the existing taxonomy and prerequisite structure are preserved.

### Dependencies / Assumptions

- **Depends on:** Existing ClusterMap/ClusterTerritory components, os-taxonomy knowledge graph (1,590 topics), practice progress API, mastery calculation engine, AI tutor skill infrastructure.
- **Assumes:** The existing Cytoscape.js graph rendering can be styled to represent the "continent" metaphor with territory regions, fog overlays, and bridge connections without requiring a new rendering library.
- **Assumes:** The backend mastery calculation and progress tracking APIs do not need structural changes — only the presentation layer and reward emphasis need adjustment.
- **Assumes:** The "manipulate-observe-reflect" interaction pattern can be implemented as a single Vue component that accepts data-driven configuration (objects, rules, success conditions) per knowledge point.
- **Risk:** If the continent metaphor requires extensive new visual assets (terrain textures, fog effects, territory illustrations) that cannot be produced with CSS/SVG within the existing design system, the visual scope may need to be reduced to styled variations of the current ClusterMap.

### Outstanding Questions

All questions resolved during planning. See Planning Contract KTDs for resolutions.

---

## Planning Contract

> Product Contract unchanged — all R-IDs, Key Decisions, Actors, Flows, AEs, and Scope Boundaries preserved verbatim from the requirements-only artifact.

### Key Technical Decisions

KTD1. **Extend ClusterMap DOM for continent metaphor, not Cytoscape.js.** The continent map uses CSS/SVG enhancements to the existing DOM-based `ClusterMap.vue` and `ClusterTerritory.vue` — territory backgrounds, fog overlays, bridge paths. Cytoscape.js remains available for the graph view but is not the primary continent rendering target. Rationale: ClusterMap already has territory grouping, frontier detection, bridge badges, path overlays, and collapse animations. Adding CSS territory backgrounds and SVG fog layers is faster to iterate, avoids the 137KB Cytoscape bundle as primary rendering, and keeps the existing `useClusterTerritories` composable unchanged.
Governs R1, R3, R8.

KTD2. **Typed Vue component for ManipulateObserveReflect, not a DSL/framework.** The reusable interaction shell is a single `<script setup lang="ts">` component that accepts a `ChallengeConfig` prop — a typed union discriminated by challenge type (`distribute`, `classify`, `compare`, `compose`). Each variant defines its objects, zones, success predicate, and feedback messages. Rationale: P1 needs one pattern; a typed component with variant configs covers all near-term subjects without the overhead of a custom DSL or runtime interpreter.

KTD3. **Client-side fog-of-war computed from mastery data.** Fog opacity is derived on the frontend from existing mastery levels — no new backend field. Each territory's aggregate mastery ratio (mastered count / total count) maps to fog opacity: 0% mastered → 0.7 opacity, 1-49% → 0.4, 50-79% → 0.15, 80%+ → 0 (fully clear). Individual topic nodes within a territory have their own mastery-based visibility. This avoids backend schema changes while providing progressive territory reveal.
Governs R1, R8.

KTD4. **Add manipulate phase to practice flow, don't replace quiz.** The practice flow gains a new `manipulate` phase before the existing `answering` phase: `mode → manipulate → answering → result`. The manipulate phase is optional per topic — topics without a challenge config skip directly to `answering`. The existing quiz phase remains for knowledge verification; the manipulate phase provides hands-on understanding before assessment.
Governs R4, R6.

KTD5. **Parent overlay as a separate component consuming the same API.** The parent view uses a new `ParentContinentOverlay.vue` component in `apps/main/src/components/learning/` that calls the same `getClusters()`/`getBridges()` APIs and the shared `useClusterTerritories` composable. The overlay adds mastery-depth annotations, recent activity highlights, and family practice suggestion cards. The child's `ClusterMap.vue` is not modified for parent mode — the parent app has its own page that renders the same territory structure with parent-specific annotations.
Governs R14, R15.

### Assumptions

- The existing `useClusterTerritories` composable provides sufficient data grouping for the continent territory rendering without modification.
- CSS `opacity` transitions with `prefers-reduced-motion` fallback provide adequate fog-of-war animation without requiring a canvas or WebGL renderer.
- The backend practice API can accept an optional `challenge_config_id` field on session creation without breaking existing clients. If the field is absent, the session follows the traditional quiz flow.
- Family practice suggestions for P1 are static text keyed to topic domains (e.g., "fractions" → "try measuring ingredients together"), not AI-generated. P3 may introduce dynamic generation.

### Sequencing

Units are grouped into two phases:

**Phase A — Trust fixes and reward rebalancing (P0):** U1, U2. These fix confirmed experience defects and can land independently of the continent work.

**Phase B — Continent experience (P1):** U3 → U4 → U5 → U6 → U7. U3 (continent visual foundation) is the prerequisite for U4 (fog), U5 (manipulation component), and U6 (P1 content). U7 (parent overlay) depends on U3 being deployed. U5 and U6 can proceed in parallel once U3 is ready.

---

## Implementation Units

### U1. Hide tool-call details from child AI session

**Goal:** Remove the `<details>` blocks that expose raw tool-call names, JSON arguments, and tool outputs on `LearningSessionPage.vue`. Covers R12, AE4.

**Requirements:** R12

**Dependencies:** None

**Files:**
- `frontend/apps/child/src/pages/learning/LearningSessionPage.vue` — remove `<details v-if="msg.toolCall">` and `<details v-if="msg.toolResult">` blocks (lines 50-64)
- `frontend/apps/child/src/pages/learning/LearningSessionPage.vue` — remove associated CSS for `.tool-details` / `.tool-details__summary` / `.tool-details__content`
- `frontend/apps/child/src/pages/learning/__tests__/LearningSessionPage.test.ts` — add test verifying tool-call elements are not rendered

**Approach:**
1. Remove the two `<details>` blocks that render `msg.toolCall` and `msg.toolResult`
2. Remove the associated CSS rules for tool display
3. Keep the data fetching intact — the API still returns tool-call data; the child UI simply doesn't render it
4. Add a test that mounts the component with a message containing `toolCall` and `toolResult` fields, then asserts no `<details>` elements exist in the rendered output

**Test scenarios:**
- Mount with a message containing `toolCall` data → no tool-call elements rendered
- Mount with a message containing `toolResult` data → no tool-result elements rendered
- Mount with normal assistant text message → text renders normally
- Mount with mixed messages (assistant text + tool calls + assistant text) → only text messages visible

**Verification:** `pnpm --filter @numina/child test:run` passes. Grep for `tool-details` class returns no matches in `LearningSessionPage.vue`.

---

### U2. Discovery-first practice result summary

**Goal:** Redesign `PracticeResultSummary.vue` to lead with what the child discovered/learned, not score percentage and reward counts. Covers R6, R7.

**Requirements:** R6, R7

**Dependencies:** None

**Files:**
- `frontend/apps/child/src/components/learning/PracticeResultSummary.vue` — restructure layout: discovery statement first, score/rewards secondary
- `frontend/apps/child/src/components/learning/__tests__/PracticeResultSummary.test.ts` — update/add tests for new layout order
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — add `learning.result.discovery` keys
- `frontend/apps/child/src/i18n/locales/en-US.ts` — add English translations

**Approach:**
1. Add a new "discovery statement" section at the top of the result hero, computed from the topic label and mastery change: e.g., "你发现了公平分配的秘诀！" / "You discovered the secret of fair sharing!"
2. Move the score percentage (`result-emoji` + `result-score`) below the discovery statement, with reduced visual weight (smaller font, muted color)
3. Move the `result-rewards` section (XP, coins, mastery) below the score, with minimal styling — small text, no large emoji icons
4. The mastery change badge (`mastery_changed`) stays but is integrated into the discovery statement rather than shown as a separate reward item
5. Add i18n keys for discovery statement templates per topic domain

**Test scenarios:**
- Result with mastery_changed=true → discovery statement shown prominently, score below in muted style
- Result with mastery_changed=false → encouragement statement shown, score visible but not dominant
- Reward section renders with reduced visual weight (small text, no oversized emoji)
- Covers AE1: completion of fair distribution challenge shows discovery-first feedback

**Verification:** `pnpm --filter @numina/child test:run` passes. Visual check: discovery text is the first element in the DOM order, score is secondary.

---

### U3. Continent map visual foundation — territory backgrounds and Clay tokens

**Goal:** Add territory-level visual styling to the existing `ClusterMap` / `ClusterTerritory` components so each subject domain renders as a distinct "territory" on the continent with Clay-themed backgrounds, rounded terrain shapes, and subject-specific accent colors. Covers R1, R2, R8.

**Requirements:** R1, R2, R3, R8

**Dependencies:** None

**Files:**
- `frontend/apps/child/src/assets/clay.css` — add continent territory tokens (`--continent-terrain-math`, `--continent-terrain-science`, etc.) for both `:root` and `[data-theme="dark"]`
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — add territory background wrapper with continent container styling
- `frontend/apps/child/src/components/learning/ClusterTerritory.vue` — add terrain background, territory name styling, subject accent border
- `frontend/apps/child/src/components/learning/__tests__/ClusterTerritory.test.ts` — add tests for territory visual classes
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — add `learning.continent.territory.*` keys
- `frontend/apps/child/src/i18n/locales/en-US.ts` — add English translations

**Approach:**
1. Add Clay CSS tokens for territory backgrounds — one soft accent color per subject domain (math=green, science=blue, language=amber, etc.), defined as `rgba` alpha overlays over `var(--color-surface-card)` so they work in both light and dark mode
2. Wrap each `ClusterTerritory` in a terrain container with `border-radius: 20px`, a subtle terrain-texture background using the subject-specific token, and a 2px accent border at the top
3. Add a continent container around all territories in `ClusterMap.vue` with warm canvas background and slight padding, giving the feeling of a shared landmass
4. Territory names rendered with subject-specific accent color, slightly larger font, and a small subject emoji/icon as a "territory marker"
5. Use CSS modifier classes (`.territory--math`, `.territory--science`) for subject-specific styling — no inline styles (per dark-mode specificity learning)
6. Respect `prefers-reduced-motion` for any transitions

**Patterns to follow:** `ClusterMap.vue` existing domain grouping, Clay token system in `clay.css`, `DomainSection.vue` collapse animation pattern, dark mode CSS class approach from `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md`.

**Test scenarios:**
- Each subject domain renders with its territory modifier class (`.territory--math`, etc.)
- Territory background uses CSS variable, not inline style
- Dark mode: territory tokens resolve correctly under `[data-theme="dark"]`
- Continent container wraps all territories with canvas background
- `prefers-reduced-motion`: no transition animations on territory expand/collapse

**Verification:** `pnpm --filter @numina/child test:run` passes. Visual check in browser: territories are visually distinct regions on a shared continent canvas.

---

### U4. Fog-of-war state overlay for continent territories

**Goal:** Add a fog-of-war visual layer to the continent map where territory clarity is driven by the child's mastery depth. Unexplored territories are partially obscured; explored territories are vivid and clear. Covers R1, R8.

**Requirements:** R1, R8

**Dependencies:** U3

**Files:**
- `frontend/apps/child/src/components/learning/ContinentFog.vue` — new component: SVG/CSS fog overlay per territory
- `frontend/apps/child/src/components/learning/ClusterTerritory.vue` — integrate fog overlay, compute fog opacity from mastery ratio
- `frontend/apps/child/src/components/learning/__tests__/ContinentFog.test.ts` — new test file
- `frontend/apps/child/src/assets/clay.css` — add fog tokens (`--continent-fog-color`, `--continent-fog-transition`)

**Approach:**
1. Create `ContinentFog.vue` — a component that accepts `masteryRatio: number` (0-1) and renders a semi-transparent overlay with `pointer-events: none`
2. Fog opacity mapping per KTD3: 0% → 0.7, 1-49% → 0.4, 50-79% → 0.15, 80%+ → 0
3. Use CSS `transition: opacity 0.6s ease` with `prefers-reduced-motion: reduce` fallback to `transition: none`
4. Fog color uses `var(--continent-fog-color)` — a warm neutral that works in both light (`#e8e0d0`) and dark (`#1a2a2a`) modes
5. Within each territory, individual topic nodes retain their existing mastery-based coloring — the fog is a territory-level overlay that dims everything beneath it
6. The `frontierTopic` (detected by existing `ClusterMap` logic) has a subtle pulse animation visible through the fog, hinting at what's next

**Test scenarios:**
- masteryRatio=0 → fog opacity is 0.7
- masteryRatio=0.5 → fog opacity is 0.15
- masteryRatio=1.0 → fog opacity is 0 (fully clear)
- `prefers-reduced-motion` → no transition on fog opacity change
- Fog overlay has `pointer-events: none` — territory nodes remain tappable through fog
- Frontier topic pulse visible through fog layer

**Verification:** `pnpm --filter @numina/child test:run` passes. Visual check: unexplored territories are dimmed, explored territories are vivid, frontier has visible pulse through fog.

---

### U5. ManipulateObserveReflect reusable challenge component

**Goal:** Create a reusable Vue component that renders hands-on manipulation challenges. The component accepts a data-driven config, renders manipulable objects, tracks the child's arrangement, and evaluates success. Supports tap-select/tap-place for accessibility. Covers R4, R5.

**Requirements:** R4, R5

**Dependencies:** U3

**Files:**
- `frontend/apps/child/src/components/learning/ManipulateObserveReflect.vue` — new component: the reusable interaction shell
- `frontend/apps/child/src/types/learning-challenge.ts` — new file: `ChallengeConfig` type definitions (discriminated union by type)
- `frontend/apps/child/src/components/learning/__tests__/ManipulateObserveReflect.test.ts` — new test file
- `frontend/apps/child/src/assets/clay.css` — add challenge tokens (`--challenge-object-bg`, `--challenge-zone-bg`, `--challenge-zone-active`)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — add `learning.challenge.*` keys
- `frontend/apps/child/src/i18n/locales/en-US.ts` — add English translations

**Approach:**
1. Define `ChallengeConfig` types in `learning-challenge.ts`:
   - Base: `scenario: string`, `objects: ChallengeObject[]`, `zones: ChallengeZone[]`, `evaluate: string` (a rule key like `equal_distribution`), `discoveryMessage: string`
   - Variant `DistributeChallenge`: objects are items to distribute, zones are targets (e.g., plates)
   - Variant `ClassifyChallenge`: objects are items to sort, zones are categories
   - Variant `CompareChallenge`: objects are quantities/shapes to compare, zones are comparison slots
2. `ManipulateObserveReflect.vue` renders:
   - Scenario text at top (the curiosity-provoking question)
   - Object pool: tappable items with label + optional icon, arranged horizontally
   - Zone area: tappable drop targets where objects can be placed
   - Interaction model: tap an object to select it (highlighted), then tap a zone to place it there. Tap a placed object to return it to the pool. No drag-and-drop required (accessibility).
   - Feedback bar at bottom: shows current state ("2 items on plate A, 1 on plate B") and a "Check" button
3. On "Check": run the evaluate function against the current arrangement. If correct → show `discoveryMessage` with celebration. If not → show a progressive hint (highlight the imbalance), allow retry.
4. All visual states use CSS classes with Clay tokens. 44px minimum touch targets for all interactive elements. `prefers-reduced-motion` respected.

**Patterns to follow:** `PracticeAnswerInput.vue` input rendering pattern, Clay CSS token system, existing 44px touch target enforcement in child components, i18n via `t()`.

**Test scenarios:**
- Renders scenario text and object pool from config
- Tap object → object enters selected state
- Tap zone with selected object → object moves to zone
- Tap placed object → object returns to pool
- Correct arrangement + check → discovery message shown
- Incorrect arrangement + check → hint shown, retry allowed
- All interactive elements have min 44px touch target
- `prefers-reduced-motion` → no animation on object placement
- Empty config → renders nothing (no crash)

**Verification:** `pnpm --filter @numina/child test:run` passes. Manual check: can complete a distribute challenge using only taps (no drag).

---

### U6. Fair distribution challenge content — fractions P1 sample

**Goal:** Wire the `ManipulateObserveReflect` component to the practice flow with a concrete "fair distribution" challenge for the fractions topic. This is the P1 vertical slice: a child can enter a territory, engage a hands-on manipulation, and receive discovery-first feedback. Covers R4, R6, AE1.

**Requirements:** R4, R5, R6

**Dependencies:** U3, U4, U5

**Files:**
- `frontend/apps/child/src/data/learning-challenges/fair-distribution.ts` — new file: challenge config for the fractions fair-distribution scenario
- `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue` — add `manipulate` phase to the state machine (between `mode` and `answering`)
- `frontend/apps/child/src/api/practice.ts` — add optional `challenge_config_id` to session creation
- `frontend/apps/child/src/api/learning.ts` — add endpoint to fetch challenge configs for a topic (or embed in topic response)
- `server/apps/backend/app/routers/learning.py` — add endpoint or extend topic response with challenge config reference
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` — add challenge scenario text and discovery messages
- `frontend/apps/child/src/i18n/locales/en-US.ts` — add English translations
- `frontend/apps/child/src/pages/learning/__tests__/PracticeSessionPage.test.ts` — add tests for manipulate phase

**Approach:**
1. Create `fair-distribution.ts` with a `DistributeChallenge` config:
   - Scenario: "野餐时，4个朋友想公平分享8块饼干。怎样分才能让每个人得到相同的一份？"
   - Objects: 8 cookie items (tap to select, tap plate to place)
   - Zones: 4 plate targets (labeled with friend names)
   - Evaluate: `equal_distribution` — each zone must have exactly 2 items
   - Discovery: "你让每个人都分到了相同数量的饼干！这就是公平分配——每人得到 8÷4=2 块。"
2. Extend `PracticeSessionPage.vue` state machine: add `manipulate` phase. When a topic has a challenge config, show `ManipulateObserveReflect` in the manipulate phase before transitioning to the existing `answering` phase.
3. Backend: add a simple `GET /child/learning/challenges/{topicId}` endpoint returning the challenge config ID and type for the topic. For P1, this can be a static lookup.
4. The manipulate phase completion records a `challenge_completed` event in the practice session, which the backend uses for progress tracking (same mastery update path).

**Test scenarios:**
- Topic with challenge config → manipulate phase shown before answering
- Topic without challenge config → skips manipulate, goes directly to answering (backward compatible)
- Fair distribution: equal placement → discovery message, proceed to answering
- Fair distribution: unequal placement → hint about imbalance, retry
- Covers AE1: first-time child enters fractions territory, completes fair distribution challenge
- Challenge completion followed by quiz question about the same concept

**Verification:** `pnpm --filter @numina/child test:run` passes. Manual check: complete the full flow — enter fractions territory → manipulate cookies → see discovery → answer quiz → see discovery-first result.

---

### U7. Parent continent map overlay with mastery depth and practice suggestions

**Goal:** Add a parent-facing overlay to the continent map showing mastery depth per territory, recent activity, and family practice suggestions. Covers R14, R15, AE3.

**Requirements:** R14, R15

**Dependencies:** U3

**Files:**
- `frontend/apps/main/src/components/learning/ParentContinentOverlay.vue` — new component
- `frontend/apps/main/src/pages/baby/learning/ParentLearningMapPage.vue` — new or existing page integrating the overlay
- `frontend/apps/main/src/api/learning.ts` — add family practice suggestion fetch (or extend existing mastery response)
- `server/apps/backend/app/routers/learning.py` — add `GET /family/children/{child_id}/practice-suggestions` endpoint returning domain-keyed suggestions
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — add parent overlay i18n keys
- `frontend/apps/main/src/i18n/locales/en-US.ts` — add English translations
- `frontend/apps/main/src/components/learning/__tests__/ParentContinentOverlay.test.ts` — new test file

**Approach:**
1. `ParentContinentOverlay.vue` accepts the same territory data as the child's `ClusterMap` (via `useClusterTerritories`) and adds:
   - Mastery depth annotation per territory: "已掌握 3/8 知识点" with a small progress bar
   - Recent activity badge: "今天探索了分数" for territories with activity in the last 24h
   - Discovery summary: brief statement of what the child has understood
2. Family practice suggestions: a card below the territory showing an actionable suggestion keyed to the child's current learning domain. P1 uses static text per domain (fractions → "让孩子帮忙量食材", science → "一起观察花园里的植物"). Backend endpoint returns the suggestion text based on the child's frontier topics.
3. The parent overlay uses the same Clay CSS territory tokens as the child view, ensuring visual consistency. Parent-specific annotations use a distinct accent (e.g., a subtle border or badge color) to differentiate the parent's analytical view from the child's exploratory view.
4. XP/coin counts are NOT shown in the parent overlay — parent sees mastery depth and discovery evidence.

**Test scenarios:**
- Territory with mastered items → shows mastery count and depth indicator
- Territory with recent activity → shows "今天探索了" badge
- Practice suggestion card renders for child's current frontier domain
- No XP/coin counts visible in parent overlay
- Empty state: child has no learning progress → overlay shows "还没有开始探索" encouragement
- Covers AE3: parent opens map, sees fractions territory with mastery depth and practice suggestion

**Verification:** `pnpm --filter @numina/main test:run` passes. Backend: `pytest server/tests/backend/ -k practice_suggestions` passes.

---

## Verification Contract

| Gate | Command | Applies to |
|------|---------|-----------|
| Child unit tests | `pnpm --filter @numina/child test:run` | U1-U6 |
| Child typecheck | `pnpm --filter @numina/child typecheck` | U1-U6 |
| Child lint | `pnpm --filter @numina/child lint` | U1-U6 |
| Main unit tests | `pnpm --filter @numina/main test:run` | U7 |
| Main typecheck | `pnpm --filter @numina/main typecheck` | U7 |
| Backend tests | `cd server && uv run pytest tests/backend/ -x -q` | U6 (endpoint), U7 (endpoint) |
| Backend typecheck | `cd server && uv run mypy apps/backend/app` | U6, U7 |

All gates must pass before the plan is considered implemented. Run child/main/frontend gates from repo root; run backend gates from `server/`.

---

## Definition of Done

**Global:**
- All 7 implementation units pass their verification commands.
- The P1 vertical slice is end-to-end navigable: child enters continent map → sees territories with fog → enters math territory → completes fair distribution hands-on challenge → receives discovery-first feedback → territory fog clears → parent can view the same map with mastery overlay and practice suggestions.
- No regressions in existing practice quiz flow (topics without challenge configs work exactly as before).
- Tool-call details are no longer visible to children in AI learning sessions.
- All new user-facing strings are i18n-ized (zh-CN + en-US).
- All new interactive elements have ≥44px touch targets.
- All new animations respect `prefers-reduced-motion`.
- No inline styles for themed colors (CSS classes only, per dark-mode specificity learning).
- All Snowflake ID fields typed as `string` in TypeScript.
- No new dependencies added to the bundle.

**Per-unit:**
- U1: `<details>` blocks removed from child AI session, test covers tool-call hiding.
- U2: Discovery statement is first DOM element in result summary, score/rewards secondary.
- U3: Territory modifier classes render per subject, Clay tokens defined for light+dark.
- U4: Fog opacity computed from mastery ratio, `pointer-events: none` confirmed.
- U5: ManipulateObserveReflect component renders from config, tap-select/place works, no drag required.
- U6: Fair distribution challenge playable end-to-end, manipulate phase integrated into practice flow.
- U7: Parent overlay shows mastery depth and practice suggestions, no XP/coin display.

**Cleanup:**
- No experimental/dead-end code remains in the diff.
- No `TODO` or `FIXME` comments without linked tracking.
- Unused imports/variables removed from all changed files.

---

### Sources / Research

- Existing product brainstorm: `docs/plans/2026-09-28-001-learning-os-product-brainstorm.md` — core Learning OS concepts (knowledge world, exploration loop, XP/Coins as scaffolding).
- Cluster knowledge map plan: `docs/plans/2026-10-20-001-feat-duolingo-cluster-knowledge-map-plan.md` — implemented the ClusterMap/ClusterTerritory components this plan extends.
- Path animation plan: `docs/plans/2026-10-22-001-feat-learning-path-animation-plan.md` — implemented PathOverlay for recommendation trails.
- Parent cluster map view: commit `e2d162c7` — parent perspective on the cluster map.
- Cross-subject bridge inference: commits `4f2fdeaa`, `e2d162c7` — bridge detection via keyword overlap.
- Child app constraints: `frontend/apps/child/AGENTS.md` — Clay visual system, Vant 4 rules, route structure.
- Practice flow: `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue` — 3-phase state machine (mode → answering → result).
- Backend reward logic: `server/apps/backend/app/routers/practice.py` — XP/coin on mastery change only.
- Gamified child system: `docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md` — batch endpoints, schema organization.
- Graph library evaluation: `docs/solutions/best-practices/graph-library-evaluation-antv-g6-vs-cytoscape-2026-10-22.md` — Cytoscape.js selected over AntV G6.
- Dark mode specificity: `docs/solutions/ui-bugs/dark-mode-inline-style-specificity-2026-05-30.md` — CSS classes over inline styles.
- Grounding dossier: `/tmp/compound-engineering-501/ce-brainstorm/learning-v2-upgrade/grounding.md` — verified code quotes with file:line pointers.
- Claim verification: `/tmp/compound-engineering-501/ce-brainstorm/learning-v2-upgrade/claim-verification.md` — all 6 claims confirmed.
