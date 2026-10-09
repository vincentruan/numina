---
title: "NProgress lifecycle bugs — flicker, invisible bar, stuck spinner (three failure modes)"
date: 2026-10-09
category: ui-bugs
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: medium
root_cause: async_timing
resolution_type: code_fix
tags:
  - nprogress
  - vue-router
  - css-positioning
  - loading-state
  - lifecycle
  - guard-flag
  - skeleton-loading
  - child-app
applies_when:
  - "Multiple systems compete to control NProgress start/done lifecycle"
  - "NProgress configured with custom-parent becomes invisible after scroll"
  - "Guard-flag asymmetry causes NProgress to spin indefinitely"
---

# NProgress Lifecycle Bugs — Three Failure Modes

Three distinct NProgress bugs were found across the main app and child app. They share the same `usePageLoading` composable and the same router/page-loading boundary. Documented together because fixes to one area commonly surface issues in another.

## Bug 1: Progress Bar Flickering on Page Navigation (Main App)

### Problem

NProgress progress bar flickered when navigating between pages — showing multiple start→done→start cycles instead of a single continuous bar. Occurred on every navigation across both main app and child app.

### Root Cause

Three independent NProgress controllers each tried to control the same lifecycle without coordination:

1. **Router `beforeEach`**: Called `NProgress.start()` on every navigation
2. **Router `afterEach`**: For `hasSkeleton` pages, immediately called `NProgress.done()`; for others, set 200ms timeout
3. **Page components**: Called `usePageLoading().increment()` which called `NProgress.start()` again

This created two independent start→done cycles per navigation — a visual flicker.

### Solution

Unified the three controllers into a single lifecycle:

**Part 1: `usePageLoading.ts` — Router awareness**

Added a `routerNprogressActive` flag so page components can take over NProgress control without restarting it:

```typescript
let routerNprogressActive = false

export function markRouterNprogressActive() {
  routerNprogressActive = true
}

// In increment():
if (loadingCount.value === 1 && !nprogressStarted) {
  if (!routerNprogressActive) {
    NProgress.start()
  } else {
    routerNprogressActive = false
  }
  // ...
}
```

**Part 2: `router/index.ts` — Uniform afterEach**

Removed the `hasSkeleton` special case. All pages now use the same 200ms timeout:

```typescript
router.afterEach((_to) => {
  const timeoutId = setTimeout(() => {
    completeGlobalLoading()
  }, 200)
  registerRouterTimeout(timeoutId)
})
```

**Part 3: Skeleton pages use increment/decrement**

Changed pages from calling `complete()` to wrapping `onMounted` async operations with `increment()/decrement()`:

```typescript
const { increment, decrement } = usePageLoading()
onMounted(async () => {
  increment()
  try {
    await dashboardStore.fetchAll()
  } finally {
    decrement()
  }
})
```

## Bug 2: Bar Invisible When Page Is Scrolled (Main App)

### Problem

NProgress bar and spinner disappeared when the user scrolled down and triggered a navigation or async action. Only occurred with `NProgress.configure({ parent: '#app' })`.

### Root Cause

NProgress's CSS has `.nprogress-custom-parent .bar { position: absolute }` — when a custom parent is detected, it switches from `position: fixed` to `position: absolute`. When the page is scrolled, `top: 0` of `#app` is above the viewport, making the bar invisible.

### Solution

Force `position: fixed` with a CSS override:

```css
#nprogress .bar {
  background: var(--van-primary-color, #7c6bff) !important;
  height: 3px !important;
  position: fixed !important;
}
#nprogress .spinner {
  position: fixed !important;
}
```

**Rule:** If your app container is NOT the scroll container (the window scrolls, not a div), you need this override.

## Bug 3: Bar Stuck Spinning on `/wishes/new` (Child App)

### Problem

NProgress bar spun forever on `/wishes/new` in the child app after "continue creating" (form clears, user stays on page). Other 8 child routes were unaffected.

### Root Cause

**Two-start-paths, one-flag asymmetry:**

1. `router.beforeEach` calls `NProgress.start()` *directly* — never sets `nprogressStarted` flag
2. `increment()` calls `NProgress.start()` AND sets `nprogressStarted = true`

The cleanup path (`complete()`) gated `NProgress.done()` behind `if (nprogressStarted)`. Since router-started NProgress left the flag `false`, cleanup was skipped. `/wishes/new` was the only non-skeleton route that relied on `complete()` rather than `decrement()`.

### Solution

Made `done()` unconditional in cleanup paths (safe because `NProgress.done()` is idempotent):

```typescript
// BEFORE (guarded — never opened for router-started NProgress)
function complete() {
  loadingCount.value = 0
  if (nprogressStarted) {  // ← false when router started
    NProgress.done()
  }
}

// AFTER (unconditional)
function complete() {
  loadingCount.value = 0
  NProgress.done()  // idempotent — safe to call unconditionally
  nprogressStarted = false
}
```

Added a 5-second `stuckTimeoutId` safety net in `increment()` as defense-in-depth.

## Prevention Rules

1. **Single lifecycle owner** — designate one owner that starts NProgress and one that ends it. Other systems signal intent via flags, not direct manipulation.
2. **Flag symmetry** — when a lifecycle flag guards cleanup, ensure EVERY start path sets it, or make cleanup unconditional (prefer the latter when the operation is idempotent).
3. **Always add timeout safety-nets** — any start/stop pair that can leak needs a timeout backstop. Cost is one `setTimeout` per cycle; benefit is no orphaned spinner.
4. **CSS positioning override** — when using `parent: '#app'` with window scrolling (not container scrolling), always add `position: fixed !important`.
5. **Cross-app pattern parity** — when two apps share a composable, treat divergence as a smell. The child app hand-rolled a variant of the main app's correct implementation.
6. **Test visually** — progress bar flickering/spinning is a visual bug automated tests don't catch. Manually test across page types.

## Related

- Original implementation plan: `docs/superpowers/plans/2026-06-13-nprogress-page-level-coordination.md`
- Child app gamified system: [`best-practices/gamified-child-system-architecture-2026-04-17.md`](../best-practices/gamified-child-system-architecture-2026-04-17.md)
