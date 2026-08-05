---
date: 2026-08-05
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: medium
root_cause: css_issue
resolution_type: code_fix
symptoms:
  - "Action-sheet inside van-tabs animated swipeable appears empty but remains clickable"
  - "The popup backdrop and items are present in the DOM but clipped by the parent container"
  - "Clicking 'blind' still triggers item selection — the popup works but is visually hidden"
tags:
  - css-containing-block
  - teleport
  - van-tabs
  - van-action-sheet
  - transform
applies_when:
  - "CSS transform:translateZ(0) creates new containing block that clips popups"
  - "Vant popup/action-sheet inside swipeable tabs is invisible but clickable"
---

# Action-Sheet Clipped Inside van-tabs Swipeable

## Problem
The "操作类型" picker on `/ai/time-machine` rendered inside `<van-tabs animated swipeable>`, whose `transform: translateZ(0)` creates a new CSS containing block and `overflow: hidden` clips the popup. The action-sheet appeared empty but remained clickable.

## Symptoms
- Action-sheet popup on the WhatIfSimulator page renders but appears invisible
- The popup backdrop and items are present in the DOM but clipped by the parent container
- Clicking "blind" still triggers item selection — the popup works but is visually hidden

## What Didn't Work
- Increasing z-index on the action-sheet — the issue is a containing block / clipping problem, not z-index stacking
- Removing `overflow: hidden` from the tab container — breaks the swipe animation

## Solution
Add `teleport="body"` to the `van-action-sheet` component so it mounts on `<body>`, bypassing the Swipe containing block entirely.

**Before** (`frontend/apps/main/src/components/ai/WhatIfSimulator.vue`):
```vue
<van-action-sheet v-model:show="showPicker" :actions="actions" />
```

**After**:
```vue
<van-action-sheet v-model:show="showPicker" :actions="actions" teleport="body" />
```

## Why This Works
CSS `transform: translateZ(0)` creates a new containing block for `position: absolute` / `position: fixed` descendants. The `van-tabs animated swipeable` component uses this for GPU-accelerated swipe transitions. The action-sheet, positioned absolutely within the tab panel, is confined to the tab panel's bounding box. With `overflow: hidden` on the same container, the popup is clipped. `teleport="body"` moves the popup's DOM node to `<body>`, completely outside the transform/overflow clipping context.

## Prevention
- **Always use `teleport="body"` for Vant popups inside transformed containers** — any `van-popup`, `van-action-sheet`, `van-picker`, or `van-dialog` inside `<van-tabs animated>` or other `transform`-using parents needs teleport.
- **Test popups inside swipeable tabs specifically** — the containing block issue only manifests with CSS transforms, not with static-positioned parents.
