---
title: 财务页面 UI/UX 全面优化 - Plan
type: feat
date: 2026-07-24
topic: finance-page-ux-optimization
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-plan-bootstrap
execution: code
---

# 财务页面 UI/UX 全面优化

## Goal Capsule

- **Objective:** 对财务页（`/finance`）三大标签（资产/负债/心愿）进行 17 项 UI/UX 优化，解决信息密度过高、过滤器层级过深、心愿进度不可见、表单过长、详情页臃肿等核心体验问题。
- **Product authority:** 财务页是家庭资产/负债/心愿管理的唯一入口，优化目标是"快速定位 + 清晰层级 + 操作效率"。
- **Execution profile:** 纯前端 Vue 3 优化，不涉及后端 API 变更。4 批次交付，Batch 1 优先解决日常使用频率最高的 3 个问题。
- **Stop conditions:** 任何优化破坏了现有交互（筛选/批选/分页/深链/批量操作），停下来重审。
- **Open blockers:** 无。

---

## Summary

基于浏览器完整探索（demouser 登录 → 资产列表 → 资产详情 → 编辑表单 → 负债列表 → 负债详情 → 心愿列表 → 心愿详情 → 新增流程 → 批量选择）+ 源码审查（4432 行组件代码），识别出 17 项 UI/UX 优化项，按影响面分为 4 个批次。

核心发现：
1. 资产列表 31 项同类资产视觉几乎相同，缺少分组和视觉锚点
2. 过滤器 4 层（状态网格 + 类型 tabs + 分类 tabs + 搜索排序）占满半屏
3. 心愿列表看不到储蓄进度，必须点进详情
4. 资产表单 20+ 字段一次展开，移动端滚动过多
5. 负债策略卡信息层级不清，两个方法并排不够直观
6. 详情页"买 vs 租"和"成本等价"计算器占据大量空间
7. 三个 tab 各自独立，缺少跨模块财务健康度摘要

---

## Problem Frame

财务页是 Numina 最复杂的页面（4432 行组件代码），承载资产/负债/心愿三大模块的完整列表管理交互。当前问题集中在三个维度：

**信息密度** — 资产列表 31 项以相同大小连续排列，同类资产（4 只基金、4 只股票）外观几乎一样。过滤器 4 层叠加后首屏几乎看不到实际列表。心愿列表只显示文字金额，缺少进度可视化。

**信息架构** — 资产详情页嵌入"买 vs 租"和"成本等价"两个计算器，总长超过 3 屏。资产表单 20+ 字段一次展开。负债策略卡两个方法并排显示，数字格式不统一。

**跨模块一致性** — 三个 tab 各自独立，无财务健康度汇总。数字格式不统一（`¥420.00万` vs `191.5万` vs `¥3,000`）。空状态风格不一致。

---

## Requirements

### 资产模块

- R1. 资产列表按 category 分组，每组有小标题（分类名 + 数量 + 小计金额），可折叠/展开
- R2. 过滤器从 4 层合并为 2 层：状态网格（保留）+ 搜索框 + 排序 + 筛选按钮（popup 包含类型 + 分类）
- R3. 列表项视觉区分度提升：category 色条加宽至 4px，增值/贬值用绿/红微底色标记（±5% 阈值）
- R4. 资产表单分区折叠：基本信息始终展开，实物信息/保修信息/标签备注默认折叠
- R5. 资产详情页拆分：计算器移入"分析"子 tab 或"更多工具"入口，操作按钮重组

### 负债模块

- R6. 负债策略卡重构：推荐方法高亮 + "推荐"标签，两方法改为上下排列，底部显示节省金额
- R7. 负债卡片 swipe 操作增加视觉提示（首次进入微滑 20px 回弹），删除增加确认
- R8. 负债还款倒计时显示在卡片上（< 7 天红色警告）

### 心愿模块

- R9. 心愿列表每项底部增加细进度条（3px，priority 颜色），进度 > 80% 显示绿色 + "即将达成！"
- R10. 心愿优先级视觉增强：高/中/低分别用 coral/amber/green 色条，列表顶部增加可折叠图例

### 跨模块

- R11. 财务页 tabs 上方增加 compact summary bar（净资产/负债率/月还），点击跳转对应 tab
- R12. 列表/卡片视图切换增加 TransitionGroup + FLIP 过渡动画（250ms ease-out）
- R13. 数字格式统一：全部使用 `useCurrency.format()`，> 10000 → 万单位，< 10000 → 千分位
- R14. 空状态统一风格：自定义 SVG 插图 + 引导文案 + CTA 按钮
- R15. Tab 切换增加 swipe 过渡动画
- R16. 资产列表长按快捷操作（编辑/出售/标记闲置）+ haptic feedback
- R17. 搜索高亮：匹配文字使用 `<mark>` 标签 + 主题色背景

