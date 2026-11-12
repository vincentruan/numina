---
title: Knowledge Continent Exploration Map - Plan
type: feat
date: 2026-11-12
topic: knowledge-continent-map
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Knowledge Continent Exploration Map - Plan

## Goal Capsule

**Objective:** A child opening the learning map sees the shape of what there is to learn — every subject as a place, every place in a state that invites a next step — instead of a ranked list of 1590 topics to work through.

**Product authority:** This plan covers the map surface only. Topic content, practice flows, and the adaptive engine are not active scope; existing data and endpoints feed this surface unchanged.

**Open blockers:** None.

---

## Product Contract

### Summary

Replace the fold-out list in the child learning map with a three-level ocean-and-islands map. Subjects sit as islands in a sea, veiled by fog that thins as that subject's mastery grows. Pinch and double-tap move between subject, domain, and topic levels, with topics drawn as constellations whose lines are prerequisite edges.

### Problem Frame

A child entering the learning map today meets a vertical stack of collapsible subject sections, each listing topic names. The format reads as an inventory: the child sees what is next in the list, not what exists. Two costs follow.

The first is a missing mental model. With 1590 topics behind accordions, no child forms a picture of how subjects relate, how a domain's topics build on one another, or where their current work sits in the larger shape. The list can express order. It cannot express structure.

The second is a missing invitation. A list of names has no pull — nothing in it is worth a second glance. A child picks whatever sits at the top of the first section, which is whatever the ordering algorithm happened to surface, and the rest of the map goes unvisited. Exploration requires that there be somewhere to be curious about.

### Key Decisions

- **Mental model first, motivation second.** When the two goals would pull toward different designs, the design serves comprehension of the knowledge landscape. `Governs R1, R5, R7.`
- **Fog is the answer to the 1590-topic scale problem.** Every topic stays present and reachable; fog controls how much is legible, not what is available. Nothing is locked. `Governs R2, R6.`
- **Fog clears per subject.** A subject's island fog responds to that subject's overall mastery ratio, not to individual topic mastery. `Governs R5.`
- **Organic island arrangement with relationship logic.** Island placement respects subject relationships (related subjects sit nearer) but takes organic variation so the map does not read as a diagram. `Governs R3.`
- **Progressive zoom, not progressive disclosure.** All three levels exist at all times; zoom changes which level is legible rather than revealing hidden content. `Governs R4, R8.`

### Requirements

**Map surface and structure**

- R1. The learning map's default view is the knowledge ocean, not the topic list.
- R2. Every subject the child can study appears as an island in the sea; no subject is hidden behind fog, pagination, or a collapsed section.
- R3. Island positions follow subject relationships — related subjects sit nearer — with organic variation so no two islands share a rigid grid or radial slot.
- R4. Three zoom levels exist: subject (islands in the sea), domain (the regions of one subject), and topic (the topics of one domain).

**Fog and progress**

- R5. Each island's fog opacity derives from its subject's mastery ratio, such that a subject at 0% mastery is heavily veiled and a subject at 80%+ mastery is fully clear.
- R6. Fog never blocks interaction. A fogged island and a fogged region remain tappable, and a tap yields a preview rather than a refusal.
- R7. Mastery affects only fog density; the sea, island silhouettes, and island labels stay legible at every mastery ratio, so the map's overall shape is always readable.

**Navigation and topic rendering**

- R8. Pinch and double-tap move between adjacent zoom levels, with double-tap descending and a zoom-out gesture returning.
- R9. At topic level, without further interaction, topics render as nodes and prerequisite relationships render as connecting lines, so the constellation pattern is visible on arrival.
- R10. Topics with no prerequisite edges remain visible as unconnected points rather than being dropped or hidden.

**Measurement**

- R11. The map records time-on-map per session, defined as elapsed time between map mount and the child's first topic selection.
- R12. Map interactions record the zoom level reached and whether a topic was selected from the map, so exploration depth is separable from dwell time.

### Key Flows

- F1. First arrival at the map
  - **Trigger:** The child opens the learning map.
  - **Steps:** The ocean renders with all subject islands in their fog states. The child pans and pinches; islands respond. The child taps an island and gets its preview. The child either descends to that subject's domains or leaves the map.
  - **Covered by:** R1, R2, R6, R7, R8, R11.

- F2. Descending to a constellation
  - **Trigger:** The child is at subject level and has chosen a subject.
  - **Steps:** The view zooms into that subject, revealing its domains as regions. A further zoom into a domain reveals its topics as a constellation with prerequisite lines. The child taps a topic and enters practice.
  - **Covered by:** R4, R8, R9, R10, R12.

