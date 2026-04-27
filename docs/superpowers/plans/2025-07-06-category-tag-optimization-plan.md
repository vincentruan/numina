# Category Tag Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize dashboard asset list category tabs to show asset counts, filter by category, and remove unnecessary UI elements.

**Architecture:** Client-side filtering using computed properties. Extend existing sticky tabs pattern. Remove legacy view/category toggles that conflict with pagination.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 + Pinia

---

## File Structure

| File | Responsibility |
|------|----------------|
| `frontend/src/pages/DashboardPage.vue` | Single file for all changes - sticky tabs, filtering logic, UI cleanup |

---

### Task 1: Remove Old UI Elements

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue:87-99` (section-header)

- [ ] **Step 1: Remove "查看全部" link**

Remove lines 89 from template section:
```vue
<!-- DELETE THIS LINE -->
<router-link to="/assets" class="view-all">查看全部 &gt;</router-link>
```

- [ ] **Step 2: Remove view-toggle span**

Remove lines 91-94 from template section:
```vue
<!-- DELETE THESE LINES -->
<span class="view-toggle" :aria-label="viewMode === 'card' ? '切换列表视图' : '切换卡片视图'" @click="toggleViewMode">
  <svg v-if="viewMode === 'card'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
</span>
```

- [ ] **Step 3: Remove category-toggle span**

Remove lines 95-97 from template section:
```vue
<!-- DELETE THESE LINES -->
<span class="category-toggle" @click="toggleCategoryView">
  {{ showCategoryGroups ? '列表' : '分类' }}
</span>
```

- [ ] **Step 4: Remove section-actions wrapper**

Remove the `<div class="section-actions">` wrapper and its contents (lines 90-98):
```vue
<!-- DELETE THIS BLOCK -->
<div class="section-actions">
  <span class="view-toggle" ...>...</span>
  <span class="category-toggle" ...>...</span>
</div>
```

After removal, section-header should only contain:
```vue
<div class="section-header">
  <span class="section-title">{{ sectionTitle }}</span>
</div>
```

- [ ] **Step 5: Remove toggleViewMode function**

Remove lines 507-509 from script section:
```typescript
// DELETE THIS FUNCTION
function toggleViewMode() {
  viewMode.value = viewMode.value === 'card' ? 'list' : 'card'
}
```

- [ ] **Step 6: Remove toggleCategoryView function**

Remove lines 511-518 from script section:
```typescript
// DELETE THIS FUNCTION
function toggleCategoryView() {
  showCategoryGroups.value = !showCategoryGroups.value
  if (showCategoryGroups.value) {
    showToast(t('toast.switchedToCategoryView'))
  } else {
    showToast(t('toast.switchedToListView'))
  }
}
```

- [ ] **Step 7: Remove showCategoryGroups ref**

Remove line 300 from script section:
```typescript
// DELETE THIS LINE
const showCategoryGroups = ref(false)
```

- [ ] **Step 8: Remove viewMode ref**

Remove line 288 from script section:
```typescript
// DELETE THIS LINE
const viewMode = ref<'card' | 'list'>('card')
```

- [ ] **Step 9: Remove groupedByCategory computed**

Remove lines 484-505 from script section:
```typescript
// DELETE THIS COMPUTED
const groupedByCategory = computed(() => {
  const groups = new Map<string, { id: string; name: string; icon: string; assets: Asset[] }>()

  sortedAndFilteredAssets.value.forEach(asset => {
    const categoryId = asset.category_id
    const category = asset.category || categories.value.find(c => c.id === categoryId)

    if (category) {
      if (!groups.has(categoryId)) {
        groups.set(categoryId, {
          id: categoryId,
          name: category.name,
          icon: category.icon,
          assets: []
        })
      }
      groups.get(categoryId)!.assets.push(asset)
    }
  })

  return Array.from(groups.values())
})
```

- [ ] **Step 10: Remove Category Grouped View template block**

Remove lines 102-126 from template section:
```vue
<!-- DELETE THIS BLOCK -->
<!-- Category Grouped View -->
<template v-if="showCategoryGroups && groupedByCategory.length">
  <div v-for="group in groupedByCategory" :key="group.id" class="category-group">
    <div class="category-group-header">
      <span class="category-icon">{{ group.icon }}</span>
      <span class="category-name">{{ group.name }}</span>
      <span class="category-count">({{ group.assets.length }})</span>
    </div>
    <div v-if="viewMode === 'card'" class="asset-list">
      <AssetCard
        v-for="asset in group.assets"
        :key="asset.id"
        :asset="asset"
        @click="$router.push(`/assets/${asset.id}`)"
      />
    </div>
    <div v-else class="asset-list-compact">
      <AssetListItem
        v-for="asset in group.assets"
        :key="asset.id"
        :asset="asset"
        @click="$router.push(`/assets/${asset.id}`)"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 11: Simplify Normal List View to only use card view**

