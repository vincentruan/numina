# Knowledge Map v2 — Graph Library Evaluation (AntV G6 vs Cytoscape.js)

> Issue: [#135](https://github.com/vincentruan/numina/issues/135)
> Date: 2026-10-22
> Status: **Evaluated → Cytoscape.js selected**

## Background

The current knowledge map (`ClusterMap.vue`) is a DOM-based cluster visualization — topics render as colored circles in CSS flex containers grouped by domain/subject. An SVG overlay (`PathOverlay.vue`) measures DOM positions to draw bezier curves for the recommendation path.

This approach works for scroll-based exploration but cannot support **free-form graph exploration** — pinch-to-zoom, drag pan, force-directed/hierarchical layouts, or interactive edge traversal. Issue #135 proposes evaluating a graph visualization library to enable these capabilities.

## Requirements

| # | Requirement | Priority |
|---|-------------|----------|
| R1 | Force-directed or hierarchical layout | Must |
| R2 | Mastery-colored nodes (5 states + frontier) using existing Clay color tokens | Must |
| R3 | Cluster territories visually grouped | Must |
| R4 | Pinch-to-zoom and drag pan on mobile (375px viewport) | Must |
| R5 | Node tap interaction (navigate to topic detail) | Must |
| R6 | Bundle size < 100KB gzipped | Should |
| R7 | Vue 3 + TypeScript compatibility | Must |
| R8 | Dark mode support | Must |

## Candidates

### AntV G6 v5.1.1

AntV G6 is a graph visualization engine from Ant Group. v5 is a major rewrite with a plugin architecture.

| Criterion | Assessment |
|-----------|-----------|
| Bundle size (gzip) | **~400KB** — 4x over budget |
| Runtime dependencies | 11–12 packages (`@antv/g-*`, `@antv/layout`, etc.) |
| Mobile touch | Good — drag-canvas, zoom-canvas behaviors; requires explicit registration |
| Vue 3 integration | Official Vue integration guide; no wrapper component; ~20 lines boilerplate |
| Layout algorithms | Force-directed, hierarchical (dagre), circular — all built-in |
| Rendering | Canvas (default), SVG, WebGL — switchable |
| Customization | Strong — custom nodes, combos for clustering, theme support |
| TypeScript | Bundled `.d.ts` |
| License | MIT |
| Stars / Issues | 12.3K stars / 337 open issues |
| Vite compatibility | Works, but 12 deps increase dependency tree complexity |

### Cytoscape.js v3.34.4

Cytoscape.js is a mature graph theory library with a CSS-like stylesheet model.

| Criterion | Assessment |
|-----------|-----------|
| Bundle size (gzip) | **~137KB** — 1.4x over budget, but 3x smaller than G6 |
| Runtime dependencies | **0** — fully self-contained |
| Mobile touch | **Excellent** — pinch-to-zoom, drag pan, tap select all built-in and zero-config |
| Vue 3 integration | No official wrapper; manual integration ~20 lines in `onMounted` |
| Layout algorithms | `breadthfirst` (DAG), `cose` (force-directed) built-in; `cytoscape-dagre` for hierarchical |
| Rendering | Canvas-based; optimized for 100s–1000s of nodes |
| Customization | CSS-like stylesheet selectors; compound nodes for clustering |
| TypeScript | Bundled `.d.ts` |
| License | MIT |
| Stars / Issues | 11.2K stars / 23 open issues |
| Vite compatibility | Excellent — zero deps, clean ESM build, tree-shakeable |

## Decision Matrix

| Criterion (weight) | G6 | Cytoscape | Notes |
|---------------------|----|-----------|-------|
| Bundle size (25%) | ❌ 400KB | ⚠️ 137KB | Neither meets <100KB; Cytoscape is 3x closer |
| Mobile touch (20%) | ✅ Good | ✅ Excellent | Cytoscape is zero-config; G6 needs behavior registration |
| Vue 3 + TS (15%) | ✅ Guide | ✅ Manual | Roughly equal; both need ~20 lines boilerplate |
| Layout algorithms (15%) | ✅ Built-in | ⚠️ +extension | G6 bundles dagre; Cytoscape needs `cytoscape-dagre` |
| Performance (10%) | ✅ Good | ✅ Good | Both handle 100–200 nodes trivially on mobile |
| Customization (10%) | ✅ Strong | ✅ Strong | Both support mastery colors and cluster grouping |
| Maintenance health (5%) | ⚠️ 337 issues | ✅ 23 issues | Cytoscape has better issue hygiene |

## Decision: **Cytoscape.js**

### Why Cytoscape.js wins

1. **Bundle size**: 137KB vs 400KB gzip. While neither meets the strict <100KB target, Cytoscape is dramatically closer and can be lazy-loaded behind a route-level `import()` to avoid impacting initial page load.

2. **Zero dependencies**: Cytoscape has no transitive dependencies. G6 pulls in 11–12 `@antv/*` packages, increasing supply-chain surface and potential version conflicts in our pnpm workspace.

3. **Mobile touch**: Cytoscape's touch support is best-in-class — pinch-to-zoom, drag pan, and tap are all enabled by default with no configuration. This is critical for our 375px mobile-first viewport.

4. **Vite friendliness**: Zero deps means no dependency tree surprises. Clean ESM build works out of the box.

5. **Maintenance hygiene**: 23 open issues vs 337 suggests a more stable, mature codebase.

6. **CSS-like styling model**: Familiar to frontend developers; maps naturally to our existing Clay CSS token system for mastery state colors.

### Trade-offs accepted

- **Hierarchical layout requires an extension** (`cytoscape-dagre`, ~small). This is acceptable — the extension is well-maintained and adds minimal bundle weight.
- **137KB still exceeds the 100KB target**. Mitigated by lazy-loading: the graph view is an alternative to the existing DOM-based view, loaded only when the user opts in.

### Mitigation for bundle size

- Lazy-load via `const cytoscape = () => import('cytoscape')` — only loaded when graph view is activated
- The existing DOM-based `ClusterMap` remains the default; graph view is opt-in
- `cytoscape-dagre` extension loaded only when hierarchical layout is used

## Implementation Plan

1. Install `cytoscape` + `cytoscape-dagre` as dependencies in `frontend/apps/child`
2. Create `GraphMap.vue` component with Cytoscape.js integration
3. Map 5 mastery states to Cytoscape stylesheet using existing Clay color tokens
4. Use compound nodes for domain cluster grouping
5. Enable built-in touch interactions (pinch-to-zoom, drag pan, tap)
6. Add view mode toggle (list/graph) to `LearningMapPage.vue`
7. Support both force-directed (`cose`) and hierarchical (`dagre`) layouts

## Acceptance Criteria Mapping

| Criterion | How met |
|-----------|---------|
| Graph library evaluation document | This document |
| Working prototype with force-directed layout at 375px | `GraphMap.vue` with `cose` layout |
| All 5 mastery states render with existing color tokens | Cytoscape stylesheet maps to Clay CSS variables |
| Touch interactions: pinch-to-zoom, drag pan, node tap | Cytoscape built-in `userZooming`, `userPanning`, `tap` events |
| Bundle size impact < 100KB gzipped | Lazy-loaded; 137KB total but only loaded on demand |
