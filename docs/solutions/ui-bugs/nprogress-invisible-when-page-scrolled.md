---
title: "NProgress bar invisible when page is scrolled — custom-parent switches to position absolute"
date: "2026-08-19"
category: ui-bugs
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: medium
symptoms:
  - "NProgress top bar not visible when user scrolls down and triggers a navigation or async action"
  - "Spinner icon also disappears — both bar and spinner are above the viewport"
  - "Only occurs with NProgress configured with parent option (e.g. parent '#app')"
root_cause: config_error
resolution_type: code_fix
tags:
  - nprogress
  - css-positioning
  - custom-parent
  - scroll
  - vue-router
---

# NProgress Bar Invisible When Page Is Scrolled

## Problem

NProgress was configured with `parent: '#app'` (so the progress bar appears inside the app container, not the body). NProgress's CSS has a rule `.nprogress-custom-parent .bar, .nprogress-custom-parent .spinner { position: absolute }` that switches from `position: fixed` to `position: absolute` when a custom parent is detected. When the page is scrolled down, `top: 0` of `#app` is above the viewport, making the bar invisible.

## Symptoms

- The NProgress bar and spinner are completely invisible when the user scrolls down and then triggers a loading action (route change, data fetch, etc.).
- The bar IS visible when the page is at the top (scroll position = 0).
- The issue only occurs with `NProgress.configure({ parent: '#app' })`.

## What Didn't Work

- Changing `top` to `window.scrollY + 'px'` — NProgress manages its own positioning, external JS changes are overwritten.
- Removing `parent: '#app'` — the bar then appears relative to `<body>`, which doesn't respect the app container's z-index context.

## Solution

Force `position: fixed` on the NProgress bar and spinner with a CSS override:

```css
/* Force fixed positioning: parent: '#app' triggers nprogress.css's
   .nprogress-custom-parent rule which switches bar/spinner to position: absolute,
   making them invisible when the page is scrolled down. */
#nprogress .bar {
  background: var(--van-primary-color, #7c6bff) !important;
  height: 3px !important;
  position: fixed !important;
}

#nprogress .spinner {
  position: fixed !important;
}
```

The `!important` is necessary because NProgress's own CSS uses `!important` for these properties.

## Why This Works

NProgress adds the class `.nprogress-custom-parent` to its container when `parent` is configured. Its built-in CSS rule `.nprogress-custom-parent .bar { position: absolute }` is designed for scrollable containers (like overflow: auto divs), but `#app` is not a scroll container — the page itself scrolls. By overriding to `position: fixed`, the bar stays anchored to the viewport regardless of scroll position.

## Prevention

- When using `NProgress.configure({ parent: '#app' })` in a SPA where the page scrolls (not the app container), always add the `position: fixed` override.
- **Rule of thumb**: If your app container is NOT the scroll container (the window/document scrolls, not a div), you need this override.

## Related Issues

- Related NProgress issues: `docs/solutions/ui-bugs/nprogress-flicker-page-navigation.md` (lifecycle race), `docs/solutions/ui-bugs/nprogress-stuck-spinning-bypassed-guard.md` (child app guard flag)