---

## Key Technical Decisions

- **KTD-1: 资产列表分组为默认视图。** 当前 31 项中同类资产视觉几乎相同，分组后每组有小标题+折叠+分类小计金额，视觉区分度最高。保持平铺只增强视觉区分不够。
- **KTD-2: 过滤器合并到 popup。** 保留状态网格作为主导航（核心高频操作），将类型 tabs + 分类 tabs 合并到一个 popup 筛选器。这改变了现有交互模式但大幅减少首屏占用。
- **KTD-3: 详情页计算器拆出。** "买 vs 租"和"成本等价"从详情页主体移入"更多工具"折叠区域（而非新建子 tab，避免增加路由复杂度）。
- **KTD-4: 进度条使用 priority 颜色。** 心愿进度条颜色复用已有的 priority 色系（高=coral，中=amber，低=green），无需新增设计 token。
- **KTD-5: 数字格式统一走 useCurrency.format()。** 不新增格式化函数，修复遗漏调用点即可。

---

## Scope Boundaries

### In Scope
- Batch 1（详设）: R1 资产列表分组, R2 过滤器合并, R9 心愿进度条
- Batch 2（概要）: R4 表单折叠, R6 策略卡重构, R11 财务摘要栏
- Batch 3（概要）: R5 详情页拆分, R12 切换动画, R7 swipe 提示
- Batch 4（概要）: R3 视觉区分, R8 还款倒计时, R10 优先级视觉, R13 数字格式, R14 空状态, R15 tab 动画, R16 长按操作, R17 搜索高亮

### Non-Goals
- 后端 API 改动（全部为前端优化）
- 新增页面/路由
- 数据模型变更
- AI 功能增强（已有 AI 建议卡保持不变）
- 暗色模式适配（当前优化在 light mode 基础上进行，dark mode 后续统一处理）

### Deferred to Follow-Up Work
- 资产卡片模式 2 列网格优化
- 心愿达成 confetti 庆祝动画
- 负债卡片自动滑动提示的首次引导逻辑（R7 先做删除确认，自动滑动提示 deferred）
- U11 负债还款倒计时（需后端新增 `next_payment_date` 字段，与纯前端 Non-Goal 冲突）

---

## Implementation Units

### Batch 1 — 高频使用优化（详细设计）

---

### U1. 资产列表按分类分组

**Goal:** 将资产列表从平铺 31 项改为按 category 分组的可折叠列表，每组有小标题（分类图标 + 名称 + 数量 + 小计金额），默认展开，可点击折叠。

