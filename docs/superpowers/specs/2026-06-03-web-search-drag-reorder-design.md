---
name: web-search-drag-reorder-status-enhancement
description: Add drag-to-reorder for enabled web search providers and enhance status display with visual health indicator and circuit reason
tags: [frontend, web-search, ux, mobile]
created: 2026-06-03
---

# Web Search Provider Drag-Reorder & Status Enhancement

## Overview

Add two features to the Web Search management page (`/settings/ai/web-search`):

1. **Drag-to-reorder** for enabled search providers to control search priority
2. **Enhanced status display** with visual health indicator and circuit reason text

## Requirements

### Requirement 1: Drag-to-reorder enabled providers

- Only enabled providers can be dragged to reorder
- Disabled providers remain in a static list below
- Order determines search priority (first enabled provider = highest priority)
- Reorder updates persist across sessions

### Requirement 2: Enhanced status display

- Visual health indicator (colored dot) showing circuit state
- Circuit reason text displayed when provider is in open/half_open state
- Clear visual distinction between healthy and unhealthy providers

## Architecture

### Files Modified

| File | Changes |
|------|---------|
| `frontend/apps/main/src/pages/WebSearchPage.vue` | Add vuedraggable, split enabled/disabled lists, enhanced status display |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add new i18n keys for drag/reorder |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | Add new i18n keys for drag/reorder |
| `frontend/apps/main/package.json` | Add `vuedraggable@next` dependency |

### No Backend Changes

Existing API already supports:
- `GET /ai/web-search` - returns providers sorted by `display_order`
- `PUT /ai/web-search/{id}` - accepts `display_order` in update payload
- `circuit_state` and `circuit_reason` fields already returned

## UI Design

### Enabled Providers List (Draggable)

```
┌─────────────────────────────────────────┐
│ 🔄 已启用的搜索源 (3)                    │  <- group title
├─────────────────────────────────────────┤
│ ⋮⋮  Google Search        🟢 正常   [开关]│  <- drag handle + green dot + badge + switch
│ ⋮⋮  Bing Search          🟡 半开   [开关]│  <- yellow dot + half_open badge
│     降级中                                │  <- circuit_reason text
│ ⋮⋮  Tavily               🔴 熔断   [开关]│  <- red dot + open badge
│     API错误                               │  <- circuit_reason text
└─────────────────────────────────────────┘
```

**Visual elements:**
- Drag handle icon (`⋮⋮`) on left for visual affordance
- Health indicator dot (8px colored circle)
- Circuit state badge (existing implementation)
- Circuit reason text (12px gray, below badge when present)
- Switch for enable/disable (existing)

### Disabled Providers List (Static)

```
┌─────────────────────────────────────────┐
│ 未配置的搜索源                           │
├─────────────────────────────────────────┤
│  SerpAPI        [配置]                  │  <- no drag, no status
│  DuckDuckGo     [配置]                  │
└─────────────────────────────────────────┘
```

### Health Indicator Colors

| State | Dot Color | Badge Color |
|-------|-----------|-------------|
| `closed` (healthy) | `var(--van-success-color)` green | green text |
| `half_open` (degraded) | `var(--van-warning-color)` yellow | yellow text |
| `open` (circuit breaker) | `var(--van-danger-color)` red | red text |

## Data Flow

### Drag Reorder Flow

```
User drags provider A to position B
    ↓
vuedraggable emits 'end' event
    ↓
Compute new display_order (0, 1, 2...) for all enabled providers
    ↓
Batch API calls: updateWebSearchProvider(id, { display_order })
    ↓
Success: toast "✅ 排序已更新"
Failure: toast "❌ 排序更新失败", reload from server
```

### State Management

- `enabledProviders` - computed array of enabled providers sorted by display_order
- `disabledProviders` - computed array of disabled/unconfigured providers
- Optimistic update on drag, confirm with API
- On failure, reload from server (no complex conflict resolution)

## Implementation Details

### Adding vuedraggable

```bash
cd frontend/apps/main
pnpm add vuedraggable@next
```

Usage in component:
```vue
<script setup>
import draggable from 'vuedraggable'
</script>

<template>
  <draggable
    v-model="enabledProviders"
    item-key="id"
    handle=".drag-handle"
    @end="onDragEnd"
  >
    <template #item="{ element }">
      <van-cell ... />
    </template>
  </draggable>
</template>
```

### Batch Update Strategy

On drag end:
1. Check if order actually changed (compare old vs new positions)
2. If changed, map each provider to its new `display_order` (index in array)
3. Call `updateWebSearchProvider(id, { display_order: newIndex })` for each
4. Use `Promise.all` for parallel updates
5. Handle failures with try/catch, reload on error

### i18n Keys to Add

**zh-CN.ts:**
```ts
webSearch: {
  reorderSuccess: '✅ 排序已更新',
  reorderFailed: '❌ 排序更新失败',
  enabledGroup: '已启用的搜索源',
  dragHint: '拖动调整优先级',
  circuitReasonTransient: '临时故障',
  circuitReasonApiError: 'API错误',
  circuitReasonTimeout: '超时',
}
```

**en-US.ts:**
```ts
webSearch: {
  reorderSuccess: '✅ Order updated',
  reorderFailed: '❌ Failed to update order',
  enabledGroup: 'Enabled search sources',
  dragHint: 'Drag to adjust priority',
  circuitReasonTransient: 'Transient error',
  circuitReasonApiError: 'API error',
  circuitReasonTimeout: 'Timeout',
}
```

## Error Handling

| Scenario | Handling |
|----------|----------|
| Network failure during reorder | Show error toast, reload from server |
| Single provider enabled | vuedraggable handles gracefully, no API call needed |
| Drag without position change | Skip API calls (order unchanged) |
| Concurrent reorder by another user | Last write wins, reload shows latest state |

## Testing

### Manual Testing Checklist

- [ ] Drag reorder works on mobile touch
- [ ] Drag reorder works on desktop mouse
- [ ] Order persists after page reload
- [ ] Disabled providers stay static
- [ ] Health indicator colors correct
- [ ] Circuit reason displays when present
- [ ] Error toast shows on network failure
- [ ] `pnpm typecheck` passes

## Out of Scope

- Animated drag preview (vuedraggable default is sufficient)
- Undo functionality for reorder
- Real-time circuit state updates (requires WebSocket/polling)
- Bulk enable/disable operations