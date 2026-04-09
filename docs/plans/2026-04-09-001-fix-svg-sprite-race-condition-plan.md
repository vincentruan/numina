---
title: "fix: Inline SVG sprite to eliminate async load race condition"
type: fix
status: completed
date: 2026-04-09
---

# fix: Inline SVG sprite to eliminate async load race condition

## Overview

Category icons in the asset form popup are blank. The popup picker was correctly implemented (commit `6d961fb`), but icons still don't render because the SVG sprite sheet is loaded asynchronously — and the popup can open before the sprite is injected into the DOM.

## Problem Frame

`App.vue` fetches `/icons.svg` in `onMounted` and injects it as a hidden `<div>` into `document.body`. This is async. When a user navigates directly to the asset form and opens the category picker before the fetch resolves, `<use href="#icon-home">` finds no matching `<symbol>` in the DOM and renders nothing.

Icons on `AssetListPage` (via `AssetCard`, `AssetListItem`) appear to work because the user spends enough time on that page for the fetch to complete before icons are rendered. The category popup is the first place where icons are needed immediately on interaction.

The fix is to inline the sprite content directly in `index.html` so symbols are available synchronously at page load — no fetch, no race.

## Requirements Trace

- R1. Category icons in the asset form popup must render on first open, regardless of navigation timing.
- R2. Icons elsewhere in the app (AssetCard, AssetListItem) must continue to work.
- R3. No runtime fetch of `/icons.svg` should be needed.

## Scope Boundaries

- Only `index.html` and `App.vue` are modified.
- No changes to `icons.svg`, `getIconId`, component templates, or any other files.
- The `icons.svg` file in `public/` can remain (no harm in keeping it), but it will no longer be fetched at runtime.

## Context & Research

### Relevant Code and Patterns

- `frontend/index.html` — currently 15 lines, no sprite reference. The inline sprite goes here as a hidden `<div>` at the top of `<body>`.
- `frontend/src/App.vue:56-67` — async fetch + inject logic to remove.
- `frontend/public/icons.svg` — 17KB, 174 lines. All 21 category symbols (`icon-home` through `icon-other-finance`) plus social icons. Appropriate size for inlining.
- `frontend/src/utils/icon.ts` — `getIconId()` unchanged; still correct.
- `frontend/src/components/asset/AssetForm.vue:65-67` — `<svg><use :href="`#${getIconId(cat.icon)}`">` — unchanged; will work once symbols are in DOM at load time.

### Why inline over other approaches

| Approach | Tradeoff |
|---|---|
| Inline in `index.html` (chosen) | Symbols available synchronously; zero runtime fetch; 17KB added to initial HTML (acceptable for a self-hosted app) |
| `<link rel="preload">` + keep async inject | Reduces latency but doesn't eliminate the race — inject still happens after JS runs |
| Vite plugin to inline at build time | Correct but adds build complexity for a 17KB file |
| Wait for sprite load before rendering popup | Adds reactive state complexity across components |

## Key Technical Decisions

- **Inline the sprite in `index.html` body, not `<head>`**: SVG `<symbol>` elements must be in `<body>` to be referenceable by `<use>` in the same document. A hidden `<div>` wrapper at the top of `<body>` (before `#app`) matches the existing runtime injection pattern.
- **Remove the async fetch from `App.vue` entirely**: Once inlined, the fetch is redundant. Keeping it would re-inject the sprite on every page load, creating duplicate symbol IDs in the DOM (harmless but wasteful).
- **Keep `icons.svg` in `public/`**: No reason to delete it. It serves as the source of truth for the sprite content and can be used for tooling or future reference.

## Open Questions

### Resolved During Planning

- **Is 17KB acceptable to inline?** Yes — this is a self-hosted PWA-style app; the sprite is loaded on every page anyway. Inlining saves a round-trip.
- **Will duplicate symbol IDs cause issues if the fetch somehow still runs?** The fetch is being removed, so no. Even if it ran, browsers handle duplicate `<symbol>` IDs gracefully (first match wins).
- **Does Vite do anything special with `index.html` that would break inline SVG?** No — Vite passes `index.html` through as-is for non-`<script>`/`<link>` content.

### Deferred to Implementation

- None. This is a straightforward two-file change.

## Implementation Units

- [x] **Unit 1: Inline SVG sprite into `index.html`**

**Goal:** Make all SVG symbols available synchronously at page load.

**Requirements:** R1, R2, R3.

**Dependencies:** None.

**Files:**
- Modify: `frontend/index.html`

**Approach:**
- Copy the full content of `frontend/public/icons.svg` into `index.html`.
- Wrap it in `<div id="svg-sprite-sheet" style="display:none">...</div>` placed as the first child of `<body>`, before `<div id="app">`.
- The wrapper `id` matches what `App.vue` currently sets, so any code checking for `#svg-sprite-sheet` continues to work.

**Test scenarios:**
- Happy path: open asset form → tap category field → popup shows icons for all physical categories immediately on first open.
- Happy path: navigate to asset list → `AssetCard` and `AssetListItem` icons render as before.
- Edge case: open category popup within 100ms of page load (fast navigation) → icons still render (no race possible with inline approach).

**Verification:**
- `npm run build` passes with no errors.
- In browser: open DevTools → Elements → `body` first child is `#svg-sprite-sheet` div containing SVG symbols.
- Category popup icons visible on first open without any delay.

---

- [x] **Unit 2: Remove async sprite fetch from `App.vue`**

**Goal:** Remove the now-redundant `fetch('/icons.svg')` logic.

**Requirements:** R3.

**Dependencies:** Unit 1 (sprite must be inlined before removing the fetch fallback).

**Files:**
- Modify: `frontend/src/App.vue`

**Approach:**
- Delete the `try/catch` block in `onMounted` that fetches `/icons.svg`, creates a container div, and injects it into `document.body` (lines 56–67).
- If `onMounted` becomes empty after removal, remove the entire `onMounted` block. If other logic remains (theme, language, media query listener), keep the block and only remove the fetch section.

**Test scenarios:**
- Test expectation: none — this is a dead-code removal. Behavior is unchanged; the sprite is already in the DOM from Unit 1.

**Verification:**
- `npm run build` passes.
- No network request to `/icons.svg` in DevTools Network tab on page load.

## System-Wide Impact

- **Unchanged invariants:** `getIconId()`, all component templates using `<use>`, category data flow — none of these change.
- **Initial HTML size:** Increases by ~17KB. Acceptable for a self-hosted app; saves one network round-trip.
- **No API surface changes.**

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `index.html` becomes harder to read with 174 lines of SVG | Acceptable tradeoff; the SVG block is clearly delimited by the wrapper div |
| Future icon additions require updating both `icons.svg` and `index.html` | Document in a comment inside `index.html` that the sprite block is sourced from `public/icons.svg` |

## Sources & References

- Related code: `frontend/src/App.vue`, `frontend/index.html`, `frontend/public/icons.svg`
- Related commits: `6d961fb` (popup picker), `dce7903` (getIconId extraction)
- Related plan: `docs/plans/2026-04-08-003-fix-asset-form-category-picker-plan.md`