**Requirements:** R1

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/components/asset/AssetListPanel.vue` — 主要修改：列表渲染逻辑从 `v-for` 平铺改为分组渲染
- `frontend/apps/main/src/components/asset/AssetGroupHeader.vue` — 新建：分组标题组件
- `frontend/apps/main/src/components/asset/__tests__/AssetGroupHeader.spec.ts` — 新建：分组标题组件测试
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 i18n key: `asset.groupSubtitle`
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 同上

**Approach:**

1. 在 `AssetListPanel.vue` 的 `filteredByCategoryAssets` computed 基础上，新增 `groupedByCategory` computed：
   - 输入: `dashboardStore.displayedAssets`
   - 分组键: `asset.category?.id ?? '__uncategorized__'`（category 是 optional 的，`types/index.ts:47` `category?: Category`，需处理 null 分支）
   - 每组计算: `count`, `subtotal`（sum of `current_value`）, `category`（取第一个 asset 的 category 对象获取 icon/color；uncategorized 组传 `undefined`，AssetGroupHeader 渲染 fallback icon + 默认 color）
   - 输出: `Array<{ category: Category | undefined, items: Asset[], subtotal: number }>`
   - **分页限制**: 分组在前端对当前页数据做（后端分页按 status），跨页时组可能不完整。组标题显示当前页数量 `(N)`，当该组可能还有更多项时显示 `还有更多 ›` 提示（启发式：该组在页面末尾被截断时触发）

2. 分组渲染结构：
   ```
   <template v-for="group in groupedByCategory" :key="group.category.id">
     <AssetGroupHeader
       :category="group.category"
       :count="group.items.length"
       :subtotal="group.subtotal"
       :collapsed="collapsedGroups.has(group.category.id)"
       @toggle="toggleGroup(group.category.id)"
     />
     <Transition name="collapse">
       <template v-if="!collapsedGroups.has(group.category.id)">
         <AssetListItem v-for="asset in group.items" ... />
       </template>
     </Transition>
   </template>
   ```

3. `collapsedGroups` 使用 `ref<Set<string>>` 管理，`toggleGroup` 方法 add/delete。

4. `AssetGroupHeader.vue` 设计：
   - 高度 44px（满足 §2 touch-target-size 最小 44px 要求），背景 `var(--bg-secondary)`
   - 左侧: category icon（32px 圆形，使用 category.color；category 为 undefined 时用 `var(--color-text-tertiary)` + 默认 `apps-o` icon）+ 分类名（undefined 时显示 i18n `asset.uncategorized`）+ `(N)` 数量
   - 右侧: 小计金额（`useCurrency.format(subtotal)`）+ 折叠箭头图标
   - 点击整行 toggle 折叠
   - 折叠时箭头旋转 90°（CSS transition 200ms）
   - **可访问性**: `role="button"`, `tabindex="0"`, `aria-expanded`, Enter/Space 触发 toggle

5. 分组排序: 按 subtotal 降序（价值最高的分类排最前）

6. 搜索/筛选时自动展开所有分组（避免用户在折叠状态下找不到结果）。注意：`van-list` 无限滚动加载更多时不清空 collapsedGroups 状态，仅搜索/筛选触发时清空

7. 批量选择模式下，分组标题显示该组已选数量

**Patterns to follow:**
- `LiabilityListPanel.vue` 的 filter-chips 模式（分类筛选 UI 参考）
- `StatusSummaryGrid.vue` 的 tab 交互模式
- `AssetListItem.vue` 已有的 `category.color` 和 `getIconId(category.icon)` 用法

**Test scenarios:**
- 31 项资产按 12 个分类正确分组，每组数量和金额正确
- 点击分组标题折叠/展开，箭头旋转动画
- 搜索后自动展开所有分组
- 空分组不显示（分类下无匹配资产时）
- 批量选择模式下分组标题显示已选数量
- 分组排序正确（按 subtotal 降序）

**Verification:**
- `pnpm typecheck` 通过
- `pnpm test:run` 相关测试通过
- 浏览器验证: 31 项资产正确分组，折叠/展开流畅，搜索后分组自动展开

---

### U2. 过滤器合并到 popup

**Goal:** 将资产列表的 4 层过滤器（状态网格 + 类型 tabs + 分类 tabs + 搜索排序）合并为 2 层：状态网格（保留）+ 搜索框 + 排序 + 筛选按钮（点击弹出 popup 包含类型和分类选择）。

**Requirements:** R2

**Dependencies:** 无（与 U1 独立，但建议 U1 先完成以减少合并冲突）

**Files:**
- `frontend/apps/main/src/components/asset/AssetListPanel.vue` — 主要修改：移除 type-tabs 和 category-tabs，新增筛选 popup
- `frontend/apps/main/src/components/asset/AssetFilterPopup.vue` — 新建：筛选 popup 组件
- `frontend/apps/main/src/components/asset/__tests__/AssetFilterPopup.spec.ts` — 新建
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 i18n keys
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 同上

**Approach:**

1. 移除 `AssetListPanel.vue` 中的：
   - `<van-tabs v-model:active="activeTypeIndex" class="type-tabs">` (lines 28-32)
   - `<div class="category-nav-container">` 整个块 (lines 35-55)

2. 在搜索栏右侧新增"筛选"按钮：
   ```
   <div class="search-bar">
     <van-search ... />
     <van-dropdown-menu>
       <van-dropdown-item v-model="sortBy" :options="sortOptions" @change="onSearch" />
     </van-dropdown-menu>
     <button class="filter-trigger" @click="filterPopupOpen = true">
       <van-icon name="filter-o" />
       <span v-if="activeFilterCount > 0" class="filter-badge">{{ activeFilterCount }}</span>
     </button>
   </div>
   ```

3. `AssetFilterPopup.vue` 使用 `van-popup` (position="right", round, closeable)：
   - 顶部标题: "筛选" + 重置按钮
   - 第一区块: "资产类型" — 3 个 chip 按钮（全部/实物/金融）
   - 第二区块: "分类" — 网格布局的分类 chip（使用 `categoriesWithAssetCount`，每项显示图标+名称+数量）
   - 底部: "确认" 按钮

4. 状态管理：
   - `filterPopupOpen: ref(false)`
   - `pendingTypeIndex: ref(0)` — popup 内的临时状态
   - `pendingCategoryId: ref<string | null>(null)`
   - 点击"确认"时，将 pending 值提交到 `activeTypeIndex` / `activeCategoryId`，触发 `onTypeTabChange` / `onCategoryChange`
   - `activeFilterCount` computed: 计算当前激活的筛选条件数量（类型非"全部" +1，分类非"全部" +1）

5. 筛选按钮的 badge 显示激活数量，0 时隐藏

6. popup 打开时从当前状态初始化 pending 值
8. **焦点管理（§1 keyboard-nav + §9 modal-escape）**: popup 打开时 focus 移入第一个可交互元素（focus trap），Escape 键关闭 popup，关闭后 focus 返回筛选触发按钮（focus restoration）。Vant `van-popup` 需配置 `lock-scroll` 并手动实现 focus trap（Vant 不内置）

7. **categoryCounts 数据源**: 移除 category-nav 后，`categoriesWithAssetCount`（来自 `dashboardStore.categoryCounts`）仍需在状态切换时刷新。保持现有 `onStatusSelect` 中的 `dashboardStore.fetchCategoryCounts(targetStatus)` 调用不变，popup 内分类列表消费同一数据源

**Patterns to follow:**
- `van-popup` 在 `SimulateExtraDialog.vue` 中的使用模式
- `van-action-sheet` 在 `AssetListPanel.vue` 中已有的 more-actions 用法
- `LiabilityListPanel.vue` 的 filter-chips 分类选择模式

**Test scenarios:**
- 筛选 popup 正确打开/关闭
- 选择类型后确认，列表正确过滤
- 选择分类后确认，列表正确过滤
- 重置按钮清除所有筛选
- filter badge 正确显示激活数量
- popup 外点击关闭
- 搜索 + 筛选组合正确

**Verification:**
- `pnpm typecheck` 通过
- `pnpm test:run` 相关测试通过
- 浏览器验证: 过滤器从 4 层减为 2 层，popup 交互流畅，筛选结果正确

---

### U3. 心愿列表进度条

**Goal:** 在每个心愿条目底部增加细进度条（3px 高度），使用 priority 颜色，进度 > 80% 显示绿色 + "即将达成！"标签。

**Requirements:** R9

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/components/wishes/WishListPanel.vue` — 修改：在 wish-item 内增加进度条
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 `wish.almostReached`
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 同上

