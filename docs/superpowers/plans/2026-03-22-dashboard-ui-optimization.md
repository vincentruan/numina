# 首页总览页面UI优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化首页总览页面UI，使其与参考截图设计保持一致，包括状态Tab样式、工具栏布局、选择模式和分类导航栏样式。

**Architecture:** 重构 StatusSummaryGrid 组件为横向Tab胶囊样式，调整 DashboardPage 布局使工具栏与状态Tab同行，优化选择模式为卡片+左上角复选框布局，自定义分类导航栏选中样式。

**Tech Stack:** Vue 3 Composition API, TypeScript, Vant 4, CSS

---

## File Structure

**Modified Files:**
- `frontend/src/components/dashboard/StatusSummaryGrid.vue` — 状态汇总组件（卡片网格 → Tab胶囊）
- `frontend/src/pages/DashboardPage.vue` — 主页面布局调整（工具栏位置、选择模式、分类导航栏）
- `frontend/src/components/asset/AssetCard.vue` — 资产卡片（支持选中覆盖层）

**No New Files Created**

---

## Task 1: 重构 StatusSummaryGrid 为横向Tab胶囊样式

**Files:**
- Modify: `frontend/src/components/dashboard/StatusSummaryGrid.vue:1-132`

**Goal:** 将状态汇总从5个卡片网格改为横向Tab标签页，每个Tab显示「文字 + 数量」，选中时有圆角胶囊背景色。

- [ ] **Step 1: 备份当前实现并理解现有逻辑**

阅读 `StatusSummaryGrid.vue`，理解：
- `statusList` 数组结构（key, label, icon）
- `getCount()` 和 `formatValue()` 函数
- `onSelect()` 事件处理

- [ ] **Step 2: 修改模板结构为横向Tab布局**

将模板从卡片网格改为横向Tab：

```vue
<template>
  <div class="status-tabs-wrapper">
    <div class="status-tabs">
      <div
        v-for="status in statusList"
        :key="status.key ?? 'all'"
        class="status-tab"
        :class="{ active: activeStatus === status.key }"
        @click="onSelect(status.key)"
      >
        <span class="tab-label">{{ status.label }}</span>
        <span class="tab-count">{{ getCount(status.key) }}</span>
      </div>
    </div>
    <div class="toolbar-slot">
      <slot name="toolbar"></slot>
    </div>
  </div>
</template>
```

- [ ] **Step 3: 更新样式为胶囊Tab样式**

```vue
<style scoped>
.status-tabs-wrapper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  padding: 12px 16px;
  gap: 12px;
}
.status-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  flex: 1;
  -webkit-overflow-scrolling: touch;
}
.status-tabs::-webkit-scrollbar {
  display: none;
}
.status-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 16px;
  background: #f7f8fa;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  flex-shrink: 0;
}
.status-tab:active {
  opacity: 0.7;
}
.status-tab.active {
  background: #1989fa;
  color: #fff;
}
.tab-label {
  font-size: 13px;
  font-weight: 500;
}
.tab-count {
  font-size: 13px;
  font-weight: 600;
}
.toolbar-slot {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-shrink: 0;
}
</style>
```

- [ ] **Step 4: 移除不再需要的代码**

删除：
- `statusList` 中的 `icon` 字段（不再显示图标）
- `formatValue()` 函数（不再显示金额）
- 卡片相关的样式类（`.status-grid`, `.status-item`, `.status-icon`, `.status-value`）

- [ ] **Step 5: 验证类型检查**

运行：`cd frontend && npx vue-tsc -b --noEmit`
预期：无类型错误

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/dashboard/StatusSummaryGrid.vue
git commit -m "refactor(dashboard): 重构状态汇总为横向Tab胶囊样式

- 将5个卡片网格改为横向Tab标签页
- 每个Tab显示「文字 + 数量」
- 选中时圆角胶囊背景色高亮
- 添加toolbar插槽支持右侧工具栏按钮"
```

---

## Task 2: 调整 DashboardPage 工具栏布局

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue:25-37,672-693`

**Goal:** 将工具栏按钮（排序/筛选/选择）从绝对定位改为与状态Tab同行显示。

- [ ] **Step 1: 修改模板结构，使用StatusSummaryGrid的toolbar插槽**

找到 `DashboardPage.vue` 中的 `.status-toolbar-container` 部分（约25-37行），修改为：

```vue
<StatusSummaryGrid
  :summary="dashboardStore.statesSummary"
  :active-status="activeStatus"
  @select="onStatusSelect"
>
  <template #toolbar>
    <van-icon name="sort" @click="showSortPopup = true" />
    <van-icon name="filter-o" @click="showFilterPopup = true" />
    <van-icon name="checked" @click="enterSelectionMode" />
  </template>
</StatusSummaryGrid>
```

- [ ] **Step 2: 删除旧的布局容器和样式**

