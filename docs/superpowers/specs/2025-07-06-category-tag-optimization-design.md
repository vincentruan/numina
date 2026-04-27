# 资产分类标签优化设计

**日期**: 2025-07-06
**状态**: 待实施
**方案**: Approach A - 扩展现有sticky tabs

---

## 概述

优化总览页资产列表上的分类标签功能，实现：
1. 显示每个分类的资产数量
2. 默认展示资产数量>0的分类，按数量降序排列
3. 点击标签筛选对应分类的资产
4. 移除"查看全部"、"分类/列表切换"按钮

---

## UI变更

### 修改区域：Sticky Category Tabs (DashboardPage.vue lines 79-83)

**现有代码**:
```vue
<div v-if="showCategoryNav && categories.length > 1" class="category-nav-sticky">
  <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
    <van-tab v-for="(cat, index) in categories" :key="cat.id" :title="cat.name" />
  </van-tabs>
</div>
```

**修改后**:
```vue
<div v-if="showCategoryNav && categoriesWithAssetCount.length > 0" class="category-nav-sticky">
  <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
    <van-tab title="全部" />
    <van-tab v-for="cat in categoriesWithAssetCount" :key="cat.id" :title="`${cat.name} (${cat.count})`" />
  </van-tabs>
</div>
```

### 移除元素

| 元素 | 位置 | 原因 |
|------|------|------|
| `<router-link to="/assets" class="view-all">` | line 89 | 分页已实现，不需要跳转查看全部 |
| `<span class="view-toggle">` | lines 91-94 | 列表/卡片切换影响分页体验 |
| `<span class="category-toggle">` | lines 95-97 | 分类分组与分页冲突 |

---

## 数据流

### 新增Computed: `categoriesWithAssetCount`

```typescript
const categoriesWithAssetCount = computed(() => {
  const allAssets = dashboardStore.displayedAssets
  const counts = new Map<string, number>()

  // 统计每个分类的资产数量
  allAssets.forEach(asset => {
    const catId = asset.category_id
    counts.set(catId, (counts.get(catId) || 0) + 1)
  })

  // 过滤并排序
  return categories.value
    .filter(cat => counts.get(cat.id) > 0)  // 只显示有资产的分类
    .map(cat => ({
      id: cat.id,
      name: cat.name,
      icon: cat.icon,
      count: counts.get(cat.id) || 0
    }))
    .sort((a, b) => b.count - a.count)  // 按数量降序
})
```

### 新增Ref: `activeCategoryId`

```typescript
const activeCategoryId = ref<string | null>(null)  // null表示"全部"
```

### 修改Computed: `filteredByCategoryAssets`

```typescript
const filteredByCategoryAssets = computed(() => {
  if (!activeCategoryId.value) {
    return dashboardStore.displayedAssets  // 显示全部
  }
  return dashboardStore.displayedAssets.filter(asset => asset.category_id === activeCategoryId.value)
})
```

---

## 交互行为

### Tab点击逻辑

| Tab | 行为 |
|-----|------|
| "全部" (index 0) | `activeCategoryId = null`, 显示所有资产 |
| 分类Tab (index > 0) | `activeCategoryId = categoriesWithAssetCount[index-1].id`, 筛选该分类 |

```typescript
function onCategoryChange(index: number) {
  activeCategoryIndex.value = index
  if (index === 0) {
    activeCategoryId.value = null  // 全部
  } else {
    const category = categoriesWithAssetCount.value[index - 1]
    activeCategoryId.value = category.id
  }
}
```

### 分页集成

- **客户端筛选**: 使用 `filteredByCategoryAssets` 作为 `van-list` 的数据源
- 当切换分类时，`van-list` 自动重新渲染筛选后的资产
- 不需要修改后端API（MVP方案）

---

## 实现步骤

### Step 1: 移除旧UI元素
- 删除 `<router-link class="view-all">` (line 89)
- 删除 `<span class="view-toggle">` (lines 91-94)
- 删除 `<span class="category-toggle">` (lines 95-97)
- 删除 `toggleViewMode()` 和 `toggleCategoryView()` 函数

### Step 2: 修改sticky tabs
- 修改条件: `categories.length > 1` → `categoriesWithAssetCount.length > 0`
- 添加"全部"Tab
- 修改分类Tab标题显示数量

### Step 3: 添加筛选逻辑
- 添加 `activeCategoryId` ref
- 添加 `categoriesWithAssetCount` computed
- 添加 `filteredByCategoryAssets` computed
- 修改 `onCategoryChange()` 函数

### Step 4: 更新van-list数据源
- 将 `dashboardStore.displayedAssets` 替换为 `filteredByCategoryAssets`

### Step 5: 清理无用代码
- 移除 `showCategoryGroups` ref
- 移除 `groupedByCategory` computed
- 移除 `viewMode` ref（如果只保留卡片视图）

---

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `frontend/src/pages/DashboardPage.vue` | 修改 | 主要变更文件 |

---

## 验收标准

- [ ] Sticky tabs显示"全部"和带数量的分类标签
- [ ] 分类按资产数量降序排列
- [ ] 无资产的分类不显示
- [ ] 点击Tab正确筛选资产列表
- [ ] 分页功能正常工作
- [ ] "查看全部"、切换按钮已移除
- [ ] 无console错误
- [ ] `npm run typecheck` 通过

---

## 后续优化（可选）

- **服务端分类筛选**: 后端API支持 `category_id` 参数，减少传输数据量
- **分类Tab样式优化**: 使用 `cat.icon` 作为Tab图标前缀
- **记住用户选择**: localStorage保存 `activeCategoryId`，下次打开自动恢复

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 客户端筛选可能显示"没有更多了"过早 | 中 | MVP接受此限制，后续可加服务端支持 |
| 大量分类导致Tab过多 | 低 | 横向滚动，Vant已支持 |

---

## 备注

- 保持现有sticky行为和样式（gradient line, active color）
- 遵循emoji约定：筛选成功toast使用 `✅ 已筛选房产分类`