**Approach:**

1. 在 `WishListPanel.vue` 的 `.wish-body` 底部（afford-bar 之后），增加进度条区块：
   ```html
   <div v-if="wish.expected_price && wish.status === 'pending'" class="wish-progress">
     <div class="wish-progress-bar">
       <div
         class="wish-progress-fill"
         :class="{ 'almost-reached': progressPercent >= 80 }"
         :style="{ width: `${progressPercent}%` }"
       />
     </div>
     <span v-if="progressPercent >= 80" class="almost-badge">
       {{ t('wish.almostReached') }}
     </span>
   </div>
   ```

2. `progressPercent` 计算：
   ```ts
   function wishProgress(wish: Wish): number {
     if (!wish.expected_price) return 0
     const saved = Number(wish.saved_amount ?? 0)
     const target = Number(wish.expected_price)
     if (target <= 0) return 0
     return Math.min(100, Math.round((saved / target) * 100))
   }
   ```

3. 进度条样式：
   - 高度 3px，圆角，背景 `var(--bg-tertiary)`
   - fill 颜色: priority-based
     - `high` → `var(--color-coral)`
     - `medium` → `var(--color-warning, #ff976a)` (amber)
     - `low` → `var(--color-success, #07c160)` (green)
   - `almost-reached` class: 颜色强制 `var(--color-success)` + 脉冲动画（reduced-motion 下降级为静态高亮，见全局动画约定）
   - **可访问性**: 进度条容器加 `role="progressbar"` `aria-valuenow="{progressPercent}"` `aria-valuemin="0"` `aria-valuemax="100"` `aria-label="{wish.name} 储蓄进度"`
   - 进度 0% 且未设月存（`monthly_saving` 为空/0）: 显示灰色虚线（`border: 1px dashed var(--color-text-tertiary)`）
   - 进度 0% 但已设月存（`monthly_saving > 0`）: 显示 2% 最小宽度的 priority 色 fill + 起点小圆点（表示"已开始储蓄但尚未存入"，区别于虚线的"未开始"）

4. "即将达成！" 标签：
   - 位置: 进度条右侧
   - 样式: 12px, `var(--color-success)`, font-weight 600
   - 仅在 `progressPercent >= 80 && status === 'pending'` 时显示

5. 已实现/已取消的心愿不显示进度条

**Patterns to follow:**
- `LiabilityCard.vue` 的 `.progress-bar` + `.progress-fill` 模式（lines 58-60）
- `AssetListItem.vue` 的 `.progress-section` 模式（lines 43-62）
- `WishSavingsProgress.vue` 已有的进度计算逻辑

