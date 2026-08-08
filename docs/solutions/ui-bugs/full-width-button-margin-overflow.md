---
date: 2026-08-05
module: frontend
problem_type: ui_bug
component: frontend_stimulus
severity: low
root_cause: css_issue
resolution_type: code_fix
symptoms:
  - "Family page action buttons overflow viewport on narrow screens"
  - "Horizontal scrollbar appears on mobile viewport"
  - "Last few pixels of button text are cut off"
tags:
  - css-box-model
  - width-100-percent
  - margin-overflow
  - parent-padding
applies_when:
  - "width: 100% combined with horizontal margin causes overflow"
  - "Full-width buttons extend beyond viewport edge on narrow screens"
---

# Family Page Action Buttons Overflow Viewport

## Problem
Full-width buttons (`width: 100%`) with horizontal `margin: 0 16px` totaled `100% + 32px`, overflowing the viewport on narrow screens.

## Symptoms
- Action buttons on the Family page (regenerate invite code, add child) extend beyond the right edge of the screen
- Horizontal scrollbar appears on mobile viewport
- Last few pixels of button text are cut off

## What Didn't Work
- `box-sizing: border-box` — already set, but margin is outside the box
- Reducing button width to `calc(100% - 32px)` — works but is fragile and not semantic

## Solution
Wrap buttons in a padding div so the block button fills the padded interior instead.

**Before**:
```vue
<van-button type="primary" block style="margin: 0 16px">
  {{ t('family.regenerateInviteCode') }}
</van-button>
```

**After**:
```vue
<div class="section-action">
  <van-button type="primary" block>
    {{ t('family.regenerateInviteCode') }}
  </van-button>
</div>
```
```css
.section-action { padding: 0 16px; }
```

## Why This Works
CSS box model: `width: 100%` + `margin: 0 16px` = `100% + 32px` total width. By moving the horizontal spacing to a parent container's `padding`, the `width: 100%` button fills the parent's content area (which is already inset by the padding). This is the standard CSS solution for full-width elements within padded containers.

## Prevention
- **Never combine `width: 100%` with horizontal `margin`** — use parent padding instead.
- **Test on narrow viewports** (320px) — overflow issues only manifest on small screens.
