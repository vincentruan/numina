---
date: 2026-08-05
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: medium
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "Onboarding guide overlay (z-index 9999) blocks tab bar taps, page appears stuck"
  - "User taps a bottom tab bar icon — nothing happens"
  - "No console errors, no network requests — click silently swallowed"
tags:
  - overlay
  - z-index
  - navigation
  - route-watch
applies_when:
  - "Full-viewport overlay with high z-index intercepts navigation element clicks"
  - "Onboarding guide or modal blocks tab bar navigation"
---

# Onboarding Guide Overlay Blocks Tab Bar Navigation

## Problem
`StepGuideOverlay` (z-index 9999, pointer-events: all) covers the entire viewport when active, intercepting clicks on the bottom tab bar (z-index 1000). When a user taps a tab to navigate away from the onboarding guide, `router.push()` never fires because the overlay captures the click.

## Symptoms
- Dashboard or Tasks page shows onboarding guide
- User taps a bottom tab bar icon — nothing happens, page appears stuck
- No console errors, no network requests — click silently swallowed

## What Didn't Work
- Reducing overlay z-index below tab bar — overlay must be above page content to function
- Adding `pointer-events: none` to overlay — breaks the guide's own interactive elements (next/skip buttons)

## Solution
Add a route watcher in pages that show the onboarding guide. When navigation is detected, call `guide.skip()` to dismiss the overlay immediately. Also save/restore body scroll position to prevent scroll leakage.

**Before** (`frontend/apps/main/src/pages/DashboardPage.vue`):
```typescript
// No route watcher — overlay persists across navigation
onMounted(() => { guide.start() })
```

**After**:
```typescript
const route = useRoute()
watch(() => route.path, (newPath, oldPath) => {
  if (newPath !== oldPath && guide.isActive.value) {
    guide.skip()  // Dismiss overlay before navigation completes
  }
})
```

Additionally, the `StepGuideOverlay` component was updated to save/restore body scroll position:
```typescript
// Before open: save scroll
const savedScrollTop = document.body.scrollTop

// After close: restore scroll, zero on route-change dismiss
document.body.scrollTop = savedScrollTop
```

## Why This Works
The overlay is a full-viewport element with the highest z-index. When a tab bar tap triggers `router.push()`, the overlay intercepts the click event before it reaches the tab bar's `<a>` element. By watching for route changes and proactively dismissing the overlay, the overlay is removed from the DOM before the navigation completes, allowing the tab bar click to reach its target on subsequent taps. The scroll save/restore prevents the onboarding guide's `overflow: hidden` body lock from leaking to the target page.

## Prevention
- **Full-viewport overlays must self-dismiss on route change** — any overlay with z-index above navigation elements should watch `route.path` and auto-dismiss.
- **Test overlay + navigation interaction** — tap tab bar while overlay is visible; the expected behavior is immediate navigation, not "stuck" state.
