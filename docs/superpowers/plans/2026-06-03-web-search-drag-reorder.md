# Web Search Provider Drag-Reorder & Status Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add drag-to-reorder for enabled web search providers and enhance status display with visual health indicator and circuit reason text.

**Architecture:** Split providers into enabled (draggable via vuedraggable) and disabled (static) lists. Add health indicator dot and circuit reason text to each provider cell. On drag end, batch update display_order via existing API.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 + vuedraggable (already installed v4.1.0)

---

## File Structure

| File | Purpose |
|------|---------|
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add i18n keys for reorder messages, enabled group title, circuit reason labels |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | Add corresponding English translations |
| `frontend/apps/main/src/pages/WebSearchPage.vue` | Add vuedraggable for enabled providers, split lists, health indicator dot, circuit reason display |

**No new files needed.** vuedraggable already installed.

---

## Task 1: Add i18n Keys for zh-CN

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts:2325-2367` (webSearch section)

- [ ] **Step 1: Add new i18n keys to zh-CN.ts webSearch section**

Add these keys after `saveFailed: '❌ 保存失败',` (line 2367):

```ts
    reorderSuccess: '✅ 排序已更新',
    reorderFailed: '❌ 排序更新失败',
    enabledGroup: '已启用的搜索源',
    disabledGroup: '未配置的搜索源',
    dragHint: '拖动调整优先级',
    circuitReasonTransient: '临时故障',
    circuitReasonApiError: 'API错误',
    circuitReasonTimeout: '超时',
```

- [ ] **Step 2: Run typecheck to verify no syntax errors**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS (no new type errors)

- [ ] **Step 3: Commit i18n zh-CN changes**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts
git commit -m "feat(i18n): add web-search reorder and status i18n keys (zh-CN)"
```

---

## Task 2: Add i18n Keys for en-US

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts:2008-2052` (webSearch section)

- [ ] **Step 1: Add new i18n keys to en-US.ts webSearch section**

Add these keys after `saveFailed: '❌ Save failed',` (line 2049):

```ts
    reorderSuccess: '✅ Order updated',
    reorderFailed: '❌ Failed to update order',
    enabledGroup: 'Enabled search sources',
    disabledGroup: 'Unconfigured search sources',
    dragHint: 'Drag to adjust priority',
    circuitReasonTransient: 'Transient error',
    circuitReasonApiError: 'API error',
    circuitReasonTimeout: 'Timeout',
```

- [ ] **Step 2: Run typecheck to verify no syntax errors**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS (no new type errors)

- [ ] **Step 3: Commit i18n en-US changes**

```bash
git add frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(i18n): add web-search reorder and status i18n keys (en-US)"
```

---

## Task 3: Implement Drag-Reorder and Enhanced Status in WebSearchPage.vue

**Files:**
- Modify: `frontend/apps/main/src/pages/WebSearchPage.vue`

- [ ] **Step 1: Add vuedraggable import and computed properties for split lists**

Add import at top of `<script setup>`:

```ts
import draggable from 'vuedraggable'
```

Add computed properties after `enabledCount`:

```ts
const enabledProviders = computed(() =>
  providers.value.filter((p) => p.is_enabled).sort((a, b) => a.display_order - b.display_order),
)

const disabledProviders = computed(() => providers.value.filter((p) => !p.is_enabled))
```

Add reorder tracking ref:

```ts
const isReordering = ref(false)
```

- [ ] **Step 2: Add getCircuitReasonLabel helper function**

Add after `getCircuitColor`:

```ts
function getCircuitReasonLabel(reason: string | null) {
  if (!reason) return ''
  if (reason === 'transient') return t('webSearch.circuitReasonTransient')
  if (reason === 'api_error') return t('webSearch.circuitReasonApiError')
  if (reason === 'timeout') return t('webSearch.circuitReasonTimeout')
  return reason
}
```

- [ ] **Step 3: Add onDragEnd handler for reorder**

Add after existing handlers:

```ts
async function onDragEnd() {
  // Check if order actually changed
  const newOrder = enabledProviders.value.map((p) => p.id)
  const oldOrder = providers.value
    .filter((p) => p.is_enabled)
    .sort((a, b) => a.display_order - b.display_order)
    .map((p) => p.id)

  if (JSON.stringify(newOrder) === JSON.stringify(oldOrder)) {
    return // No change, skip API calls
  }

  isReordering.value = true
  try {
    // Batch update display_order (index = new order)
    const updates = enabledProviders.value.map((p, index) =>
      updateWebSearchProvider(p.id, { display_order: index }),
    )
    await Promise.all(updates)
    showToast(t('webSearch.reorderSuccess'))
    await load() // Refresh to confirm
  } catch {
    showToast(t('webSearch.reorderFailed'))
    await load() // Reload to restore correct state
  } finally {
    isReordering.value = false
  }
}
```

- [ ] **Step 4: Update template to split enabled/disabled lists with draggable**

Replace the existing `<van-cell-group :title="t('webSearch.subtitle')">` section with:

```vue
    <!-- Enabled providers - draggable -->
    <van-cell-group v-if="enabledProviders.length > 0" :title="t('webSearch.enabledGroup')">
      <div class="drag-hint">{{ t('webSearch.dragHint') }}</div>
      <draggable
        v-model="enabledProviders"
        item-key="id"
        handle=".drag-handle"
        :disabled="!isOwner"
        ghost-class="ghost-item"
        @end="onDragEnd"
      >
        <template #item="{ element: provider }">
          <van-cell
            :key="provider.id"
            :title="provider.display_name || provider.provider_name"
            :label="getTemplate(provider.provider_name)?.note"
            is-link
            @click="goToForm(undefined, provider.id)"
          >
            <template #icon>
              <div v-if="isOwner" class="drag-handle">
                <van-icon name="wap-nav" />
              </div>
            </template>
            <template #right-icon>
              <div class="provider-actions">
                <span
                  class="health-dot"
                  :style="{ background: getCircuitColor(provider.circuit_state) }"
                />
                <div class="status-info">
                  <span
                    class="circuit-badge"
                    :style="{ color: getCircuitColor(provider.circuit_state) }"
                  >
                    {{ getCircuitLabel(provider.circuit_state) }}
                  </span>
                  <span v-if="provider.circuit_reason" class="circuit-reason">
                    {{ getCircuitReasonLabel(provider.circuit_reason) }}
                  </span>
                </div>
                <van-switch
                  v-if="isOwner"
                  :model-value="provider.is_enabled"
                  size="20px"
                  @click.stop
                  @update:model-value="handleToggle(provider)"
                />
              </div>
            </template>
          </van-cell>
        </template>
      </draggable>
    </van-cell-group>

    <!-- Disabled providers - static list -->
    <van-cell-group :title="t('webSearch.disabledGroup')">
      <van-cell
        v-for="provider in disabledProviders"
        :key="provider.id"
        :title="provider.display_name || provider.provider_name"
        :label="getTemplate(provider.provider_name)?.note"
        is-link
        @click="goToForm(undefined, provider.id)"
      >
        <template #right-icon>
          <div class="provider-actions">
            <van-switch
              v-if="isOwner"
              :model-value="provider.is_enabled"
              size="20px"
              @click.stop
              @update:model-value="handleToggle(provider)"
            />
          </div>
        </template>
      </van-cell>
    </van-cell-group>