删除：
- `.status-toolbar-container` div 容器
- `.toolbar-buttons` div 容器
- 对应的CSS样式（约672-693行）

- [ ] **Step 3: 添加工具栏图标样式**

在 `<style scoped>` 中添加：

```css
:deep(.toolbar-slot .van-icon) {
  font-size: 20px;
  color: #646566;
  cursor: pointer;
  padding: 4px;
}
:deep(.toolbar-slot .van-icon:active) {
  opacity: 0.6;
}
```

- [ ] **Step 4: 验证类型检查**

运行：`cd frontend && npx vue-tsc -b --noEmit`
预期：无类型错误

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/DashboardPage.vue
git commit -m "fix(dashboard): 调整工具栏按钮布局与状态Tab同行

- 使用StatusSummaryGrid的toolbar插槽
- 移除绝对定位的叠加布局
- 工具栏按钮与状态Tab在同一行右侧对齐"
```

---

## Task 3: 优化选择模式为卡片布局

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue:110-136`
- Modify: `frontend/src/components/asset/AssetCard.vue:1-202`

**Goal:** 选择模式使用卡片展示，复选框在卡片左上角，顶部显示已选数量。

### Subtask 3.1: 修改 AssetCard 支持选中覆盖层

- [ ] **Step 1: 为 AssetCard 添加 selectable 和 selected props**

在 `AssetCard.vue` 的 `<script setup>` 中添加：

```typescript
const props = defineProps<{
  asset: Asset
  selectable?: boolean
  selected?: boolean
}>()

defineEmits<{
  click: []
  'update:selected': [value: boolean]
}>()
```

- [ ] **Step 2: 在模板中添加选中覆盖层**

在 `.asset-card` 根元素内部最前面添加：

```vue
<div v-if="selectable" class="selection-overlay">
  <van-checkbox
    :model-value="selected"
    @click.stop="$emit('update:selected', !selected)"
  />
</div>
```

- [ ] **Step 3: 添加选中覆盖层样式**

```css
.asset-card {
  position: relative; /* 确保已有此属性 */
}
.selection-overlay {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  padding: 2px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
.selection-overlay :deep(.van-checkbox) {
  display: flex;
}
```

- [ ] **Step 4: Commit AssetCard 修改**

```bash
git add frontend/src/components/asset/AssetCard.vue
git commit -m "feat(asset): AssetCard支持选中覆盖层

- 添加selectable和selected props
- 左上角显示复选框覆盖层
- 支持update:selected事件"
```

### Subtask 3.2: 修改 DashboardPage 选择模式布局

- [ ] **Step 5: 修改选择模式模板为卡片布局**

找到 `DashboardPage.vue` 中的选择模式部分（约110-136行），修改为：

```vue
<!-- Selection Mode -->
<div v-else class="selection-mode">
  <div class="selection-header">
    <van-checkbox v-model="selectAll" @change="toggleSelectAll">全选</van-checkbox>
    <span class="selection-count">已选 {{ selectedIds.length }} 项</span>
    <van-button type="primary" size="small" @click="exitSelectionMode">完成</van-button>
  </div>
  <div class="selection-list-cards">
    <AssetCard
      v-for="asset in sortedAndFilteredAssets"
      :key="asset.id"
      :asset="asset"
      :selectable="true"
      :selected="selectedIds.includes(asset.id)"
      @click="toggleSelection(asset.id)"
      @update:selected="(val) => val ? selectedIds.push(asset.id) : selectedIds.splice(selectedIds.indexOf(asset.id), 1)"
    />
  </div>
  <div class="selection-actions">
    <van-button icon="share-o" size="small" @click="handleBatchShare">分享</van-button>
    <van-button icon="delete-o" size="small" @click="handleBatchDelete">删除</van-button>
    <van-button icon="label-o" size="small" @click="handleBatchCategory">分类</van-button>
    <van-button icon="tag-o" size="small" @click="handleBatchTag">标签</van-button>
    <van-button icon="ellipsis" size="small" @click="showMoreActions = true">更多</van-button>
  </div>
</div>
```

- [ ] **Step 6: 更新选择模式样式**

```css
.selection-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
}
.selection-count {
  flex: 1;
  text-align: center;
  font-size: 14px;
  font-weight: 500;
  color: #1989fa;
}
.selection-list-cards {
  padding: 0 12px;
}
.selection-actions {
  display: flex;
  justify-content: space-around;
  padding: 12px 16px;
  background: #fff;
  border-radius: 8px;
  position: sticky;
  bottom: 60px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08);
}
```

- [ ] **Step 7: 删除旧的选择模式样式**

删除不再使用的样式类：
- `.selection-list`
- `.selection-item`
- `.selection-item-content`

- [ ] **Step 8: 验证类型检查**

