---
date: 2026-08-05
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: high
root_cause: logic_error
resolution_type: code_fix
symptoms:
  - "Blank screen after back navigation from sub-pages (Devices, ChangePassword) to cached tab pages"
  - "Router-view renders nothing permanently — no content, no error"
  - "Affects all sub-page → cached-tab navigation flows"
tags:
  - vue3-transition
  - keepalive
  - router-view
applies_when:
  - "Vue 3 Transition + KeepAlive + dynamic :key combination causes blank router-view"
  - "Navigate from cached tab to non-cached sub-page and back → blank screen"
---

# Vue 3 Transition + KeepAlive + :key Blank Screen

## Problem

The `<Transition mode="out-in">` + `<KeepAlive>` + `:key="route.path"` combination in `MainLayout.vue` caused a Vue 3 rendering bug where navigating back from any non-cached sub-page to a cached tab page left the `<router-view>` permanently blank.

## Symptoms
- Navigate from Dashboard (cached tab) to Devices (non-cached sub-page), then press back
- Router-view renders nothing permanently — no content, no error
- Affects all sub-page → cached-tab navigation flows

## What Didn't Work
- Keeping `mode="out-in"` and adjusting transition duration — the issue is structural, not timing
- Switching to `mode="in-out"` — same blank result because the leave transition never completes for KeepAlive components

## Solution
Remove the `<Transition>` wrapper and the dynamic `:key` entirely. KeepAlive handles caching without transition animation.

**Before** (`frontend/apps/main/src/layouts/MainLayout.vue`):
```vue
<router-view v-slot="{ Component, route }">
  <Transition name="page-fade" mode="out-in">
    <KeepAlive :include="cachedTabs">
      <component :is="Component" :key="route.path" />
    </KeepAlive>
  </Transition>
</router-view>
```

**After**:
```vue
<router-view v-slot="{ Component }">
  <KeepAlive :include="cachedTabs">
    <component :is="Component" />
  </KeepAlive>
</router-view>
```

## Why This Works
Vue 3's `<Transition mode="out-in">` waits for the leaving component's transition to finish before mounting the entering component. When combined with `<KeepAlive>`, the "leaving" component is deactivated (not destroyed), and the transition's `afterLeave` hook may never fire for certain deactivation paths — specifically when navigating back from a non-cached page to a cached one. The `:key="route.path"` exacerbates this by forcing Vue to treat every route as a distinct component instance, breaking KeepAlive's name-based cache matching. Removing both the Transition and the dynamic key lets KeepAlive manage the component lifecycle directly.

## Prevention
- **Avoid `<Transition mode="out-in">` + `<KeepAlive>` + `:key` combinations** in Vue 3. If page transitions are needed, use `mode="default"` (simultaneous) or apply transitions per-component via `onMounted`/`onActivated` hooks.
- **Test all navigation paths**: tab→sub-page→back, tab→tab, sub-page→sub-page. The blank-screen bug only manifests on specific navigation directions.
