---
title: "refactor: Remove duplicate charts section from Dashboard"
type: refactor
status: completed
date: 2026-04-13
---

# refactor: Remove duplicate charts section from Dashboard

## Overview

The Dashboard page (`/`) contains a collapsible "数据可视化" section that renders `TrendLineChart` and `AllocationPieChart` — the exact same two components already present on the Stats page (`/stats`). Removing the duplicate from the Dashboard simplifies the page, reduces cognitive load, and makes the Stats tab the single authoritative home for chart analytics.

## Problem Frame

Two tabs show identical chart content sourced from the same store fields:

| Location | Label | Components |
|---|---|---|
| `DashboardPage.vue` (line 49–72) | "数据可视化" (collapsible) | `TrendLineChart`, `AllocationPieChart` |
| `DataStatsPage.vue` | "资产趋势" / "资产分布" | `TrendLineChart`, `AllocationPieChart` |

The Dashboard's version adds no unique value — it duplicates the Stats page with a worse UX (hidden behind a toggle, no section titles). Keeping only the Stats version is the right call.

## Requirements Trace

- R1. Remove the "数据可视化" collapsible charts block from `DashboardPage.vue`
- R2. Remove all code that exists solely to support that block (ref, handler, imports, CSS)
- R3. `DataStatsPage.vue` is unchanged — it remains the single home for trend and allocation charts
- R4. Dashboard still loads and renders correctly after the removal
- R5. No regressions in type-checking or build

## Scope Boundaries

- No changes to `DataStatsPage.vue` or any chart component
- No changes to routing, store, or API layer
- No UI redesign of the Dashboard — only removal of the charts block

## Context & Research

### Relevant Code and Patterns

- `frontend/src/pages/DashboardPage.vue` — template lines 49–72 (charts-section block), script line 272 (`showCharts` ref), script lines 510–512 (`onPeriodChange` handler), imports lines 259–260, CSS lines 745–771
- `frontend/src/pages/DataStatsPage.vue` — owns `TrendLineChart` + `AllocationPieChart` cleanly, no changes needed
- `frontend/src/components/charts/TrendLineChart.vue` — shared component, untouched
- `frontend/src/components/charts/AllocationPieChart.vue` — shared component, untouched

## Key Technical Decisions

- **Remove, don't hide:** The block is deleted entirely rather than feature-flagged or conditionally hidden. It adds no value and the Stats tab is always one tap away.
- **`onPeriodChange` is charts-only:** The handler calls `dashboardStore.fetchTrend(period)` and is only wired to `TrendLineChart`'s `@period-change` event. Safe to delete with the block.
- **`showCharts` ref is charts-only:** Only referenced inside the removed block. Safe to delete.
- **Imports:** `TrendLineChart` and `AllocationPieChart` are only used in the removed block. Both imports can be dropped.

## Implementation Units

- [ ] **Unit 1: Remove charts block from DashboardPage.vue**

**Goal:** Delete all code in `DashboardPage.vue` that exists solely for the "数据可视化" section.

**Requirements:** R1, R2, R4

**Dependencies:** None

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue`

**Approach:**
- Template: remove the entire `<!-- Charts Section (Expandable) -->` comment and `<div class="charts-section">` block (lines 49–72)
- Script: remove `const showCharts = ref(true)` (line 272)
- Script: remove the `onPeriodChange` function (lines 510–512)
- Script: remove `import TrendLineChart` and `import AllocationPieChart` (lines 259–260)
- CSS: remove the `/* Charts Section */` block and all four rules under it: `.charts-section`, `.charts-toggle`, `.charts-toggle-title`, `.charts-toggle-hint`, `.charts-toggle :deep(.van-icon)` (lines 745–771)

**Patterns to follow:** Other removed-import patterns in the same file — drop the line entirely, no tombstone comment.

**Test scenarios:**
- Happy path: Dashboard page renders without errors after removal; net worth card, alert cards, and asset list all display normally
- Happy path: Stats page (`/stats`) still renders both charts correctly and is unaffected
- Edge case: Dashboard with zero assets renders correctly (the removed block was already gated on `overview.asset_count > 0`, so empty state is unchanged)
- Error path: No TypeScript errors — `showCharts` and `onPeriodChange` are not referenced anywhere else in the file

**Verification:**
- `npm run typecheck` passes with no new errors
- `npm run build` completes successfully
- Navigating to `/` shows no charts section; navigating to `/stats` shows trend and allocation charts as before

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `onPeriodChange` referenced elsewhere in the file | Grep confirms it is only wired to the removed `TrendLineChart` `@period-change` event — safe to delete |
| `showCharts` used outside the removed block | Only referenced in the toggle button and the `v-if` inside the removed block — safe to delete |

## Sources & References

- Related code: `frontend/src/pages/DashboardPage.vue` lines 49–72, 259–260, 272, 510–512, 745–771
- Related code: `frontend/src/pages/DataStatsPage.vue`