- F3. Returning to a subject that has progressed
  - **Trigger:** The child's mastery in a subject has risen since the last visit.
  - **Steps:** The island's fog is thinner than at the last visit. Nothing else about the map's layout has moved.
  - **Covered by:** R3, R5, R7.

### Acceptance Examples

- AE1. A child with zero recorded mastery in every subject
  - **Covers R2, R5, R7.**
  - **Given** a new child account with no practice history,
  - **When** the child opens the map,
  - **Then** every subject island is present and heavily veiled, and every island's silhouette and label remain readable through the fog.

- AE2. A child taps a fogged island
  - **Covers R6.**
  - **Given** a subject island at low mastery,
  - **When** the child taps it,
  - **Then** the child sees a preview of that subject rather than a blocked or locked state, and can continue into it.

- AE3. A domain whose topics have no prerequisite edges
  - **Covers R9, R10.**
  - **Given** a domain containing topics with no recorded prerequisite edges,
  - **When** the child zooms to topic level in that domain,
  - **Then** those topics appear as points with no connecting lines, and the topics that do have edges show their lines.

- AE4. Exploration that ends without a selection
  - **Covers R11, R12.**
  - **Given** a child who pans, pinches, and previews several islands but selects no topic,
  - **When** the child leaves the map,
  - **Then** the recorded exploration time and zoom depth are retained even though no topic selection occurred.

### Success Criteria

- Children spend a median of two or more minutes on the map between opening it and selecting a topic, measured over the first four weeks after release.
- The time-on-map measurement distinguishes dwell from navigation: a session that only scrolls past the map is not counted as exploration (R11, R12).

<!-- ce-section: work-relationships -->

### How This Work Fits Together

This plan covers the map surface only. It is one of several separately planned pieces of a broader child-learning improvement effort; that breakdown is the current understanding, not a committed roadmap.

- Knowledge Castle Visualization (issue #209)
  - Depends on this plan. The castle reuses the visual language and rendering experience this surface establishes.
  - Still to decide: whether the castle replaces the XP progress surface or sits beside it.
- Discovery-First Challenge Flow (issue #210)
  - Can proceed independently of this plan. It changes the practice entry, not the map.
- Practice-experience issues generally
  - Share the topic and progress data this map consumes; a change to that data shape would reach both.

### Scope Boundaries

- Topic content, practice sessions, the adaptive engine, and the knowledge graph's data are unchanged; this plan consumes their existing outputs.
- Per-topic fog clearing is deferred. Fog responds to subject mastery only (R5).
- Redesigning the map for desktop-first layouts is deferred; the map is designed for the child app's touch surface.
- The existing list view's removal is not required by this plan. Whether it survives as a secondary view is deferred to planning.

### Dependencies / Assumptions

- Prerequisite edges exist for 3,221 topic pairs. Domains whose topics fall outside those pairs will render partially unconnected, which R10 accepts by design.
- Subject-level mastery ratios are derivable from existing progress records without a new aggregation service; if that assumption fails, it is a planning-time discovery, not a scope change.

### Outstanding Questions

- **Deferred to Planning:** Whether the existing `ContinentFog.vue`, `PathOverlay.vue`, and Cytoscape-based `GraphMap.vue` are extended or replaced. The requirements are indifferent to the answer; the three-level zoom and constellation rendering are what must hold.
- **Deferred to Planning:** How island positions are computed and persisted — generated per child, or generated once and shared. R3 constrains the outcome (relational but organic), not the storage.
- **Deferred to Planning:** Whether the list view remains reachable, and from where.

### Sources / Research

- `docs/ideation/2026-11-10-child-learning-experience-ideation.html` — the originating ideation document.
- `frontend/apps/child/src/components/learning/ClusterMap.vue` — the current list surface being replaced as default.
- `frontend/apps/child/src/components/learning/ContinentFog.vue` — existing fog-of-war with a mastery-ratio-to-opacity mapping.
- `frontend/apps/child/src/components/learning/GraphMap.vue` — existing Cytoscape surface with mastery-state styling.
- `frontend/apps/child/src/components/learning/PathOverlay.vue` — existing SVG trail rendering.
- `frontend/apps/child/src/api/learning.ts` — `TopicResponse`, `ProgressResponse`, `DependencyEdge` shapes this surface consumes.