**Test scenarios:**
- 进度 0% 显示虚线（未设月存时）
- 进度 50% 显示对应宽度 + priority 颜色
- 进度 80% 显示绿色 + "即将达成！"
- 进度 100% 进度条满宽
- 已实现/已取消心愿不显示进度条
- 无 expected_price 的心愿不显示进度条

**Verification:**
- `pnpm typecheck` 通过
- `pnpm test:run` 相关测试通过
- 浏览器验证: 5 个心愿正确显示进度条，颜色与 priority 匹配，80%+ 显示"即将达成！"

---

### Batch 2 — 信息架构优化（概要设计，后续详设）

---

### U4. 资产表单分区折叠

**Goal:** 将新建/编辑资产表单的 20+ 字段分区折叠：基本信息始终展开，实物信息/保修信息/标签备注默认折叠，选择"实物资产"时自动展开实物信息区块。

**Requirements:** R4

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/components/asset/AssetForm.vue` — 主要修改
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增折叠区块标题 i18n
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 同上

**Approach:**
- 使用 `van-collapse` 组件或自定义折叠区块
- "基本信息" 始终展开（名称/分类/货币/价格/日期/状态）
- "实物资产信息" 选择 `asset_type === 'physical'` 时自动展开（watch asset_type 变化）
- "保修信息" 默认折叠
- "标签与备注" 默认折叠
- 折叠/展开动画 250ms ease-out
- 必填字段添加 `*` 标记（名称/分类/购入价格）
- "同购入价" 按钮改为当前价值的默认行为（新建时 current_value = purchase_price）
- **验证失败导航**（关键）: 表单提交验证失败时，(1) 自动展开包含第一个无效字段的折叠区块，(2) `scrollIntoView` 滚动到该字段，(3) `focus()` 聚焦。避免用户在折叠状态下看到错误 toast 却找不到出错字段的死路 UX

**Test scenarios:**
- 新建表单: 实物信息区块在选择"实物资产"时自动展开
- 新建表单: 选择"金融资产"时实物信息区块隐藏
- 编辑表单: 已有实物信息的资产打开时实物区块展开
- 折叠/展开动画流畅
- 必填标记正确显示
- **验证失败时自动展开含错误字段的折叠区块并滚动聚焦**

**Verification:** `pnpm typecheck` + `pnpm test:run` + 浏览器验证表单折叠行为

---

### U5. 负债策略卡重构

**Goal:** 重构 LiabilityStrategyCard，推荐方法高亮 + "推荐"标签，两方法改为上下排列，底部显示节省金额。

**Requirements:** R6

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/components/liability/LiabilityStrategyCard.vue` — 主要修改
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 i18n keys
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 同上

**Approach:**
- 标题: "还款策略建议" + 副标题 "基于你的 N 笔负债"
- 推荐方法（雪崩法）高亮: 左侧边框 3px `var(--color-coral)` + "推荐" badge
- 两方法改为上下排列（flex-direction: column）
- 底部: "选择雪崩法可节省 ¥XXX 利息" 一行文字
- "采纳" 按钮 -> "按此策略排序"：点击后按对应策略（雪崩=利率降序，雪球=余额升序）对负债列表排序，卡片变为 "当前策略: 雪崩法 ✓" + "更换策略" 链接
- **状态持久化**: 采纳状态用 `localStorage` 存储（key: `liability_strategy_adopted`，值: `avalanche` | `snowball` | null），与现有 LiabilityStrategyCard 的 ADOPT_KEY 模式一致
- "更换策略" 链接: 清除 localStorage 采纳标记，恢复列表默认排序，卡片回到双方法对比状态

**Test scenarios:**
- 2+ 笔负债时卡片正确渲染
- 推荐方法有高亮边框和"推荐"标签
- 节省金额计算正确
- 采纳后卡片状态变化
- 1 笔负债时卡片不渲染

**Verification:** `pnpm typecheck` + `pnpm test:run` + 浏览器验证策略卡布局

---

### U6. 财务摘要栏

**Goal:** 在 FinanceHubPage 的 tabs 上方增加 compact summary bar，显示净资产/负债率/月还三个指标，点击跳转对应 tab。