```

- [ ] **Step 5: Update styles for new elements**

Replace the existing `<style scoped>` section with:

```css
<style scoped>
.web-search-page {
  padding-bottom: 20px;
}

.status-bar {
  padding: 12px 16px;
  font-size: 14px;
}

.status-enabled {
  color: var(--van-success-color);
}

.status-disabled {
  color: var(--text-secondary);
}

.drag-hint {
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}

.drag-handle {
  display: flex;
  align-items: center;
  padding-right: 8px;
  cursor: grab;
  color: var(--text-secondary);
}

.drag-handle:active {
  cursor: grabbing;
}

.ghost-item {
  opacity: 0.5;
  background: var(--van-background);
}

.provider-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.circuit-badge {
  font-size: 12px;
}

.circuit-reason {
  font-size: 11px;
  color: var(--text-secondary);
}

.mcp-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
```

- [ ] **Step 6: Run typecheck to verify no type errors**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 7: Run dev server to visually verify**

Run: `cd frontend/apps/main && pnpm dev`
Manual check:
- Navigate to `/settings/ai/web-search`
- Verify enabled providers show drag handle
- Verify health dot colors match circuit state
- Verify circuit reason shows below badge when present
- Drag to reorder (if multiple enabled providers exist)
- Verify order persists after page reload

- [ ] **Step 8: Commit WebSearchPage.vue changes**

```bash
git add frontend/apps/main/src/pages/WebSearchPage.vue
git commit -m "feat(web-search): add drag-reorder and enhanced status display

- Split providers into enabled (draggable) and disabled (static) lists
- Add health indicator dot showing circuit state color
- Display circuit reason text when provider is in open/half_open state
- Batch update display_order on drag end with optimistic UI update"
```

---

## Task 4: Final Verification

- [ ] **Step 1: Run full typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: PASS

- [ ] **Step 2: Run linter**

Run: `cd frontend/apps/main && pnpm lint`
Expected: No errors

- [ ] **Step 3: Manual testing checklist**

Verify each item:
- [ ] Drag reorder works on mobile touch
- [ ] Drag reorder works on desktop mouse
- [ ] Order persists after page reload
- [ ] Disabled providers stay in static list (no drag handle)
- [ ] Health indicator colors: green (closed), yellow (half_open), red (open)
- [ ] Circuit reason displays when present
- [ ] Error toast shows on network failure (disconnect and try reorder)
- [ ] Single enabled provider: no crash, drag gracefully handled

---

## Self-Review Checklist

After implementing, verify:

1. **Spec coverage:** All requirements from spec implemented?
   - [ ] Drag-to-reorder enabled providers ✓ (Task 3)
   - [ ] Disabled providers remain static ✓ (Task 3)
   - [ ] Order persists ✓ (Task 3 - onDragEnd saves to API)
   - [ ] Health indicator dot ✓ (Task 3 - Step 5)
   - [ ] Circuit reason text ✓ (Task 3 - Step 2,4)
   - [ ] Clear visual distinction ✓ (Task 3 - Step 5 styles)

2. **Placeholder scan:** No TBD/TODO in plan? ✓

3. **Type consistency:** Function names match across steps?
   - `getCircuitReasonLabel` defined in Step 2, used in Step 4 ✓
   - `enabledProviders` / `disabledProviders` computed defined in Step 1, used in Step 4 ✓
   - `onDragEnd` defined in Step 3, used in Step 4 ✓