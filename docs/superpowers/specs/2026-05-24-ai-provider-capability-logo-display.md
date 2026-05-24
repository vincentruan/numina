---
name: ai-provider-capability-logo-display
description: Replace text badges with icon chips for capability display in AIProviderFormPage
created: 2026-05-24
status: approved
---

# AI Provider Form Capability Logo Display

## Problem

In `AIProviderFormPage.vue`, selected capabilities display as text badges ("文本生成", "深度思考", "视觉理解").
User wants them to display as logo icons like in `AIConfigPage.vue` provider cards.

## Solution

Replace text badges with icon chips using same SVG patterns from `AIConfigPage.vue`.

### Template Change

Before:
```vue
<span class="cap-preview__badge">{{ capLabel(cap) }}</span>
```

After:
```vue
<span class="cap-preview__chip" :title="capLabel(cap)">
  <!-- SVG icon for each capability -->
</span>
```

### CSS Change

Replace `.cap-preview__badge` text styling with `.cap-preview__chip` icon container:
- 24x24px size
- 6px border-radius
- Colored backgrounds matching existing palette
- Centered SVG icons (12x12)

## Files

- `frontend/apps/main/src/pages/AIProviderFormPage.vue`

## Verification

Visual check in browser: capability preview in form should show icons, not text.