**Requirements:** R11

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/pages/FinanceHubPage.vue` — 新增 summary bar
- `frontend/apps/main/src/components/dashboard/FinanceSummaryBar.vue` — 新建
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增 i18n keys
- `frontend/apps/main/src/i18n/locales/en-US.ts` — 同上

**Approach:**
- 高度 60px，背景 `var(--bg-primary)`，不参与滚动
- 三列等宽: 净资产（主指标）| 负债率 | 月还总额
- 数据来源: `dashboardStore.overview`（已有）
- 负债率 = `total_assets > 0 ? (total_liabilities / total_assets * 100) : 0`（需零除保护：total_assets=0 时显示 `-`，避免 NaN/Infinity）
- 点击指标跳转: 净资产->`assets`，负债率->`liabilities`，月还->`liabilities`（月还无独立 tab，跳负债 tab 并滚动到月供 banner）
- 仅在 overview 数据加载后显示
- **可访问性**: 每个指标 `role="button"`, `tabindex="0"`, `aria-label`, Enter/Space 触发跳转

**Test scenarios:**
- overview 加载后正确显示三个指标
- 负债率计算正确
- total_assets=0 时负债率显示 `-`（不显示 NaN/Infinity）
- 点击净资产指标跳转 assets tab
- 点击负债率/月还指标跳转 liabilities tab
- overview 未加载时不显示

**Verification:** `pnpm typecheck` + `pnpm test:run` + 浏览器验证摘要栏

---

### Batch 3 — 品质感提升（概要设计）

---

### U7. 详情页计算器拆出

**Goal:** 将 AssetDetailPage 的"买 vs 租"和"成本等价"计算器移入"更多工具"折叠区域。

**Requirements:** R5

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/pages/AssetDetailPage.vue` — 重构
- "编辑"按钮提升为 header 右侧
- "出售/退役/删除"移入"..."更多菜单

**Approach:** 在详情页底部增加 `<van-collapse>` "更多工具"区块，包含 BuyVsRentCalculator 和 CostEquivalenceCard。操作按钮重组: 编辑→header，出售/退役/删除→action-sheet。 action-sheet 中删除项使用 `danger` 类型（红色）+ 与出售/退役之间加分隔线；删除仍需 showConfirmDialog 二次确认（与 U9 一致），满足 §8 destructive-emphasis 危险操作视觉分离。

**Test scenarios:** 计算器在折叠区域内正确渲染；编辑按钮在 header 可点击；危险操作有确认弹窗。

---

### U8. 列表/卡片视图切换动画

**Goal:** 视图切换增加 TransitionGroup + FLIP 动画。

