---
title: "Vite cache serves stale Vue version after lockfile upgrade"
date: 2026-09-09
category: developer-experience
module: frontend
problem_type: developer_experience
component: tooling
severity: medium
resolution_type: workflow_improvement
applies_when:
  - "After pnpm install upgrades Vue or Vant versions and the dev server is already running"
  - "After pulling a branch that changed Vue/Vant versions in the lockfile"
  - "Missing ref owner context warnings appear on Vant components with no code changes"
  - "KeepAlive stops detecting route changes despite the router resolving correctly"
tags:
  - vite-cache
  - vue-version
  - pnpm
  - dev-server
  - stale-cache
  - keepalive
  - vant
---

# Vite cache serves stale Vue version after lockfile upgrade

## Context

A Vue 3 + Vant 4 frontend (Numina family asset management) exhibited three symptoms simultaneously:

1. `[Vue warn]: Missing ref owner context. ref cannot be used on hoisted vnodes` warnings flooding the console — affecting Vant components: VanNavBar, VanSticky, VanSwipeCell, VanTabbar, VanDialog, and KeepAlive
2. Page switching broken: clicking bottom navigation tabbar changed the URL but page content didn't update
3. Settings page sub-options also didn't navigate

All Vant packages resolved to vant@4.10.2 (no duplicate versions) and the lockfile had vue@3.5.34. However, the browser runtime reported vue@3.5.33 — a version mismatch between lockfile and what the dev server actually served.

## Guidance

When Vue version warnings appear alongside broken component behavior (especially KeepAlive not detecting component changes or navigation failures), verify the runtime Vue version matches the lockfile:

```bash
# In browser console:
document.querySelector("#app").__vue_app__.version
```

If the runtime version is stale, clear all Vite dev server caches and restart:

```bash
rm -rf frontend/{apps,packages}/*/node_modules/.vite
# Then restart the dev server
```

Vite caches transformed modules aggressively. When a dependency version changes in the lockfile but the `.vite` cache isn't cleared, the dev server can continue serving the old version's code — causing subtle vnode/patchFlag incompatibilities between the runtime and compiled templates.

## Why This Matters

- **Silent breakage**: The app appears to load normally, but internal vnode mechanics (hoisting, patchFlags, shapeFlags) are mismatched. KeepAlive fails to detect component changes, so route transitions silently break while the router itself works correctly.
- **Misleading warnings**: "Missing ref owner context" warnings point developers toward template ref issues, when the real cause is a stale Vue runtime. Following the warnings leads to wasted time auditing component code.
- **Version alignment is a prerequisite**: Vant 4.10.2's compiled templates assume Vue 3.5.34's vnode hoisting behavior. Vue 3.5.33 had different behavior, causing internal template refs on hoisted vnodes to lose their owner context.

## When to Apply

- After `pnpm install` upgrades Vue or Vant versions and the dev server is already running
- After pulling a branch that changed Vue/Vant versions in the lockfile
- When "Missing ref owner context" warnings appear on Vant components with no code changes
- When KeepAlive stops detecting route/component changes despite the router resolving correctly
- When page navigation changes the URL but doesn't update the rendered content

## Examples

**Diagnosis:**
```bash
# Lockfile says:
grep "vue@" frontend/pnpm-lock.yaml  # → vue@3.5.34

# Browser console says:
document.querySelector("#app").__vue_app__.version  # → "3.5.33"

# Mismatch confirmed → cache issue
```

**Fix:**
```bash
rm -rf frontend/{apps,packages}/*/node_modules/.vite
pnpm dev  # Restart dev server
```

**Verification:**
```bash
# Browser console:
document.querySelector("#app").__vue_app__.version  # → "3.5.34" ✓
# Zero "Missing ref owner context" warnings ✓
# All tab bar navigation works ✓
```

**Related previous incident** (different root cause): Vant 4.9 vs 4.10 dual instances breaking provide/inject caused van-tabs white screen — solved by version deduplication, not cache clearing.

## Related

- [pnpm workspace duplicate Vant versions break van-tabs](../tooling-decisions/pnpm-workspace-duplicate-vant-provide-inject-broken.md) — different root cause (4.9 vs 4.10 dual instances) solved by version alignment rather than cache clearing
- [Vue 3 Transition + KeepAlive blank screen](../ui-bugs/vue3-transition-keepalive-blank-screen.md) — shares the KeepAlive/page-switching symptom but different root cause (Transition mode + dynamic :key)
- Both issues share the theme: Vant's internal template compilation is sensitive to Vue runtime version alignment