Modify lines 129-153 to remove `v-if="viewMode === 'card'"` condition and remove list view branch:

Replace:
```vue
<template v-else-if="sortedAndFilteredAssets.length">
  <van-list
    v-model:loading="loadingMore"
    :finished="dashboardStore.assetListFinished"
    finished-text="没有更多了"
    @load="onLoadMore"
  >
    <div v-if="viewMode === 'card'" class="asset-list">
      <AssetCard
        v-for="asset in dashboardStore.displayedAssets"
        :key="asset.id"
        :asset="asset"
        @click="$router.push(`/assets/${asset.id}`)"
      />
    </div>
    <div v-else class="asset-list-compact">
      <AssetListItem
        v-for="asset in dashboardStore.displayedAssets"
        :key="asset.id"
        :asset="asset"
        @click="$router.push(`/assets/${asset.id}`)"
      />
    </div>
  </van-list>
</template>
```

With:
```vue
<template v-else-if="filteredByCategoryAssets.length">
  <van-list
    v-model:loading="loadingMore"
    :finished="dashboardStore.assetListFinished"
    finished-text="没有更多了"
    @load="onLoadMore"
  >
    <div class="asset-list">
      <AssetCard
        v-for="asset in filteredByCategoryAssets"
        :key="asset.id"
        :asset="asset"
        @click="$router.push(`/assets/${asset.id}`)"
      />
    </div>
  </van-list>
</template>
```

- [ ] **Step 12: Remove related CSS styles**

Remove from style section:
```css
/* DELETE THESE CSS BLOCKS */
.view-toggle,
.category-toggle {
  font-size: 13px;
  color: var(--color-action-primary);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(21, 101, 192, 0.1);
}
[data-theme='dark'] .view-toggle,
[data-theme='dark'] .category-toggle {
  background: rgba(21, 101, 192, 0.15);
}
.view-toggle:active,
.category-toggle:active {
  opacity: 0.7;
}

/* Category Group */
.category-group {
  margin-bottom: 16px;
}
.category-group-header {
  display: flex;
  align-items: center;
  padding: 12px 8px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 8px;
  margin-bottom: 8px;
}
[data-theme='dark'] .category-group-header {
  background: linear-gradient(135deg, #2a2a2a 0%, #1f1f1f 100%);
}
.category-icon {
  font-size: 20px;
  margin-right: 8px;
}
.category-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.category-count {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

.asset-list-compact {
  background: var(--card-bg);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}
[data-theme='dark'] .asset-list-compact {
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}
```

- [ ] **Step 13: Commit UI cleanup changes**

```bash
git add frontend/src/pages/DashboardPage.vue
git commit -m "refactor: remove view toggle and category group UI from dashboard

- Remove '查看全部' link (pagination handles this)
- Remove card/list view toggle (conflicts with pagination)
- Remove category group toggle (conflicts with pagination)
- Simplify to single card view layout

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Add Category Filtering Logic

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue` (script section, after line 288)

- [ ] **Step 1: Add activeCategoryId ref**

Add after line 287 (after `const viewMode` which will be deleted):
```typescript
const activeCategoryId = ref<string | null>(null)  // null = show all
```

- [ ] **Step 2: Add categoriesWithAssetCount computed**

Add after `const categories` computed (around line 316):
```typescript
// Filter and sort categories by asset count (descending)
const categoriesWithAssetCount = computed(() => {
  const allAssets = dashboardStore.displayedAssets
  const counts = new Map<string, number>()

  // Count assets per category
  allAssets.forEach(asset => {
    const catId = asset.category_id
    counts.set(catId, (counts.get(catId) || 0) + 1)
  })

  // Filter categories with assets and sort by count descending
  return categories.value
    .filter(cat => counts.get(cat.id) > 0)
    .map(cat => ({
      id: cat.id,
      name: cat.name,
      icon: cat.icon,
      count: counts.get(cat.id) || 0
    }))
    .sort((a, b) => b.count - a.count)
})
```

- [ ] **Step 3: Add filteredByCategoryAssets computed**

Add after `categoriesWithAssetCount`:
```typescript
// Filter displayed assets by selected category
const filteredByCategoryAssets = computed(() => {
  if (!activeCategoryId.value) {
    return dashboardStore.displayedAssets
  }
  return dashboardStore.displayedAssets.filter(asset => asset.category_id === activeCategoryId.value)
})
```

- [ ] **Step 4: Modify onCategoryChange function**

