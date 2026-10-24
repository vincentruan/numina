---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
title: "Duolingo-Style Cluster Knowledge Map - Plan"
date: 2026-10-20
focus: "Replace child app's flat TopicGrid with a scrollable cluster-based knowledge map using existing os-taxonomy clusters"
---

<!-- Product Contract preservation: unchanged. All R-IDs, KTD-IDs, AE-IDs carried forward from requirements-only version. -->

## Goal Capsule

**Objective:** Replace the child app's flat TopicGrid with a scrollable, cluster-based knowledge map that visualizes the 1,590-topic os-taxonomy as named learning territories. Children explore subject tabs → cluster areas → individual topic nodes, each colored by 5-state mastery. Context-dependent taps route to practice, topic detail, or prerequisite guidance. Cross-subject bridge edges connect related clusters across disciplines.

**Product authority:** Child app learning map page (`frontend/apps/child/src/pages/learning/LearningMapPage.vue`). Parent-side views (DnaGraph2D.vue) are out of scope.

**Open blockers:** None. Backend APIs, taxonomy data, and mastery state machine are complete. This is a frontend visualization and UX improvement.

## Product Contract

### Summary

A hybrid CSS/SVG scrollable knowledge map for the child app. Each of the 183 existing os-taxonomy clusters becomes a named territory containing topic nodes colored by mastery state. Native mobile scroll (no graph library). Subject tabs filter by subject. Cross-subject bridges visualized as connectors between clusters. Context-dependent taps: mastered→detail, available→practice, locked→prerequisites. Soft lock — all nodes visible and tappable, no hard gates on exploration.

### Problem Frame

Children currently see a flat list of topics grouped by domain within each subject tab (TopicGrid.vue). They cannot see relationships between topics, understand what to learn next, or visualize their progress across the knowledge graph. The parent side has an interactive graph (DnaGraph2D.vue) but the primary learner — the child — gets only a list. The 3,221 prerequisite edges stored in the database are invisible to the child. Two independent research reports independently identified this as the #1 gap: the system's biggest missing piece is not a feature but a visualization.

### Requirements

