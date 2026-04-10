---
title: "fix: Currency button dark mode color inconsistency"
type: fix
status: completed
date: 2026-04-08
---

# fix: Currency button dark mode color inconsistency

## Overview

The exchange rate selector chip (`.currency-button`) in `CurrencyButton.vue` uses `var(--van-gray-2)` for its background. This raw Vant palette variable is not overridden in Vant's dark theme, so the chip stays light gray (`#f2f3f5`) against a dark field background in dark mode. Replacing it with the semantic `var(--van-active-color)` — which Vant correctly overrides to `#3a3a3c` in dark mode — resolves the inconsistency with a one-line change.

## Problem Frame

In dark mode, the currency selector chip inside `<van-field>` (used in AssetForm, LiabilityForm, and WishFormPage) renders with a light gray background while the surrounding field is dark. This is a visual inconsistency that breaks the unified dark theme.

Root cause: `--van-gray-2` is a raw palette variable (`#f2f3f5`) that Vant does not remap in `.van-theme-dark`. The semantic variable `--van-active-color` is the correct substitute — it maps to `var(--van-gray-2)` in light mode and `#3a3a3c` in dark mode.

## Requirements Trace

- R1. The currency button chip background must match the dark theme in dark mode
- R2. The fix must not change the light mode appearance
- R3. No new `[data-theme='dark']` override block should be needed — use the correct semantic variable

## Scope Boundaries

- Only `CurrencyButton.vue` is in scope — `CurrencySelector.vue` exists but is unused (no imports found)
- No changes to `CurrencyPicker.vue`, `CurrencyPicker`'s popup, or any form page
- No changes to dark mode infrastructure (`App.vue`, `style.css`, `stores/settings.ts`)

## Context & Research

### Relevant Code and Patterns

- `frontend/src/components/common/CurrencyButton.vue` — the broken component; `.currency-button` uses `var(--van-gray-2)` at line 55
- `frontend/src/components/asset/AssetForm.vue` — uses `CurrencyButton` in `#left-icon` slot
- `frontend/src/components/liability/LiabilityForm.vue` — uses `CurrencyButton` in `#left-icon` slot
- `frontend/src/pages/WishFormPage.vue` — uses `CurrencyButton` in `#left-icon` slot
- Dark mode is activated via `<van-config-provider :theme="resolvedTheme">` in `App.vue` (applies `.van-theme-dark`) and `document.documentElement.setAttribute('data-theme', theme)` (activates `[data-theme='dark']` CSS vars in `style.css`)
- Vant's `--van-active-color`: light → `var(--van-gray-2)` = `#f2f3f5`; dark → `#3a3a3c`

### Institutional Learnings

- No prior documented solutions for Vant dark mode theming in `docs/solutions/`

## Key Technical Decisions

- **Use `var(--van-active-color)` instead of `var(--van-gray-2)`**: This is the Vant semantic variable for "chip/tag/active background" that already has the correct dark value. No `[data-theme='dark']` override block is needed, keeping the fix minimal and aligned with how Vant's own components handle dark mode.
- **Do not touch `CurrencySelector.vue`**: The file exists but has zero imports in the codebase — fixing it would be dead code maintenance.

## Open Questions

### Resolved During Planning

- **Is `CurrencySelector.vue` in use?** No — grep found zero imports. Out of scope.
- **Should a `[data-theme='dark']` override block be used instead?** No — the existing codebase pattern uses `[data-theme='dark']` only when Vant's own variable system cannot cover the case. Here, `--van-active-color` already handles it cleanly.

### Deferred to Implementation

- Whether the `van-icon` arrow color inside the chip also needs adjustment — visually inspect in dark mode after the background fix lands.

## Implementation Units

- [x] **Unit 1: Fix `.currency-button` background variable**

**Goal:** Replace `var(--van-gray-2)` with `var(--van-active-color)` in `CurrencyButton.vue` so the chip background adapts correctly in dark mode.

**Requirements:** R1, R2, R3

**Dependencies:** None

**Files:**
- Modify: `frontend/src/components/common/CurrencyButton.vue`

**Approach:**
- In the `<style scoped>` block, change the `background` property of `.currency-button` from `var(--van-gray-2)` to `var(--van-active-color)`
- No other style changes needed — the border-radius, padding, and flex layout are theme-neutral

**Patterns to follow:**
- Vant semantic variable usage pattern: prefer `--van-*` semantic vars over raw palette vars (`--van-gray-*`) for any property that must adapt to dark mode

**Test scenarios:**
- Happy path: In light mode, the currency chip background is `#f2f3f5` (visually unchanged from before)
- Happy path: In dark mode, the currency chip background is `#3a3a3c` (dark, consistent with surrounding field)
- Edge case: Switching theme at runtime (light → dark → light) — chip background updates immediately without page reload
- Integration: Currency chip renders correctly inside `AssetForm`, `LiabilityForm`, and `WishFormPage` in both themes

**Verification:**
- In light mode: chip appearance is visually identical to before the fix
- In dark mode: chip background is dark and consistent with the `van-field` background — no light-gray island visible
- `npm run build` passes with no type errors

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `--van-active-color` semantic meaning shifts in a future Vant version | Low risk — this variable is stable and semantically correct for chip/tag backgrounds; monitor Vant changelog on upgrades |
| Arrow icon color inside chip may still look off in dark mode | Deferred — visually verify after background fix; `van-icon` inherits `color` from parent which should be fine via Vant's text color vars |

## Sources & References

- Related code: `frontend/src/components/common/CurrencyButton.vue:55`
- Related code: `frontend/src/components/asset/AssetForm.vue`, `frontend/src/components/liability/LiabilityForm.vue`, `frontend/src/pages/WishFormPage.vue`
- Vant 4 dark mode vars: `--van-active-color` light=`#f2f3f5`, dark=`#3a3a3c`