运行：`cd frontend && npx vue-tsc -b --noEmit`
预期：无类型错误

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/DashboardPage.vue
git commit -m "feat(dashboard): 优化选择模式为卡片布局

- 选择模式使用AssetCard展示
- 卡片左上角显示复选框覆盖层
- 顶部中间显示已选数量
- 保持底部操作按钮栏不变"
```

---

## Task 4: 自定义分类导航栏选中样式

**Files:**
- Modify: `frontend/src/pages/DashboardPage.vue:39-44,694-705`

**Goal:** 为分类导航栏添加带光晕效果的下划线选中样式。

- [ ] **Step 1: 为分类导航栏添加自定义样式类**

找到 `.category-nav-sticky` 部分（约39-44行），确保使用了自定义类：

```vue
<div v-if="showCategoryNav && categories.length > 1" class="category-nav-sticky">
  <van-tabs v-model:active="activeCategoryIndex" @change="onCategoryChange">
    <van-tab v-for="(cat, index) in categories" :key="cat.id" :title="cat.name" />
  </van-tabs>
</div>
```

- [ ] **Step 2: 添加光晕下划线样式**

在 `.category-nav-sticky` 样式中添加自定义下划线：

```css
.category-nav-sticky {
  position: sticky;
  top: 0;
  z-index: 99;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.category-nav-sticky :deep(.van-tabs__wrap) {
  padding: 0 12px;
}
.category-nav-sticky :deep(.van-tabs__line) {
  background: linear-gradient(90deg, transparent, #1989fa, transparent);
  height: 3px;
  border-radius: 3px;
  box-shadow: 0 0 8px rgba(25, 137, 250, 0.6);
}
.category-nav-sticky :deep(.van-tab--active) {
  color: #1989fa;
  font-weight: 600;
}
```

- [ ] **Step 3: 验证类型检查**

运行：`cd frontend && npx vue-tsc -b --noEmit`
预期：无类型错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DashboardPage.vue
git commit -m "style(dashboard): 分类导航栏添加光晕下划线效果

- 自定义van-tabs下划线样式
- 添加渐变和阴影光晕效果
- 选中Tab文字加粗高亮"
```

---

## Task 5: 端到端验证

**Goal:** 验证所有UI优化是否符合参考截图要求。

- [ ] **Step 1: 构建项目验证类型**

运行：`cd frontend && npm run build`
预期：构建成功，无类型错误

- [ ] **Step 2: 启动开发服务器**

运行：`cd frontend && npm run dev`
访问：`http://localhost:5173`

- [ ] **Step 3: 验证状态Tab样式**

检查点：
- ✅ 状态区域是横向Tab标签页（非卡片网格）
- ✅ 每个Tab显示「文字 + 数量」（如「服役中 3」）
- ✅ 选中Tab有圆角胶囊蓝色背景
- ✅ 工具栏按钮（排序/筛选/选择）与状态Tab在同一行右侧

- [ ] **Step 4: 验证选择模式**

操作：点击"选择"按钮进入选择模式

检查点：
- ✅ 资产以卡片形式展示（非列表项）
- ✅ 卡片左上角有复选框覆盖层
- ✅ 顶部中间显示「已选 N 项」
- ✅ 底部操作按钮栏正常显示

- [ ] **Step 5: 验证分类导航栏**

操作：向上滚动页面，使总览卡片消失

检查点：
- ✅ 分类导航栏sticky显示在顶部
- ✅ 选中分类有光晕下划线效果
- ✅ 点击分类可筛选对应资产

- [ ] **Step 6: 截图对比**

使用浏览器开发者工具截图，与参考截图对比：
- `docs/images/references/有数app-首页-总览&列表.jpeg`
- `docs/images/references/有数app-首页-资产总览&日均成本&资产状态汇总.jpeg`
- `docs/images/references/有数app-首页-选择.jpeg`

- [ ] **Step 7: 最终Commit**

```bash
git add -A
git commit -m "docs: 添加UI优化验证截图和说明"
```

---

## Verification Checklist

运行以下命令验证实现：

```bash
# 1. 类型检查
cd frontend && npx vue-tsc -b --noEmit

# 2. 构建验证
cd frontend && npm run build

# 3. 启动开发服务器
cd frontend && npm run dev
```

浏览器验证点：
- [ ] 状态Tab为横向胶囊样式，显示文字+数量
- [ ] 工具栏按钮与状态Tab同行右侧对齐
- [ ] 选择模式使用卡片布局，复选框在左上角
- [ ] 顶部显示已选数量
- [ ] 分类导航栏选中有光晕下划线

---

## Notes

- 所有修改遵循现有代码风格（Vue 3 Composition API + TypeScript）
- 使用Vant 4组件，自定义样式通过 `:deep()` 选择器
- 保持响应式设计，支持移动端触摸交互
- 频繁commit，每个任务独立可回滚