- R1. The map replaces TopicGrid as the primary learning navigation surface in LearningMapPage.vue. Subject tabs remain the top-level filter (Mathematics, Science, English, Chinese, etc.).
- R2. Each of the 183 existing os-taxonomy clusters renders as a named territory (area) on the map. The cluster name (from clusters.json) is displayed as the area label.
- R3. Topic nodes within a cluster are rendered as circles colored by the child's mastery state: mastered (gold + glow), learning (blue + pulse animation), available (purple), locked (gray, reduced opacity), review (orange).
- R4. Nodes are tappable with context-dependent behavior: mastered nodes navigate to topic detail; available/learning nodes start practice directly; locked nodes show a prerequisite guidance view (what needs to be mastered first).
- R5. All nodes are visible and tappable regardless of lock state (soft lock). Locked nodes do not block exploration — they inform. The existing backend practice gate still enforces hard prerequisites when a child attempts to start practice on a locked topic.
- R6. Cross-subject bridge edges connect clusters across subject boundaries when prerequisite relationships span subjects (e.g., Math "Measurement" → Science "Units & Conversion"). Bridges are shown as visual connectors (dashed lines or arrow indicators) between cluster areas.
- R7. Bridge indicators on a cluster show which other subjects it connects to ("Connects to: 科学, 生活技能"). Tapping a bridge indicator navigates to the target subject tab and scrolls to the connected cluster.
- R8. A progress indicator shows the child's overall mastery progress within the current subject (e.g., "12/47 topics mastered" with a progress bar).
- R9. The current learning frontier (the child's next recommended topic) is visually highlighted — either by auto-scrolling to the cluster containing it or by a "You are here" marker on the map.
- R10. The map loads progressively: the selected subject's clusters and topics load first; other subjects' data loads lazily as the child switches tabs.
- R11. The map is responsive and usable on mobile screens (375px width). Native vertical scroll is the primary navigation mechanism within a subject. No pinch-to-zoom or canvas panning required.
- R12. The existing `/child/learning/map` API endpoint and batch topic detail fetching remain the primary data sources. Two new lightweight endpoints (`GET /clusters`, `GET /bridges`) are added to serve cluster metadata and cross-subject bridge computation.

### Key Decisions

- KTD1. **Hybrid CSS/SVG scroll map over graph library.** A dedicated graph library (AntV G6, Cytoscape.js) was considered and rejected for v1. The cluster map at 183 areas with ~8 topics each is a scrolling problem, not a graph interaction problem. Native scroll gives better mobile performance, zero new dependencies, and predictable layout. A graph library can be adopted later if the map evolves toward free-form exploration.
- KTD2. **Existing os-taxonomy clusters as territories.** The 183 clusters from `clusters.json` are used directly as map areas. No manual curation, no new clustering algorithm. This keeps the map aligned with the taxonomy data and avoids a parallel maintenance burden.
- KTD3. **Soft lock over hard lock.** All nodes are visible and tappable. Locked nodes inform (show prerequisites needed) rather than block. This protects curiosity and lets children explore the knowledge space freely. The backend practice gate still enforces prerequisites when actual practice starts.
- KTD4. **Context-dependent tap actions.** Rather than a uniform tap action (all navigate to detail), taps route based on mastery state. This reduces friction for ready-to-learn topics (one tap → practice) while keeping locked topics informative.
- KTD5. **Separate child and parent views.** The child's cluster map and the parent's DnaGraph2D spiral graph serve different needs. The child map optimizes for simplicity, touch, and progression. The parent graph optimizes for detailed mastery analysis. They share data but not components.
- KTD6. **Cross-subject bridges derived from existing dependency data.** Bridge edges come from `learning_dependencies` where the source and target topics belong to different subjects. If few such edges exist in the current data, bridges may need to be supplemented via curriculum standards alignment or LLM inference as a follow-up.

### Acceptance Examples

- AE1. A child opens the learning map. They see subject tabs at the top. Tapping "数学" shows ~50 cluster areas (加减法领地, 乘法关卡, 分数水域, etc.) arranged vertically. Each area has a name label and 3-10 topic nodes inside. Nodes are colored by mastery: gold for mastered, blue (pulsing) for the current learning topic, gray for locked.
- AE2. The child taps a blue (learning) node "50以内加法". Practice starts immediately — no intermediate screen. The child completes the practice, and on returning to the map, the node turns gold.
- AE3. The child taps a gray (locked) node "100以内加法". A view shows: "To unlock this, you need to master: 50以内加法 (not yet mastered), 50以内减法 (not yet mastered)." The child can tap the prerequisites to navigate to them.
- AE4. A cluster in the Math tab shows a bridge indicator: "Connects to: 科学 → 物质世界". Tapping it switches to the Science tab and scrolls to the "物质世界" cluster.
- AE5. A child with no progress sees all nodes as gray (locked) except the first available cluster's topics (purple/available). A "You are here" marker points to the first recommended topic.

### Scope Boundaries

**In scope:**
- Child app cluster map with subject tabs, cluster territories, mastery-colored nodes
- Context-dependent tap actions (detail / practice / prerequisites)
- Cross-subject bridge visualization and navigation
- Progressive loading (subject-first, lazy-load others)
- Current frontier / "You are here" indicator
- Responsive mobile layout (375px+)

**Deferred for later:**
- Parent-side view changes (DnaGraph2D.vue stays as-is) → [#137](https://github.com/vincentruan/numina/issues/137)
- Graph library upgrade (AntV G6 / Cytoscape.js) — viable as v2 if free-form exploration is needed → [#135](https://github.com/vincentruan/numina/issues/135)
- Animated path-finding or "recommended route" highlighting → [#134](https://github.com/vincentruan/numina/issues/134)
- Domain-level grouping within subject tabs (call-out: may be needed if cluster density is too high) → [#133](https://github.com/vincentruan/numina/issues/133)
- Bridge edge curation or LLM inference (v1 uses only existing dependency data) → [#136](https://github.com/vincentruan/numina/issues/136)

**Outside this product's identity:**
- Free-form graph exploration (pinch-to-zoom, drag, force-directed layout)
- 3D visualization or gamified world-map with avatars
- Teacher/instructor view (this product serves families, not classrooms)

### Outstanding Questions

- OQ1. **Cluster density threshold:** Math has ~503 topics across potentially 50+ clusters. If a subject has more than ~30 clusters, should we add domain-level grouping (collapsible domain sections within the subject tab)? This depends on the actual cluster distribution after data analysis. → [#133](https://github.com/vincentruan/numina/issues/133)
- OQ2. **Cross-subject edge distribution:** Verification confirmed 161 cross-subject edges exist (see Risk 2), but they may cluster in a few domains. If a subject has only 1-2 bridges, the feature is underwhelming. Should bridge visualization be supplemented with curriculum-standards-based inference? → [#136](https://github.com/vincentruan/numina/issues/136)
- OQ3. **Auto-scroll behavior refinement:** U5 implements one-time auto-scroll on initial load. Should the map also re-scroll when the child returns from a practice session and the frontier topic changes? → [#139](https://github.com/vincentruan/numina/issues/139)

---

## Planning Contract

### High-Level Technical Design

The data flow follows a three-layer architecture: backend cluster API → frontend cluster-topic matching → CSS/SVG rendering.

**Data flow:**

```
┌─────────────────────────────────────────────────────────┐
│ Backend                                                  │
│                                                          │
│  GET /clusters?subject=Math ──────────────────────────►  │
│  Returns: LearningCluster[] (183 rows, subject/domain/   │
│           summary/age_range) from clusters.json seed     │
│                                                          │
│  GET /child/learning/map ─────────────────────────────►  │
│  Returns: ProgressResponse[] (existing, unchanged)       │
│                                                          │
│  GET /child/learning/topics?subject= ─────────────────►  │
│  Returns: TopicResponse[] (existing, filter by subject)  │
│                                                          │
│  GET /child/learning/bridges?subject= ────────────────►  │
│  Returns: BridgeResponse[] (new: cross-subject edges     │
│           computed from learning_dependencies)           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ Frontend: ClusterMap.vue                                 │
│                                                          │
│  1. Load clusters + topics + progress + bridges          │
│  2. Match topics → clusters (by subject + domain + age_group,        │
│     fallback to subject + domain if no 3-key match)                  │
│  3. Compute mastery state per topic (from progress)      │
│  4. Render: SubjectTabs → ClusterTerritory[] → Nodes     │
│  5. Context-dependent tap handlers per mastery state     │
│  6. Bridge badges on clusters with cross-subject edges   │
│  7. Progress bar + "You are here" marker                 │
└─────────────────────────────────────────────────────────┘
```

**Topic-to-cluster matching:** Topics don't have a direct `cluster_id` foreign key. Clusters group topics by `subject + domain + age_group`. Both `LearningTopic` and `LearningCluster` models have an `age_group` string field (values: 'low', 'mid', 'high'). The frontend joins topics to clusters where `topic.subject === cluster.subject && topic.domain === cluster.domain && topic.age_group === cluster.age_group`. If no exact 3-key match exists, fall back to `subject + domain` (ignoring age_group). Topics with NULL domain or no matching cluster at either key level are collected into a synthetic "其他" (Other) territory at the bottom of the subject. If "其他" accumulates more than 12 topics, show the first 12 with a "展开查看更多 (N)" expand button.

**Cross-subject bridge computation:** For each `learning_dependencies` edge, look up the subject of both `topic_id` and `prerequisite_id`. When subjects differ, that edge is a cross-subject bridge. Map each bridge endpoint to its cluster via subject+domain matching. Return unique `(from_cluster_domain, from_subject, to_cluster_domain, to_subject)` tuples.

**Loading & error states:** R10 mandates progressive loading, so each async data fetch needs a visual treatment:
- **Initial page load:** `van-skeleton` rows (3-5 placeholder lines) fill the cluster area while clusters + topics load. Subject tabs remain interactive.
- **Subject tab switching:** Existing clusters fade out (opacity 0.5); skeleton rows replace the cluster list until new subject data arrives.
- **Bridge badges:** Fade in when `getBridges()` resolves; no loading indicator (non-critical, graceful absence is acceptable).
- **Prerequisite guidance sheet (U3):** `van-loading` spinner centered in the popup while `getTopicGraph()` resolves.
- **Error fallback:** If cluster/topic load fails, show `EmptyState` component (from `@numina/assets/empty-states`) with `t('learning.cluster.loadError')` description and a retry button. If progress data (`/child/learning/map`) fails, render clusters with all nodes shown as `available` (purple, default unlocked state) instead of mastery-colored — mastery coloring requires progress data. If `getBridges()` fails, silently skip badges. If `getTopicGraph()` fails, show error message in the popup with a close button.
- **Pull-to-refresh:** ClusterMap remains inside the existing `van-pull-refresh` wrapper in LearningMapPage.vue. `onRefresh` reloads clusters + topics + bridges for the current subject.
- **Child profile switch:** When the active child changes (watch on babyStore.selectedChildId or page re-mount), reload all data: clusters + topics + progress + bridges. Mastery colors, progress bar, frontier marker, and bridge badges all depend on the child's data.

### Implementation Units

### U1. Backend: Cluster API and Bridge Endpoint

**Goal:** Add cluster metadata serving and cross-subject bridge computation to the backend.

**Requirements:** R2, R6, R7, R10, R12

**Dependencies:** None (first unit)

**Files:**
- `server/apps/backend/app/schemas/learning.py` — add `ClusterResponse` and `BridgeResponse` schemas
- `server/apps/backend/app/routers/learning_child.py` — add `GET /clusters` and `GET /bridges` endpoints
- `server/apps/backend/app/services/learning/topic_service.py` — add `get_cross_subject_bridges()` function
- `server/tests/backend/test_learning_cluster_api.py` — new test file

**Approach:**
1. Extend existing `ClusterResponse` schema (`server/apps/backend/app/schemas/learning.py:94-100`) with an optional `topic_count: int = 0` field. The existing schema already has id, subject, domain, age_range_start, age_group, summary.
2. Add `BridgeResponse` schema: `from_cluster_domain`, `from_subject`, `to_cluster_domain`, `to_subject`, `edge_count`.
3. Add `GET /clusters` endpoint in `learning_child.py` — delegates to `topic_service.list_clusters()` (already exists at line 142), enriched with topic counts via GROUP BY query on `learning_topics`.
4. Add `GET /bridges` endpoint — calls new `get_cross_subject_bridges(db, subject)` function that joins `learning_dependencies` with `learning_topics` (twice: for topic and prerequisite), filtering where subjects differ AND both topics match the current `source_taxonomy`. The `?subject=` param filters on `from_subject` (outgoing bridges from this subject). Group by cluster pairs (subject+domain on each side).
5. Both endpoints use locale-based source_taxonomy filtering (same pattern as `/map` endpoint).
6. **Bridge query sketch:**
   ```python
   TopicAlias = aliased(LearningTopic)
   PrereqAlias = aliased(LearningTopic)
   query = (
       db.query(
           TopicAlias.subject.label("from_subject"),
           TopicAlias.domain.label("from_domain"),
           PrereqAlias.subject.label("to_subject"),
           PrereqAlias.domain.label("to_domain"),
           func.count().label("edge_count"),
       )
       .join(LearningDependency, LearningDependency.topic_id == TopicAlias.id)
       .join(PrereqAlias, LearningDependency.prerequisite_id == PrereqAlias.id)
       .filter(TopicAlias.subject != PrereqAlias.subject)
       .filter(TopicAlias.source_taxonomy == source_taxonomy)
       .filter(PrereqAlias.source_taxonomy == source_taxonomy)
       .group_by("from_subject", "from_domain", "to_subject", "to_domain")
   )
   if subject:
       query = query.filter(TopicAlias.subject == subject)
   ```
7. **Indexes:** Ensure composite indexes exist for the bridge query: `CREATE INDEX idx_topics_subject_taxonomy ON learning_topics(subject, source_taxonomy)` and `CREATE INDEX idx_deps_topic_prereq ON learning_dependencies(topic_id, prerequisite_id)`. Add to an Alembic migration if not already present.

**Patterns to follow:**
- Existing `/map` endpoint pattern in `learning_child.py:67-87` (locale filter, child auth)
- Existing `list_clusters()` in `topic_service.py:142-153`
- Schema patterns follow `SnowflakeBase` for ID serialization

**Test scenarios:**
- GET /clusters returns 183 clusters with correct subject/domain fields
- GET /clusters?subject=Mathematics filters to math clusters only
- GET /clusters includes accurate topic_count per cluster
- GET /bridges returns cross-subject bridge pairs (verify known edges: Science topic depending on Math prereq)
- GET /bridges?subject=Mathematics returns only bridges where Math is the source subject
- Empty result when no cross-subject edges exist for a subject

**Verification:** `uv run pytest server/tests/backend/test_learning_cluster_api.py -v` passes.

---

### U2. Frontend: ClusterMap Component with Territory Rendering

**Goal:** Build the core ClusterMap.vue component that replaces TopicGrid.vue — renders clusters as named territory cards containing mastery-colored topic nodes.

**Requirements:** R1, R2, R3, R8, R11

**Dependencies:** U1 (needs cluster API)

**Files:**
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — new component
- `frontend/apps/child/src/components/learning/ClusterTerritory.vue` — new sub-component (single territory card)
- `frontend/apps/child/src/components/learning/TopicNode.vue` — new sub-component (single topic circle)
- `frontend/apps/child/src/api/learning.ts` — add `getClusters()`, `ClusterResponse`, `BridgeResponse` types
- `frontend/apps/child/src/pages/learning/LearningMapPage.vue` — replace TopicGrid with ClusterMap

**Approach:**
1. Add API types and `getClusters(subject?, source_taxonomy?)` function in `learning.ts`. Follow existing `getTopicsBatch()` pattern.
2. `ClusterMap.vue` receives `items: ProgressWithTopic[]`, `clusters: ClusterResponse[]`, `selectedSubject: string`. Fetches bridges internally via `getBridges(selectedSubject)` in its own `load()` hook (see U4). Internally matches topics to clusters by `subject + domain + age_group`.
3. Renders as vertical scroll container. Each cluster becomes a `ClusterTerritory` card. Use `content-visibility: auto` on territory cards for lazy rendering (only render cards within ~2 viewport heights), reducing DOM nodes for subjects with 50+ clusters.
4. `ClusterTerritory.vue` renders a rounded card with: cluster domain name as label, summary text (truncated), and a flex-wrap grid of `TopicNode` circles inside.
5. `TopicNode.vue` renders a 40px circle colored by mastery state, with a minimum 44×44px tappable hit area (via padding on the wrapper element to meet the child app's 44px touch target standard). CSS classes for each state: `.mastered` (gold + box-shadow glow), `.learning` (blue + CSS pulse animation), `.available` (purple), `.locked` (gray + opacity 0.5), `.review` (orange). All animations respect `@media (prefers-reduced-motion: reduce)` (disable pulse/border animations; use `behavior: 'auto'` for scrollIntoView). Emits `@tap` with topic data.
6. `LearningMapPage.vue` replaces `<TopicGrid>` with `<ClusterMap>`, adds `getClusters()` call in `load()`.
7. Progress bar at top of ClusterMap: computed from items filtered by selectedSubject (mastered count / total count).
8. **Empty states:** (a) Subject with no clusters: `EmptyState` component with illustration + `t('learning.cluster.empty')` and suggestion to try another subject. (b) Zero progress (all nodes locked/available): show `t('learning.cluster.frontier.banner')` banner above the first cluster with a subtle highlight on the first recommended territory. (c) All topics mastered: progress bar fills with celebration color + `t('learning.cluster.allMastered')` message, suggest exploring other subjects. All user-facing strings use `t()` keys (per child app i18n convention — no hardcoded Chinese).

**Patterns to follow:**
- Existing TopicGrid.vue domain grouping pattern (line 116-124) — replace with cluster matching
- SubjectTabs.vue horizontal scroll pattern
- Vant `van-` components for cards and typography
- CSS custom properties for mastery colors (consistent with DnaGraph2D.vue mastery classes). New tokens must be defined in both `:root` and `[data-theme="dark"]` blocks (child app dark mode iron rule).

**Test scenarios:**
- ClusterMap renders one ClusterTerritory per cluster that has matching topics
- ClusterTerritory displays correct domain name and topic count
- TopicNode renders correct mastery color for each of the 5 states
- Progress bar shows correct mastered/total ratio for selected subject
- Empty state when no clusters exist for a subject
- Responsive: clusters wrap correctly at 375px width

**Verification:** Component renders in dev server with mock data matching all 5 mastery states. Visual check at 375px viewport.

---

### U3. Frontend: Context-Dependent Tap Handlers and Prerequisite Guidance

**Goal:** Implement context-dependent tap actions per mastery state and the prerequisite guidance view for locked topics.

**Requirements:** R4, R5

**Dependencies:** U2 (needs TopicNode and ClusterTerritory)

**Files:**
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — add tap handler routing
- `frontend/apps/child/src/components/learning/PrerequisiteGuidance.vue` — new component (bottom sheet)
- `frontend/apps/child/src/api/learning.ts` — use existing `getTopicGraph(topicId)` for prerequisite data (no new API function needed)

**Approach:**
1. In `ClusterMap.vue`, the `@tap` handler on TopicNode routes by mastery_level:
   - `mastered` → `router.push(/learning/topic/${topicId})` (existing topic detail page)
   - `available` / `learning` → `router.push(/learning/topic/${topicId}?action=practice)` (start practice)
   - `locked` → open `PrerequisiteGuidance` bottom sheet
   - `review` → `router.push(/learning/topic/${topicId}?action=review)`
2. `PrerequisiteGuidance.vue` is a `van-popup` (position=bottom) showing: topic name, list of unmet hard prerequisites with their mastery status (✅ mastered / ❌ not yet), and a "Go to [prerequisite]" button for each unmet prerequisite.
3. Prerequisite data: use existing `getTopicGraph(topicId)` endpoint (confirmed at `learning.py:174-186`) which returns prerequisites and dependents. Filter to hard prerequisites where the child's mastery is not "mastered".
4. Soft lock behavior (R5): tapping a locked node does NOT show an error or block. It shows the guidance sheet. The child can navigate to prerequisites from there. If they somehow reach a locked topic's detail page and try to start practice, the existing backend gate (403/409) handles enforcement.

**Patterns to follow:**
- Existing `van-popup` bottom sheet pattern from DnaGraph2D.vue (node detail sheet)
- Existing router.push patterns from LearningMapPage.vue:124 (`/learning/topic/${topicId}`)
- Existing prerequisite display from LearningTopicPage.vue

**Test scenarios:**
- Covers AE2. Tapping a `learning` node navigates to practice start
- Covers AE3. Tapping a `locked` node opens prerequisite guidance bottom sheet
- Prerequisite sheet shows correct unmet hard prerequisites with mastery status
- "Go to prerequisite" button navigates to the prerequisite topic
- Tapping a `mastered` node navigates to topic detail page
- Tapping a `review` node navigates to review session

**Verification:** Manual test in dev server — tap each mastery state and verify correct routing. Prerequisite sheet shows accurate data.

---

### U4. Frontend: Cross-Subject Bridge Visualization

**Goal:** Show cross-subject bridge indicators on clusters and enable navigation to connected clusters in other subject tabs.

**Requirements:** R6, R7

**Dependencies:** U1, U2

**Files:**
- `frontend/apps/child/src/components/learning/ClusterTerritory.vue` — add bridge badge display
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — pass bridge data to territories, handle bridge tap navigation
- `frontend/apps/child/src/pages/learning/LearningMapPage.vue` — handle bridge tap event from ClusterMap, switch selectedSubject
- `frontend/apps/child/src/api/learning.ts` — add `getBridges(subject?)` API call

**Approach:**
1. In `ClusterMap.vue` `load()`, call `getBridges(selectedSubject)` to fetch cross-subject bridges for the current subject.
2. Match bridges to ClusterTerritory components: a bridge with `from_cluster_domain === cluster.domain` belongs to that cluster.
3. `ClusterTerritory.vue` accepts optional `bridges: BridgeResponse[]` prop. When bridges exist, render a badge below the cluster label using `t('learning.cluster.bridgeLabel', { subjects })` (truncated to 2 subjects with "+N" overflow).
4. Tapping a bridge badge: switch `selectedSubject` to the target subject (emit event to parent LearningMapPage), then scroll to the target cluster using `scrollIntoView()` with the cluster's DOM id (`data-cluster-domain="..."`).
5. Bridge badge styling: small pill with link icon, muted color to not compete with topic nodes.

**Patterns to follow:**
- SubjectTabs tab-switching pattern (programmatic tab change)
- `scrollIntoView({ behavior: 'smooth' })` for navigation
- Vant `van-tag` for bridge badge styling

**Test scenarios:**
- Covers AE4. Cluster with cross-subject bridges shows bridge badge with target subject names
- Tapping bridge badge switches to target subject tab
- After tab switch, view scrolls to the connected cluster
- Cluster with no bridges shows no badge
- Bridge badge truncates at 2 subjects with "+N" overflow indicator

**Verification:** Manual test — verify bridge badges appear on clusters with known cross-subject edges (e.g., Math Measurement cluster). Tap badge and verify navigation.

---

### U5. Frontend: Progress Indicator and "You Are Here" Marker

**Goal:** Add overall subject progress bar and highlight the child's current learning frontier.

**Requirements:** R8, R9

**Dependencies:** U2

**Files:**
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — add progress bar and frontier detection
- `frontend/apps/child/src/components/learning/ClusterTerritory.vue` — add "frontier" highlight styling
- `frontend/apps/child/src/components/learning/TopicNode.vue` — add "here" marker for frontier topic

**Approach:**
1. Progress bar: computed property in ClusterMap — `masteredCount / totalCount` for items filtered by `selectedSubject`. Render as a thin bar at the top of the map area (below subject tabs). Format: "12/47 已掌握" with a colored fill bar.
2. Frontier detection: use the existing recommendation logic — the first topic with mastery_level `available` or `learning`, ordered by the recommendation priority (breakpoint > curriculum gap > review). This is the "next recommended topic."
3. Highlight the cluster containing the frontier topic with a subtle border glow or "📍 推荐" badge on the territory card.
4. Highlight the frontier topic node with a "📍 You are here" ring (dashed border animation).
5. Auto-scroll: on initial load, if the frontier cluster is below the fold, `scrollIntoView({ behavior: 'smooth', block: 'center' })` to bring it into view. This is a one-time scroll on load, not continuous tracking.

**Patterns to follow:**
- Existing progress bar pattern from `PracticeResultSummary.vue`
- CSS `@keyframes` for dashed border animation (similar to `.learning` pulse)
- `onMounted` hook for one-time auto-scroll

**Test scenarios:**
- Covers AE5. Child with no progress sees "0/47 已掌握" and "You are here" on first available topic
- Progress bar updates correctly as child completes practice (verify after returning from session)
- Frontier topic has visible "here" marker
- Auto-scroll brings frontier cluster into view on load
- When all topics in a subject are mastered, progress shows "47/47 已掌握" with no "here" marker

**Verification:** Visual test in dev server — verify progress bar accuracy, "here" marker placement, and auto-scroll behavior.

---

### U6. Integration Testing and E2E Verification

**Goal:** End-to-end verification that the cluster map works correctly with real data and the practice flow.

**Requirements:** R1-R12 (all)

**Dependencies:** U1-U5

**Files:**
- `server/tests/backend/test_learning_cluster_api.py` — backend API tests (created in U1, expanded here)
- `frontend/apps/child/src/components/learning/ClusterMap.test.ts` — component unit tests
- `frontend/apps/child/src/pages/learning/LearningMapPage.test.ts` — update existing test file

**Approach:**
1. Backend tests (expand U1 tests): verify full data flow — clusters with topic counts, bridges with correct cross-subject edges, locale filtering.
2. Frontend component tests: ClusterMap renders correct number of territories, topic-to-cluster matching works, mastery coloring is correct, tap handlers route correctly.
3. Integration: verify LearningMapPage loads clusters + topics + bridges, renders ClusterMap instead of TopicGrid, subject tab switching works.
4. E2E smoke test: with seeded data (demouser/小宝), verify the map loads, clusters display, tapping a learning node starts practice, tapping a locked node shows prerequisites.

**Test scenarios:**
- Full flow: load map → select subject → see clusters → tap available topic → start practice → complete → return to map → node turns gold
- Cluster topic counts match actual topic counts per subject+domain
- Cross-subject bridges appear on correct clusters
- Locked topic tap shows prerequisite guidance with correct unmet prereqs
- Map loads within 2 seconds on mobile network throttling (performance)

**Verification:** `uv run pytest server/tests/backend/test_learning_cluster_api.py -v` and `pnpm exec playwright test` for frontend integration.

---

### Risks and Mitigations

**Risk 1: Cluster density on mobile.** Math (503 topics) may produce 50+ clusters. Vertical scroll through 50 territory cards is long but manageable (similar to a long feed). Mitigation: add domain-level collapsible grouping if user testing shows navigation difficulty (OQ1). This is a follow-up, not v1 scope. → [#133](https://github.com/vincentruan/numina/issues/133)

**Risk 2: Cross-subject bridge count is low.** Verification confirmed 161 cross-subject edges exist, but they may cluster in a few domains. If a subject has only 1-2 bridges, the feature is underwhelming. Mitigation: bridge badges degrade gracefully — clusters with no bridges simply show no badge. → [#136](https://github.com/vincentruan/numina/issues/136)

**Risk 3: Topic-to-cluster matching ambiguity.** Topics with NULL domain won't match any cluster. The matching algorithm uses `subject + domain + age_group` (all string fields on both models). Topics with NULL domain or no matching cluster are collected into a synthetic "其他" (Other) territory at the bottom of the subject view, following the existing TopicGrid pattern (`item.topic.domain || t('learning.general')`).

**Risk 4: Source taxonomy cluster seeding (BLOCKER).** `locale_to_source_taxonomy()` maps zh-CN to 'beijing', but `seed_learning_topics.py` imports clusters.json with `source_taxonomy='os-taxonomy'` only. The `upsert_cluster()` function can handle beijing clusters but is not called in the standard seed path. **Must resolve before U1 implementation:** either (a) add beijing cluster seeding to the seed script's `seed_clusters()` function, or (b) configure the cluster endpoints to fall back to os-taxonomy when beijing clusters are absent. Without this, zh-CN children will see an empty map. → [#138](https://github.com/vincentruan/numina/issues/138)

---

### Verification Contract

1. All backend tests pass: `uv run pytest server/tests/backend/test_learning_cluster_api.py -v`
2. All frontend unit/component tests pass: `pnpm --filter child exec vitest run`
3. Frontend integration/E2E tests pass: `pnpm exec playwright test` (see U6)
4. Visual verification: map renders correctly at 375px viewport width with all 5 mastery states visible
5. E2E acceptance: all 5 Acceptance Examples (AE1-AE5) verified manually in dev server
6. No regression: existing LearningMapPage tests still pass after TopicGrid → ClusterMap replacement
7. Performance: map loads within 3 seconds on simulated 3G network

---

### Definition of Done

- [ ] U1: Backend cluster + bridge endpoints merged with passing tests
- [ ] U2: ClusterMap component renders territories with mastery-colored nodes
- [ ] U3: Context-dependent tap handlers work for all 5 mastery states
- [ ] U4: Cross-subject bridge badges display and navigate correctly
- [ ] U5: Progress bar and "You are here" marker functional
- [ ] U6: Integration tests pass, E2E acceptance examples verified
- [ ] All acceptance examples (AE1-AE5) verified in dev server
- [ ] No regression in existing learning map functionality
- [ ] Code review passed
