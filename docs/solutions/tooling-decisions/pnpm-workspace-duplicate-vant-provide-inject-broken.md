---
title: "pnpm workspace duplicate Vant versions break van-tabs provide/inject via module-scoped Symbol keys"
date: 2026-09-09
category: tooling-decisions
module: frontend
problem_type: tooling_decision
component: tooling
severity: high
applies_when:
  - "Adding a new workspace package that shares a dependency with existing packages"
  - "Upgrading a dependency in one package but not others"
  - "White screens or silent rendering failures with component libraries using provide/inject"
  - "Bundle analysis shows unexpected duplicate modules"
tags:
  - pnpm
  - workspace
  - vant
  - vite
  - dedupe
  - provide-inject
  - duplicate-dependency
  - symbol-key
  - white-screen
---

# Pnpm Workspace Dependency Deduplication — Vant Duplicate Instance White Screen

## Context

Numina is a pnpm monorepo frontend with two Vue 3 apps (`apps/main` and `apps/child`) sharing a workspace root at `frontend/`. Both apps depend on Vant 4 (a Vue 3 mobile component library) and its companion `@vant/use` hooks package.

The workspace root `frontend/package.json` declared `vant: ^4.10.2`, while `frontend/apps/main/package.json` and `frontend/apps/child/package.json` each declared `vant: ^4.9.22`. Because the version ranges did not overlap, pnpm resolved two separate copies into the store: `vant@4.9.24` (satisfying the apps) and `vant@4.10.2` (satisfying the root). Both copies were installed, imported, and bundled independently.

The symptom was a white screen on `FinanceHubPage`: `van-tabs` rendered four empty tab panel containers with zero tab headers and zero content. No errors appeared in the console. The `titleList` property on the `van-tabs` proxy was `undefined`; `setupState` was empty. The only provide key was `Symbol(van-tabs)`, but the `van-tab` children were registering against a *different* `Symbol(van-tabs)` from the other installed copy, so parent never saw child registrations.

## Guidance

### Version alignment rule

In a pnpm workspace, every package that depends on the same library must declare a version range that resolves to a single installed copy. When ranges diverge, pnpm happily installs both — and any library that relies on module-level singletons (Symbols, module-scoped state, `instanceof` checks) will silently break.

**Rule:** shared component libraries, framework packages, and anything that uses provide/inject or module-level identity must be pinned to a single version range across all workspace packages. Prefer declaring the version once (at the workspace root via `pnpm.overrides` or a shared `workspace:*` protocol) rather than repeating it in each app.

### Vite `resolve.dedupe` configuration

Even when pnpm deduplicates correctly, Vite's module resolution can still serve two copies if the dependency is reachable via different paths in `node_modules`. Adding the package names to `resolve.dedupe` forces Vite to resolve them to a single module instance regardless of import path:

```ts
// vite.config.ts
export default defineConfig({
  resolve: {
    dedupe: ['vant', '@vant/use'],
  },
});
```

Both the library itself and any companion packages that share its Symbols (here `@vant/use`) must be listed. Apply this to every app's Vite config in the workspace.

### How to detect duplicates

Before assuming versions are aligned, verify on disk:

```sh
ls node_modules/.pnpm/vant@*/
```

If more than one version directory exists, duplicates are installed. Also check:

```sh
pnpm why vant          # shows which packages pull which version
pnpm ls vant -r        # lists vant across all workspace packages
```

After fixing versions, run `pnpm install` and re-check that only one version remains.

### Why Symbol-based provide/inject breaks with duplicates

Vant's `van-tabs` component creates its provide key as `Symbol('van-tabs')` at module evaluation time. Each installed copy of the Vant module evaluates this expression independently, producing two distinct Symbol values. When `van-tabs` (from copy A) calls `provide(Symbol_A, ...)`, and `van-tab` (from copy B) calls `inject(Symbol_B, ...)`, the inject returns `undefined` because `Symbol_A !== Symbol_B`. The parent sees zero children; the children see no parent context. No error is thrown — registration simply never connects.

This pattern affects any library using module-level Symbols for coordination: Vant, Element Plus, Headless UI, and many Vue composition-api libraries.

## Why This Matters

**When followed:** all workspace apps share a single Vant instance. `van-tabs`, `van-popup`, `van-dialog`, and every other coordination-based component works correctly. Provide/inject chains connect. Vite bundles one copy, reducing bundle size.

**When not followed:** white screens with zero console errors. Tab headers disappear. Popups fail to open. Modals render in place instead of overlaying. The failure is silent because Symbol mismatches produce `undefined` from inject, not exceptions. Debugging leads down rabbit holes of component lifecycle, slot rendering, and reactivity — the real cause (two module instances) is invisible in DevTools unless you compare `Symbol.keyFor()` output across the parent and child.

The cost of not following this is disproportionate: a one-line version mismatch can consume hours of debugging because the symptom (empty component) has dozens of plausible causes and the actual cause (module duplication) is not checkable from component state alone.

## When to Apply

- Adding a new workspace package that shares a dependency with existing packages (especially component libraries, state libraries, or anything using provide/inject).
- Upgrading a dependency in one package but not others — always check whether the upgrade creates a second installed copy.
- When white screens or silent rendering failures appear with component libraries that use provide/inject or module-level singletons.
- When bundle analysis shows unexpected duplicate modules.
- After `pnpm install` reports large changes in package count — verify no critical dependency was duplicated.

## Examples

### Before — divergent versions

`frontend/package.json` (workspace root):
```json
{
  "dependencies": {
    "vant": "^4.10.2"
  }
}
```

`frontend/apps/main/package.json`:
```json
{
  "dependencies": {
    "vant": "^4.9.22"
  }
}
```

`frontend/apps/child/package.json`:
```json
{
  "dependencies": {
    "vant": "^4.9.22"
  }
}
```

Result: pnpm installs both `vant@4.9.24` and `vant@4.10.2`. Two module instances. `Symbol('van-tabs')` evaluated twice. White screen.

### After — aligned versions + dedupe

`frontend/apps/main/package.json`:
```json
{
  "dependencies": {
    "vant": "^4.10.2"
  }
}
```

`frontend/apps/child/package.json`:
```json
{
  "dependencies": {
    "vant": "^4.10.2"
  }
}
```

`frontend/apps/main/vite.config.ts`:
```ts
export default defineConfig({
  resolve: {
    dedupe: ['vue', 'pinia', '@vue/runtime-dom', '@vue/runtime-core',
             'vue-i18n', '@intlify/core-base', '@intlify/shared',
             'vant', '@vant/use'],
  },
});
```

Then:
```sh
pnpm install          # Packages: +2 -3 — one vant copy removed
# Kill old Vite dev server and restart to pick up new resolution
```

Verification: `ls node_modules/.pnpm/vant@*/` shows a single version directory. All tabs, popups, and inject-dependent components render correctly.

## Related

- Commit `4821c1e0` — previous white-screen fix applying the same `resolve.dedupe` pattern to `@vue/runtime-dom` in a different context. The recurrence confirms this is a structural risk in any workspace that shares framework or component-library dependencies.
- `docs/solutions/ui-bugs/vue3-transition-keepalive-blank-screen.md` — similar blank-screen symptom but different root cause (Transition+KeepAlive+key issues).
- `docs/solutions/ui-bugs/vant4-field-modelvalue-binding-2026-04-08.md` — Vant 4 binding issue, different problem.
