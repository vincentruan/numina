---
title: "Child app NProgress bar stuck spinning on /wishes/new — bypassed guard flag in loading lifecycle"
date: 2026-07-20
category: ui-bugs
module: frontend-child
problem_type: ui_bug
component: frontend_stimulus
severity: medium
symptoms:
  - "NProgress bar spins forever on /wishes/new in the child app after triggering 'continue creating'"
  - "Loading state never resolves on the only non-skeleton child-app route"
  - "Other 8 child-app routes (skeleton routes) are unaffected — only the non-skeleton route hangs"
root_cause: logic_error
resolution_type: code_fix
tags: [nprogress, loading-state, vue-router, child-app, lifecycle, guard-flag]
---

# Child App NProgress Bar Stuck Spinning on `/wishes/new`

> Branch-local: `feat/two-ai-apps-unified-dispatch` (unmerged at time of writing). Fix shipped in commit `b58f8c18` on this branch. All file:line citations are against the tree at that commit.

## Problem

The child app's nprogress top loading bar got stuck spinning forever on the `/wishes/new` route after the user tapped "continue creating" (which submits the wish form but deliberately does NOT navigate away — the user stays on the create page to create another). The root cause was a guard-flag asymmetry: the loading-done path was gated behind a `nprogressStarted` boolean that only ONE of TWO start paths ever set, so the cleanup gate never opened for the start path that the router used.

## Symptoms

- The nprogress bar at the top of the viewport spins indefinitely after tapping "continue creating" on `/wishes/new`. The spinner never completes; it persists across subsequent interactions on the same page until a navigation finally fires.
- The other 8 child routes (`/`, `/tasks`, `/ledger`, `/wishes`, `/wishes/:id`, `/assets/:id`, `/treasures`, `/calendar/day`) are unaffected — they spin briefly then complete normally.
- "Return to list" on `/wishes/new` (which navigates to the `/wishes` list page) stops the bar — because that navigation triggers the router's `afterEach` hook, which calls `NProgress.done()` directly for skeleton routes.
- "Continue creating" (which does NOT navigate — the form clears and the user remains on `/wishes/new`) does NOT stop the bar. With no navigation, neither `afterEach` nor any page-level `done()` fires, so the bar is orphaned spinning.
- The bug is scoped to `/wishes/new` because it is the only child route that omits the `meta: { hasSkeleton: true }` flag (`frontend/apps/child/src/router/index.ts:47` — every other content route sets it at lines 26/32/38/44/55/61/67/77). Routes with `hasSkeleton: true` go through the `afterEach` direct-`done()` fast path (`frontend/apps/child/src/router/index.ts:168-171`). `/wishes/new` instead defers to the page's own `usePageLoading` lifecycle — which is exactly where the broken guard lived.

## What Didn't Work

- **Debugging the NProgress bar itself / the page's fetch logic.** A natural first instinct is to suspect the wish-create API call, the form submit handler, or the nprogress configuration (`showSpinner`, `parent`, `trickleSpeed`). All red herrings. The bar was spinning because of a *lifecycle bookkeeping* bug in the loading-state coordinator, not because of any slow network request or nprogress misconfiguration. The page's fetch completed fine; the coordinator simply never told nprogress to stop.
- **Hunting inside `/wishes/new`'s page component.** The bug was not in the create page at all. It was in the shared `usePageLoading` composable (`frontend/apps/child/src/composables/usePageLoading.ts`) that the page (and every other non-skeleton page) relies on. The create page just happened to be the only non-skeleton route, which is why it was the only page that could trigger the bug.
- **The guard-flag asymmetry between the two start paths.** The decisive dead-end was conceptual: assuming "NProgress was started, therefore `nprogressStarted` is true." It wasn't. `router.beforeEach` calls `NProgress.start()` *directly* (`frontend/apps/child/src/router/index.ts:137`) and never touches `nprogressStarted`. Only `increment()` (`frontend/apps/child/src/composables/usePageLoading.ts:54-56`) sets `nprogressStarted = true`. So for any page whose loading lifecycle begins with a router navigation (which is all of them), the flag was `false` at done-time, the `if (nprogressStarted)` guard closed, and `done()` was skipped.

## Solution

The fix closes the start-path asymmetry and adds a defense-in-depth backstop. Three changes:

### 1. Unconditional `NProgress.done()` in cleanup paths

