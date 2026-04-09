---
title: "Vant 4 van-field requires :model-value not :value for reactive display"
date: 2026-04-08
module: frontend
component: frontend_stimulus
problem_type: ui_bug
severity: high
symptoms:
  - "van-field with :value binding shows initial value but does not update after computed changes"
  - "Category picker selection has no visible effect on the field row"
  - "Reactive computed string updates are silently ignored by the component"
root_cause: wrong_api
resolution_type: code_fix
tags: [vant4, vue3, v-model, model-value, van-field, reactivity, picker]
---

# Vant 4 van-field requires :model-value not :value for reactive display

## Problem

In Vant 4, binding a computed string to `van-field` with `:value` causes the field to display the initial value but never update when the computed changes. The fix is to use `:model-value` instead, which maps to the prop Vant 4 actually watches.

## Symptoms

- `van-field` shows the correct initial value but ignores all subsequent reactive updates
- Selecting an item from a popup and updating the backing `ref` has no visible effect on the field row
- No Vue warnings or console errors — the binding silently does nothing

## What Didn't Work

- **`:value="selectedCategoryName"`** — Maps to a prop that Vant 4 does not wire to its internal display update path. The field renders once on mount and then freezes.
- **`v-model` on a readonly computed** — Not applicable; `v-model` requires a writable ref. For display-only fields driven by a computed, `:model-value` is the correct one-way binding.

## Solution

Change `:value` to `:model-value` on any `van-field` that displays a computed or reactive string:

```vue
<!-- Before: field freezes after initial render -->
<van-field
  :value="selectedCategoryName"
  is-link
  readonly
  label="分类"
  placeholder="请选择分类"
  @click="showCategoryPicker = true"
/>

<!-- After: field updates reactively -->
<van-field
  :model-value="selectedCategoryName"
  is-link
  readonly
  label="分类"
  placeholder="请选择分类"
  @click="showCategoryPicker = true"
/>
```

The computed driving the field should search the full source array, not a filtered subset, to handle edit-mode pre-population correctly:

```ts
// ✓ Searches all categories — works in edit mode before filtered list is ready
const selectedCategoryName = computed(() => {
  const cat = props.categories.find(c => c.id === form.value.category_id)
  return cat?.name ?? ''
})

// ✗ Searches only filtered — blank label in edit mode during async load window
const selectedCategoryName = computed(() =>
  filteredCategories.value.find(c => c.id === form.value.category_id)?.name ?? ''
)
```

## Why This Works

Vue 3 components use `modelValue` as the canonical prop name for v-model binding. Vant 4 follows this convention: `van-field` internally declares `modelValue` as its prop and watches it for display updates. The `:value` shorthand maps to a different prop (`value`) that Vant 4 does not watch — so the field renders once on mount and ignores all subsequent changes.

In plain HTML `<input :value="x">` works because the DOM `value` attribute is directly reactive. Vant 4 components are not DOM elements; they follow the Vue 3 component prop contract where the reactive display prop is always `modelValue`.

## Prevention

- **Always use `:model-value` (or `v-model`) for Vant 4 component bindings**, never `:value`. The `:value` prop exists on some Vant components for legacy reasons but is not the reactive display path.
- **Pattern for read-only picker fields** (date, status, category): use `van-field` with `:model-value` + `readonly` + `is-link` + `@click` to open a popup. This is the established pattern in Vant 4 for tap-to-open pickers.
- **Avoid `van-picker` for custom icon rendering**: Vant 4's `van-picker` does not expose an `option` slot for individual item customization. Use a plain `div` grid inside `van-popup` when items need icons or custom layout.
- **Popup content scroll**: when a popup contains a grid with many items (e.g. 13 categories), add `max-height: 60vh; overflow-y: auto` to the inner container to prevent clipping on small screens.

## Related Issues

- `frontend/src/components/asset/AssetForm.vue` — category picker implementation
- `frontend/src/utils/icon.ts` — shared `getIconId()` utility extracted during this fix
