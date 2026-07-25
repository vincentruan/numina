---
title: "NProgress progress bar flickering on page navigation — router/composable lifecycle race"
date: 2026-07-25
category: ui-bugs
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: medium
symptoms:
  - "Progress bar flashes multiple times when entering pages (start→done→start)"
  - "Flickering occurs on both skeleton and non-skeleton pages"
  - "Visual flicker most noticeable on pages with skeleton loaders"
root_cause: async_timing
resolution_type: code_fix
tags:
  - nprogress
  - vue-router
  - skeleton-loading
  - page-navigation
  - usepageloading
  - lifecycle-race
  - async-timing
  - visual-flicker
---

# NProgress Progress Bar Flickering on Page Navigation

## Problem

NProgress progress bar flickered when navigating between pages in the Vue 3 SPA, showing multiple start→done→start cycles instead of a single continuous bar from navigation start to data load completion. The issue occurred on every navigation across both the main app and child app.

## Symptoms

- Progress bar would flash: appear briefly, disappear, then reappear during a single page navigation
- Visual flicker was most noticeable on pages with skeleton loaders (DashboardPage, FinanceHubPage, BabyPage, AIHubPage)
- Child app pages (ChildHomePage, ChildTasksPage, etc.) exhibited the same flickering behavior
- The issue occurred on every navigation, not intermittently

## What Didn't Work

Initial attempts to fix by adjusting individual controllers (router hooks or page loading logic) failed because the root cause was architectural: three independent systems were each trying to control the same NProgress lifecycle without coordination. Adjusting one controller in isolation could not eliminate the flicker because the other two continued their independent start→done cycles.

## Solution

The fix coordinated the three independent NProgress controllers into a single unified lifecycle.

### Part 1: usePageLoading.ts — Router awareness

Added a `routerNprogressActive` flag that allows page components to take over NProgress control without restarting it when the router has already started the progress bar.

**Before:**
```typescript
export function usePageLoading() {
  function increment() {
    if (loadingCount.value === 0) {
      NProgress.start()
      nprogressStarted = true
    }
    loadingCount.value++
  }
  // ...
}
```

**After:**
```typescript
let routerNprogressActive = false

export function markRouterNprogressActive() {
  routerNprogressActive = true
}

export function usePageLoading() {
  function increment() {
    // Clear router's safety timeout to prevent TOCTOU race
    if (routerTimeoutId !== null) {
      clearTimeout(routerTimeoutId)
      routerTimeoutId = null
    }

    const instance = pendingInstances.get(instanceId)
    if (!instance || !instance.active) {
      return
    }

    loadingCount.value++
    instance.count++

    if (loadingCount.value === 1 && !nprogressStarted) {
      // If router already started NProgress, take over without restarting
      if (!routerNprogressActive) {
        NProgress.start()
      } else {
        routerNprogressActive = false
      }
      nprogressStarted = true
      // ... stuck safety timeout
    }
  }
  // ...
}
```

### Part 2: router/index.ts — Unified afterEach behavior

Removed the special case for `hasSkeleton` pages. All pages now use the same 200ms timeout, allowing pages with async work to take over NProgress control before the timeout fires.

**Before:**
```typescript
router.afterEach((to) => {
  if (to.meta.hasSkeleton) {
    clearRouterTimeout()
    NProgress.done()
    return
  }
  const timeoutId = setTimeout(() => {
    completeGlobalLoading()
  }, 200)
  registerRouterTimeout(timeoutId)
})
```

**After:**
```typescript
router.afterEach((_to) => {
  const timeoutId = setTimeout(() => {
    completeGlobalLoading()
  }, 200)
  registerRouterTimeout(timeoutId)
})
```

### Part 3: All skeleton pages — Use increment/decrement instead of complete

Changed pages from calling `complete()` (which immediately dismisses NProgress) to wrapping their `onMounted` async operations with `increment()/decrement()`.