**Requirements:** R12

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/components/asset/AssetListPanel.vue` — 添加 `<TransitionGroup>`

**Approach:** 使用 Vue `<TransitionGroup name="asset-list">` 包裹列表项，CSS 定义 `move`/`enter`/`leave` 过渡。时长 250ms ease-out。 所有过渡包裹 `@media (prefers-reduced-motion: reduce)` 降级为即时切换（见全局动画约定）。

**Test scenarios:** 切换时动画流畅无闪烁；快速连续切换不卡顿。

---

### U9. 负债卡片删除确认

**Goal:** 为负债卡片的删除操作增加 confirm dialog，防止误删。（首次进入微滑提示已 deferred，见 Scope Boundaries）

**Requirements:** R7（仅删除确认部分；swipe 提示 deferred）

**Dependencies:** 无

**Files:**
- `frontend/apps/main/src/components/liability/LiabilityCard.vue` — 增加删除确认

**Approach:** 删除 emit 前增加 `showConfirmDialog`（Vant 的 `showConfirmDialog`），确认后执行 `$emit('delete', liability)`，取消则不执行。

**Test scenarios:** 删除前弹出确认；确认后执行删除；取消则不执行删除。

---

### Batch 4 — 细节打磨（概要设计）

---

### U10. 资产列表视觉区分增强

**Requirements:** R3

**Approach:** AssetListItem 左侧色条从 2px 加宽到 4px。增值（current_value > purchase_price * 1.05）加浅绿底色 `rgba(7, 193, 96, 0.04)`。贬值（current_value < purchase_price * 0.95）加浅红底色 `rgba(238, 49, 49, 0.04)`。

**Files:** `AssetListItem.vue`

---

### U11. 负债还款倒计时 (MOVED TO DEFERRED)

**Requirements:** R8

**Status:** MOVED TO DEFERRED - 此项需要后端新增 `next_payment_date` 字段（当前 `Liability` 类型无 `first_payment_date`/`payment_cycle`/`payment_day`，无法前端计算），与 Non-Goal "后端 API 改动/数据模型变更" 冲突。移至 Deferred to Follow-Up Work，待后端支持后再做。

**Files:** `LiabilityCard.vue`, `LiabilityListPanel.vue` (when backend supports it)

---

### U12. 心愿优先级视觉增强

**Requirements:** R10

**Approach:** priority-stripe 当前已是 4px（`WishListPanel.vue:401-405`，无需加宽）。主要工作是列表顶部增加可折叠图例（"高/中/低" 三色说明，默认折叠，localStorage 记忆展开状态）。颜色已存在：high=#f44336, medium=#ff9800, low=#4caf50。

**Files:** `WishListPanel.vue`

---

### U13. 数字格式统一

**Requirements:** R13

**Approach:** grep 排查所有直接拼接金额的位置，统一使用 `useCurrency.format()`。重点关注: LiabilityListPanel 的 summary-banner（`191.5万` → `¥191.50万`），WishListPanel 的价格显示。

**Files:** `LiabilityListPanel.vue`, `WishListPanel.vue`, `LiabilityCard.vue`

---

### U14. 空状态统一

**Requirements:** R14

**Approach:** 创建 `FinanceEmptyState.vue` 通用组件（自定义 SVG + 文案 + CTA），替换各模块的空状态。资产: "还没有资产" + [添加]。负债已结清: "恭喜！所有负债已结清"。心愿已取消: "取消的心愿会出现在这里"。

**Files:** 新建 `FinanceEmptyState.vue`，修改 `AssetListPanel.vue`, `LiabilityListPanel.vue`, `WishListPanel.vue`

---

### U15. Tab 切换动画

**Requirements:** R15

**Approach:** FinanceHubPage 的 van-tabs 内容区使用 `<Transition>` 包裹，方向根据 tab index 变化决定（左滑/右滑）。 过渡时长 250ms ease-out，包裹 `@media (prefers-reduced-motion: reduce)` 降级为无动画（见全局动画约定）。

**Files:** `FinanceHubPage.vue`

---

### U16. 资产列表长按快捷操作

**Requirements:** R16

**Approach:** AssetListItem 已有 touchstart/touchend 事件。增加 400ms 长按阈值（早于 iOS/Android 系统长按菜单 ~500ms，避免 §2 gesture-conflicts）-> 弹出 action-sheet。AssetListItem 加 `user-select: none; -webkit-touch-callout: none;` 抑制系统长按菜单（编辑/出售/标记闲置）。触发 `navigator.vibrate?.(50)` haptic feedback（可选链调用，iOS Safari 不支持时静默跳过）。**可发现性**: 首次进入资产列表时显示一次性 toast 提示"长按资产可快捷操作"（localStorage 标记，仅显示一次）；同时在 AssetListItem 右上角增加一个 `⋯` 图标按钮作为桌面/非触摸设备的替代入口。

**Files:** `AssetListItem.vue`, `AssetListPanel.vue`

---

### U17. 搜索高亮

**Requirements:** R17

**Approach:** 创建 `HighlightText.vue` 组件，接收 `text` 和 `query` props，使用 `<mark>` 标签高亮匹配文字。在 AssetListItem 的 name 字段使用。

**Files:** 新建 `HighlightText.vue`，修改 `AssetListItem.vue`

---

## Verification Contract

### Per-Unit Gates
- 每个 U 完成后: `pnpm typecheck` 0 errors
- 每个 U 完成后: `pnpm test:run` 相关测试通过
- Batch 1 完成后: 浏览器完整验证资产列表分组 + 过滤器 popup + 心愿进度条

### Cross-Unit Gates
- Batch 1 完成后: 资产列表不破坏现有筛选/批选/分页/深链
- Batch 2 完成后: 表单折叠不丢失任何字段
- 全部完成后: `pnpm -r typecheck` 0 errors, `pnpm -r test:run` 全通过

### 全局交互约定（UI/UX Pro Max 审核补充）

**全局动画约定（§7 reduced-motion, High severity）:**
所有新增动画（U1 箭头旋转、U3 脉冲、U8 FLIP 切换、U12 图例折叠、U15 tab 滑动）统一包裹：
```css
@media (prefers-reduced-motion: reduce) {
  animation: none;
  transition: none;
}
```
脉冲动画在 reduced-motion 下降级为静态高亮；FLIP/tab 滑动降级为即时切换。

**全局焦点环约定（§1 focus-states, High severity）:**
所有新增可交互元素（U1 分组标题、U2 popup trigger + 内部元素、U6 摘要栏指标、U16 `⋯` 按钮）统一：
```css
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```
不使用 `outline: none` 移除焦点环而不提供替代。

**触摸目标约定（§2 touch-target-size, CRITICAL）:**
所有新增可点击元素最小 44×44px（Apple HIG）。视觉高度不足时用 `padding` / `min-height` / `min-width` 扩展触摸区域。

### Definition of Done
- 17 个优化项全部实现
- 所有新增组件有单元测试
- 浏览器验证通过（Chrome + Safari mobile emulation）
- 无回归（现有交互全部保留）

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| U1 分组逻辑与分页冲突 | 分页按 status 而非 category，分组可能跨页不完整 | 分组在前端对当前页数据做，不改变后端分页逻辑。每组标题的"数量"显示当前页数量而非总数；组被截断时显示"还有更多 ›"提示 |
| U1 asset.category 为 optional | `category?: Category`（types/index.ts:47），null 时 grouping 崩溃 | 分组键用 `category?.id ?? '__uncategorized__'`，AssetGroupHeader 渲染 fallback icon+color |
| U2 popup 筛选器与深链冲突 | `?tab=` 深链可能依赖 type/category 状态 | 保持 `activeTypeIndex` 和 `activeCategoryId` 状态不变，只是 UI 从 tabs 改为 popup |
| U3 进度条依赖 `saved_amount` 字段 | Wish 类型可能没有此字段 | 已确认 `saved_amount?: string` 存在（types/index.ts:363），fallback 到 0 |
| U4 表单折叠可能影响表单验证 | 折叠区域内的必填字段验证时机 | 验证失败时自动展开含错误字段的折叠区块 + scrollIntoView + focus（见 U4 Approach） |
| U6 负债率零除 | total_assets=0 时 NaN/Infinity | `total_assets > 0 ? (liab/assets*100) : 0`，显示 `-` |
| U11 需后端改动 | 与纯前端 Non-Goal 冲突 | U11 移至 Deferred，待后端支持 next_payment_date 后再做 |
| 新增交互元素缺少 a11y | 所有新增可交互元素（分组标题/popup/摘要栏/长按）需键盘可操作 | 每个新增元素加 role/aria/tabindex/Enter-Space handler（见各 U 的 Approach） |

---

## Sources & Research

- 浏览器探索: demouser 登录 → 财务页三 tab 完整交互流程
- 源码审查: `AssetListPanel.vue` (1004L), `LiabilityListPanel.vue` (730L), `WishListPanel.vue` (681L), `AssetDetailPage.vue` (807L), `LiabilityDetailPage.vue` (423L), `WishDetailPage.vue` (787L)
- 相关计划: `docs/plans/2026-07-22-001-feat-finance-hub-overview-redesign-plan.md` (前序 Hub 重构)
- UI/UX Pro Max skill: 规则优先级 §1-§10

---

## Document Review

**Review date:** 2026-07-24
**Reviewers:** coherence-reviewer, feasibility-reviewer, design-lens-reviewer, scope-guardian-reviewer (headless mode)

**Applied fixes (safe_auto + gated_auto + manual integration):**
- U1: 分组键改为 `category?.id ?? '__uncategorized__'`（处理 optional category）+ 跨页截断"还有更多"提示 + a11y specs
- U2: 补充 categoryCounts 数据源保持说明
- U3: 补充 0%-但已设月存的视觉状态定义
- U4: 补充验证失败自动展开+滚动+聚焦的导航逻辑
- U5: 补充采纳状态 localStorage 持久化 + 更换策略流程
- U6: 零除保护 + 修复重复 tab 映射（月还->liabilities+滚动）+ a11y
- U9: 修复与 Deferred 的 scope 矛盾（移除 swipe 提示，仅做删除确认）
- U11: 移至 Deferred（需后端改动，与 Non-Goal 冲突）
- U12: 修正 priority-stripe 已是 4px 的事实
- U16: 补充可发现性（首次 toast + `⋯` 替代入口）+ vibrate 可选链
- Risks 表新增 5 项（U1 category null、U6 零除、U11 后端、a11y、跨页截断）

**Round 2 - UI/UX Pro Max 交互设计审核 (2026-07-24):**
- U1: 触摸目标 40px -> 44px（§2 touch-target-size CRITICAL）
- U2: 补充 popup focus trap + Escape 关闭 + focus restoration（§1 keyboard-nav + §9 modal-escape）
- U3: 进度条补充 ARIA `role="progressbar"` + `aria-valuenow/min/max`（§10 screen-reader-summary）+ reduced-motion 降级说明
- U7: action-sheet 删除项 `danger` 类型 + 分隔线 + 二次确认（§8 destructive-emphasis）
- U8/U15: 补充 reduced-motion 降级为即时切换/无动画（§7 reduced-motion High）
- U16: 长按阈值 500ms -> 400ms + `user-select:none;-webkit-touch-callout:none;` 抑制系统长按菜单（§2 gesture-conflicts）
- 新增「全局交互约定」区块（Verification Contract 下）：全局动画约定（reduced-motion）、全局焦点环约定（focus-visible 2px outline）、触摸目标约定（44px 最小）