In `complete()` and the `onUnmounted` handler, drop the `if (nprogressStarted)` guard and call `NProgress.done()` unconditionally. The same unconditional call was added to `completeGlobalLoading()` (the emergency-cleanup export the router's safety timeout and the new stuck-timeout call). From `frontend/apps/child/src/composables/usePageLoading.ts`:

```ts
// BEFORE (guarded — never opened for router-started NProgress)
function complete() {
  loadingCount.value = 0
  pendingInstances.clear()
  if (nprogressStarted) {       // ← false when router started NProgress
    NProgress.done()
    nprogressStarted = false
  }
}

// AFTER (unconditional — closes the start-path asymmetry)
function complete() {
  loadingCount.value = 0
  pendingInstances.clear()
  if (stuckTimeoutId !== null) {
    clearTimeout(stuckTimeoutId)
    stuckTimeoutId = null
  }
  // Always call NProgress.done() - this is a cleanup function
  // Router beforeEach may have called NProgress.start() directly,
  // so we must complete NProgress unconditionally
  NProgress.done()
  nprogressStarted = false
}
```

The same unconditional `done()` lands in `onUnmounted` and in `completeGlobalLoading()`. The `decrement()` path keeps its `nprogressStarted` check — that path is only reachable when `increment()` ran, which is the one path that does set the flag, so the guard there is correct and harmless.

### 2. `stuckTimeoutId` 5-second safety net in `increment()`

A backstop for any future code path that starts loading but never decrements. When `increment()` transitions the counter to 1 and starts NProgress, it also schedules a 5-second `setTimeout` that force-calls `completeGlobalLoading()` if loading is still active. The timeout is cleared on normal completion (`decrement()` reaching 0, `complete()`, `completeGlobalLoading()`, and `onUnmounted`). DEV-mode logs a warning so stuck leaks are visible in development. From `frontend/apps/child/src/composables/usePageLoading.ts:54-68`:

```ts
if (loadingCount.value === 1 && !nprogressStarted) {
  NProgress.start()
  nprogressStarted = true

  // Start stuck safety timeout
  if (stuckTimeoutId !== null) {
    clearTimeout(stuckTimeoutId)
  }
  stuckTimeoutId = setTimeout(() => {
    if (import.meta.env.DEV) {
      console.warn('[usePageLoading] Loading operation stuck, forcing complete')
    }
    completeGlobalLoading()
  }, 5000)
}
```

### 3. `scrollBehavior` on the child router

Added the missing `scrollBehavior` to the router config (`frontend/apps/child/src/router/index.ts:15`):

```ts
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0 }),
  routes: [ /* ... */ ]
})
```

The child router previously lacked this; the main app already had it. Without it, bottom-nav tab switches preserved the previous route's scroll position, so switching from a long ledger back to home left the home page scrolled partway down. This is unrelated to the nprogress bug but was caught and fixed in the same pass since the router file was already open.

### Test

Added `ChildWishCreatePage.loading.test.ts` covering the loading-state contract: `onMounted` `complete()` leaves `globalLoadingCount` at 0; submit + continue-create does not leak loading count. **Verification caveat:** the NProgress `start()`/`done()` calls themselves cannot be asserted in happy-dom — the bar never renders in the virtual DOM, and `vi.mock('nprogress')` cannot reliably replace the binding that `usePageLoading` captured at module-eval time under native ESM + pnpm's symlinked node_modules. So the nprogress-specific fix is verified by *source-level parity* with the main app's already-shipped correct `usePageLoading` implementation, not by a direct nprogress call assertion. This is a real testability gap worth recording for anyone touching this composable in the future. *(auto memory [claude] — ai-chat-child-nprogress-stuck-fix)*

## Why This Works

The root cause was a **two-start-paths, one-flag** asymmetry. There were two places NProgress could be started on a child-app navigation:

1. `router.beforeEach` (`frontend/apps/child/src/router/index.ts:137`) — calls `NProgress.start()` *directly*, sets `nprogressStarted` to nothing (leaves it `false`).
2. `increment()` (`frontend/apps/child/src/composables/usePageLoading.ts:54-56`) — calls `NProgress.start()` AND sets `nprogressStarted = true`.

The cleanup path (`complete()`, and originally `onUnmounted`) gated `NProgress.done()` behind `if (nprogressStarted)`. Since every navigation goes through path (1), `nprogressStarted` was `false` at cleanup time for every page whose loading lifecycle was driven by `complete()` rather than `decrement()`. The guard never opened. `done()` was skipped. The bar spun.

For the 8 skeleton routes, this was masked: their `afterEach` hook (`frontend/apps/child/src/router/index.ts:168-171`) calls `NProgress.done()` *directly*, bypassing `usePageLoading` entirely. So the guard never ran for them. `/wishes/new` was the one route that deferred entirely to `usePageLoading`'s `complete()` (called in `onMounted` because the create page has no skeleton and no async fetch to wait on) — and that's the one path the guard broke.

Making `done()` unconditional in `complete()` / `onUnmounted` / `completeGlobalLoading()` removes the dependence on the flag entirely for cleanup. NProgress's own `done()` is idempotent (calling it when nothing is in progress is a no-op), so unconditionally calling it costs nothing when the flag would have been `true`, and fixes the leak when the flag was `false`. The `stuckTimeoutId` backstop is the second layer: even if a *future* start path fails to pair with a decrement, the 5-second timeout force-completes the loading state so no spinner can ever leak indefinitely. The existing `routerTimeoutId` safety timeout in `afterEach` (`frontend/apps/child/src/router/index.ts:179-182`) is a third layer — it covers the case where a page never calls `increment()` at all.

## Prevention

Four strategies, ordered by leverage:

**(a) When a lifecycle flag guards cleanup, ensure EVERY start path sets it — or make cleanup unconditional.** The bug was a flag whose set-sites and check-sites were out of sync. Two safe designs: either (i) funnel every start through a single function that sets the flag (here, route the router's `NProgress.start()` through `increment()` too), or (ii) make cleanup not depend on the flag at all when the underlying operation is idempotent. NProgress's `done()` is idempotent, so option (ii) was strictly simpler and is what shipped. The general lesson: a guard flag is a coupling between start and stop; if you can eliminate the coupling by relying on idempotency, do.

**(b) Cross-app pattern parity.** The main app (`frontend/apps/main`) already shipped the correct `usePageLoading` implementation. The child app diverged — someone hand-rolled a variant and introduced the guard asymmetry the main app didn't have. A shared composable package (or at minimum a parity check / diff against the known-good impl when touching the sibling) would have caught this at write time. The repo already has a `frontend/packages/` workspace; this composable is a strong candidate to live there. The broader signal: when two apps in a monorepo share a pattern, treat divergence as a smell, not just a style preference — divergence in lifecycle bookkeeping is where this class of bug breeds.

**(c) Always add a timeout safety-net to any start/stop pair that can leak.** Loading spinners, toasts, progress bars, "submitting…" badges, full-screen overlays — anything with a start and a stop that can be orphaned by an early return, an exception, or an unmounted component. The 5-second `stuckTimeoutId` here is the template: start it alongside the start, clear it on every stop path, and have it force-stop on expiry with a DEV-mode warning. The cost is one `setTimeout` per loading cycle; the benefit is that no future refactor can ever produce an orphaned spinner. This is defense-in-depth for UI state, and it is cheap.

**(d) The happy-dom test caveat — verify by source-parity when the runtime can't be asserted.** NProgress can't be meaningfully asserted in happy-dom (bar never renders; `vi.mock` can't replace the binding captured at native-ESM module-eval under pnpm). When the runtime behavior can't be directly tested, the next-best verification is source-level parity with a known-good implementation, plus a test that asserts the *invariant you can* observe (here, `globalLoadingCount` returning to 0). Record the gap explicitly in the test file so the next maintainer knows the nprogress calls themselves are unverified by automated tests and relies on the parity argument + manual smoke. Do not pretend the test covers more than it does.

### Sibling pattern: tolerant-success UX robustness

The same branch shipped a sibling "make the failure path graceful" fix worth noting in the same family: **idempotent chore approval** (commit `1384f2e4`). When a child (or parent) approves a chore that was already approved — e.g., a double-tap, a retry after a network blip, two clients acting on the same chore — the backend returns `409 Conflict` or `422 Unprocessable` (depending on which invariant tripped). Rather than surfacing that as an error toast, the child app treats `status === 'approved'` (the post-failure re-fetch state) combined with a 409/422 response as a *success*: it shows the success toast and updates the UI optimistically. This is the same philosophical family as the unconditional `done()`: don't let a bookkeeping edge case (a duplicate request, an already-started NProgress) produce a degraded user experience. The user's intent was "approve this chore" / "stop the spinner"; if the end state already satisfies that intent, declare success. Both fixes are about making the failure path of a state machine converge to the same observable outcome as the happy path.

## Related

- **Cross-reference** [`../best-practices/gamified-child-system-architecture-2026-04-17.md`](../best-practices/gamified-child-system-architecture-2026-04-17.md) — same child app (`frontend/apps/child`) and wishes/心愿 feature domain; documents backend batch-endpoint + E2E route-manifest patterns. Adjacent to the router-guard surface where this bug lives, but has no loading-state/nprogress content.
- **Cross-reference** [`../developer-experience/vue3-i18n-locale-switching-persistence-2026-05-15.md`](../developer-experience/vue3-i18n-locale-switching-persistence-2026-05-15.md) — same child app and same module-level singleton composable pattern that `usePageLoading` mirrors.
- **Sibling** [`vant4-field-modelvalue-binding-2026-04-08.md`](./vant4-field-modelvalue-binding-2026-04-08.md) — same `ui-bugs/` category and Vue 3 + Vant stack; frontmatter-convention reference.
- **Sibling** [`dark-mode-inline-style-specificity-2026-05-30.md`](./dark-mode-inline-style-specificity-2026-05-30.md) — same `ui-bugs/` category and Vue 3 frontend stack.