Replace existing `onCategoryChange` function (lines 520-527):
```typescript
// Old function to replace:
function onCategoryChange(index: number) {
  activeCategoryIndex.value = index
  // Scroll to the category group
  const categoryGroups = document.querySelectorAll('.category-group')
  if (categoryGroups[index]) {
    categoryGroups[index].scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// New function:
function onCategoryChange(index: number) {
  activeCategoryIndex.value = index
  if (index === 0) {
    activeCategoryId.value = null  // "全部" tab
  } else {
    const category = categoriesWithAssetCount.value[index - 1]
    activeCategoryId.value = category.id
  }
}
```

- [ ] **Step 5: Run typecheck to verify**

```bash
cd frontend && npm run typecheck
```

Expected: No TypeScript errors

- [ ] **Step 6: Commit filtering logic**

```bash
git add frontend/src/pages/DashboardPage.vue
git commit -m "feat: add category filtering logic for dashboard tabs

- Add activeCategoryId ref for category selection
- Add categoriesWithAssetCount computed (sorted by count desc)
- Add filteredByCategoryAssets computed for filtering
- Update onCategoryChange to set category filter

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Update Sticky Tabs UI

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue:79-83` (template section)

- [ ] **Step 1: Modify sticky tabs condition and add "全部" tab**

Replace lines 79-83:
```vue
<!-- OLD CODE -->
<div v-if="showCategoryNav && categories.length > 1" class="category-nav-sticky">
  <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
    <van-tab v-for="(cat, index) in categories" :key="cat.id" :title="cat.name" />
  </van-tabs>
</div>

<!-- NEW CODE -->
<div v-if="showCategoryNav && categoriesWithAssetCount.length > 0" class="category-nav-sticky">
  <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
    <van-tab title="全部" />
    <van-tab v-for="cat in categoriesWithAssetCount" :key="cat.id" :title="`${cat.name} (${cat.count})`" />
  </van-tabs>
</div>
```

- [ ] **Step 2: Update empty state condition**

Modify line 155 to use `filteredByCategoryAssets`:
```vue
<!-- OLD -->
<van-empty v-else description="暂无资产" image-size="60" />

<!-- NEW -->
<van-empty v-else-if="!filteredByCategoryAssets.length" description="暂无资产" image-size="60" />
```

- [ ] **Step 3: Run typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: No TypeScript errors

- [ ] **Step 4: Commit sticky tabs update**

```bash
git add frontend/src/pages/DashboardPage.vue
git commit -m "feat: update sticky tabs to show asset counts

- Add '全部' tab as first option
- Show category name with count: '房产 (3)'
- Filter to only show categories with assets > 0
- Sort categories by count descending

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Final Cleanup and Testing

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue`

- [ ] **Step 1: Remove unused imports**

Check if `AssetListItem` is still used. If not, remove from imports (line 273):
```typescript
// If AssetListItem is no longer used anywhere, remove:
import AssetListItem from '@/components/asset/AssetListItem.vue'
```

- [ ] **Step 2: Remove unused watch for view_mode**

Remove lines 785-789 (watch for user view_mode settings):
```typescript
// DELETE THIS WATCH
watch(() => authStore.user?.view_mode, (newMode) => {
  if (newMode === 'list' || newMode === 'card') {
    viewMode.value = newMode
  }
})
```

- [ ] **Step 3: Remove view_mode initialization in onMounted**

Remove lines 769-771 from `onMounted`:
```typescript
// DELETE THESE LINES
if (authStore.user?.view_mode === 'list') {
  viewMode.value = 'list'
}
```

- [ ] **Step 4: Run full typecheck**

```bash
cd frontend && npm run typecheck
```

Expected: Pass with no errors

- [ ] **Step 5: Manual testing - Open dashboard page**

Start dev server:
```bash
cd frontend && npm run dev
```

Navigate to `http://localhost:5173/` (or appropriate port) and verify:
- Sticky tabs appear when scrolling past overview card
- "全部" tab is first
- Category tabs show count like "房产 (3)"
- Tabs sorted by count descending
- Clicking tabs filters asset list
- No "查看全部" link
- No view toggle buttons

- [ ] **Step 6: Commit final cleanup**

```bash
git add frontend/src/pages/DashboardPage.vue
git commit -m "refactor: remove unused imports and view_mode code

- Remove AssetListItem import (unused after simplification)
- Remove view_mode watch and initialization
- Clean up unused refs and watchers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Acceptance Criteria Verification

After all tasks complete, verify:

- [ ] Sticky tabs show "全部" and categories with counts
- [ ] Categories sorted by count descending
- [ ] Zero-asset categories not shown
- [ ] Tab click filters asset list correctly
- [ ] Pagination works with filtered assets
- [ ] "查看全部" and toggle buttons removed
- [ ] No console errors
- [ ] `npm run typecheck` passes

---

## Total Commits

1. `refactor: remove view toggle and category group UI from dashboard`
2. `feat: add category filtering logic for dashboard tabs`
3. `feat: update sticky tabs to show asset counts`
4. `refactor: remove unused imports and view_mode code`