**Before (example: DashboardPage):**
```typescript
onMounted(() => {
  dashboardStore.fetchAll()
  // NProgress already done() by router afterEach
  // Then increment() calls start() again → flicker
})
```

**After:**
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

**Pages updated (main app):**
- DashboardPage
- FinanceHubPage
- BabyPage
- AIHubPage
- AIChatBox

**Pages updated (child app):**
- ChildHomePage
- ChildTasksPage
- ChildLedgerPage
- ChildTreasuresPage
- ChildWishDetailPage
- ChildWishesPage
- ChildAssetDetailPage
- ChildDayDetailPage

**Special case:** ChildWishCreatePage removed `usePageLoading` entirely (pure form page with no async loading, relies on router 200ms timeout for auto-completion).

## Why This Works

The original implementation had three independent NProgress controllers:

1. **Router `beforeEach`**: Called `NProgress.start()` on every navigation
2. **Router `afterEach`**: For `hasSkeleton` pages, immediately called `NProgress.done()`; for other pages, set a 200ms timeout to call `completeGlobalLoading()` which does `NProgress.done()`
3. **Page components**: Called `usePageLoading().increment()` which called `NProgress.start()` again when `loadingCount` went 0→1

This created two independent start→done cycles per navigation:
- **Cycle 1**: router `beforeEach` start() → `afterEach` done() (immediate for skeleton pages, or 200ms timeout for others)
- **Cycle 2**: page `increment()` start() → `decrement()` done()

The visual result: progress bar appears, disappears, then appears again — a flicker.

The fix unifies these into a single lifecycle:
- Router `beforeEach` starts NProgress once and calls `markRouterNprogressActive()`
- Router `afterEach` sets a 200ms timeout for auto-completion (handles pages without async work)
- Pages with async work call `increment()` within 200ms, which clears the timeout and takes over NProgress control **without restarting it** (checks `routerNprogressActive` flag)
- Pages call `decrement()` when done, which calls `NProgress.done()` only when `loadingCount` reaches 0

The result: one continuous progress bar from navigation start to data load completion.

## Prevention

1. **Single lifecycle owner**: When multiple systems need to coordinate a shared resource (like NProgress), designate one owner that starts it and one owner that ends it. Other systems should signal intent (via flags or events) rather than directly manipulating the resource.

2. **Avoid special cases in router hooks**: Special-casing pages in `afterEach` (like the `hasSkeleton` check) creates divergent behavior that's hard to reason about. Prefer uniform behavior with escape hatches (like the 200ms timeout that pages can override).

3. **Use increment/decrement for async work**: Pages with async operations should use `increment()/decrement()` to signal loading state, not `complete()`. The `complete()` method should only be called by the router's auto-completion timeout.

4. **Test navigation visually**: Progress bar flickering is a visual bug that automated tests don't catch. When refactoring router hooks or loading logic, manually test navigation across multiple page types (with/without skeleton loaders, with/without async data).

5. **Document the NProgress contract**: The `routerNprogressActive` flag exists to prevent the router's `start()` from being called twice. Future contributors should understand that the router starts NProgress, pages take over via `increment()`, and the router's 200ms timeout is a safety net for pages without async work.

## Related

- **Sibling** [`nprogress-stuck-spinning-bypassed-guard.md`](./nprogress-stuck-spinning-bypassed-guard.md) — same `usePageLoading` composable, same router/page-loading boundary. This doc (flicker) = `done()` fires too early then restarts; that doc (stuck) = `done()` never fires. Two failure modes of the same ownership model.
- **Implementation plan** [`../../superpowers/plans/2026-06-13-nprogress-page-level-coordination.md`](../../superpowers/plans/2026-06-13-nprogress-page-level-coordination.md) — original design for the `usePageLoading` composable. The flicker bug was a remaining symptom the plan's architecture did not fully eliminate (router `afterEach` was still calling `done()` before page data load finished).
