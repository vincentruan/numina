# Skeleton Screen Optimization Design Spec

Created: 2026-06-07
Status: Draft
Author: Claude (Brainstorming Session)

## Overview

为 WishListPage（心愿列表）和 LiabilityListPage（负债列表）添加骨架屏，优化弱网环境下的首次加载体验。采用与现有 DashboardPage、AssetListPage 一致的页面级骨架屏模式，并与 NProgress 进度条实现分层协作。

## Problem Statement

### Current State

| 页面 | 骨架屏 | NProgress 使用 | 弱网体验 |
|------|--------|---------------|---------|
| DashboardPage | ✅ DashboardSkeleton | 路由级 + 批量操作 | 良好 |
| AssetListPage | ✅ AssetCardSkeleton | 路由级 | 艹好 |
| WishListPage | ❌ 无 | 仅路由级 beforeAfterEach | 空白等待 |
| LiabilityListPage | ❌ 无 | 仅路由级 beforeAfterEach | 空白等待 |

### Issues

1. WishListPage 和 LiabilityListPage 在弱网环境下首次加载时，用户只能看到空白页面等待数据返回
2. 路由级 NProgress 进度条在所有页面都会触发，但无法区分页面是否有骨架屏
3. 详情页（WishDetailPage、AssetDetailPage 等）在 onMounted 中手动调用 NProgress，与路由级 NProgress 叠加

## Design Goals

1. 为 WishListPage 和 LiabilityListPage 添加页面级骨架屏组件
2. 实现骨架屏与 NProgress 的分层协作机制
3. 保持与现有骨架屏实现模式的一致性
4. 首次加载和下拉刷新两种场景都需要优化

## Solution Architecture

### 1. Route Meta Field 标识

在路由配置中使用 `meta.hasSkeleton` 标识页面是否有骨架屏：

```typescript
// router/index.ts
{
  path: 'wishes',
  name: 'WishList',
  component: () => import('@/pages/WishListPage.vue'),
  meta: { hasSkeleton: true }
},
{
  path: 'liabilities',
  name: 'LiabilityList',
  component: () => import('@/pages/LiabilityListPage.vue'),
  meta: { hasSkeleton: true }
},
// 现有骨架屏页面也添加标识
{
  path: '',
  name: 'Dashboard',
  component: () => import('@/pages/DashboardPage.vue'),
  meta: { hasSkeleton: true }
},
{
  path: 'assets',
  name: 'AssetList',
  component: () => import('@/pages/AssetListPage.vue'),
  meta: { hasSkeleton: true }
}
```

### 2. NProgress 路由守卫协作逻辑

修改 router/index.ts 的 afterEach 逻辑：

```typescript
// router/index.ts
router.beforeEach((to, _from, next) => {
  NProgress.start()
  // ... existing auth checks ...
})

router.afterEach((to) => {
  // 有骨架屏的页面：立即完成 NProgress，让骨架屏接管视觉反馈
  if (to.meta.hasSkeleton) {
    NProgress.done()
  }
  // 无骨架屏的页面：保留 NProgress 状态，
  // 等待页面 onMounted 中的数据加载完成后调用 done()
})
```

### 3. 骨架屏显示逻辑

#### 首次加载

骨架屏在 `loading && data.length === 0` 时显示：

```vue
<!-- WishListPage.vue -->
<template>
  <div class="wish-list-page">
    <van-nav-bar :title="t('wish.nav.title')" />

    <!-- Skeleton -->
    <WishListSkeleton v-if="wishStore.loading && wishes.length === 0" />

    <!-- Actual Content -->
    <template v-else>
      <van-tabs v-model:active="activeTab" sticky>...</van-tabs>
      <div class="sort-bar">...</div>
      <div class="list-content">...</div>
    </template>

    <div class="fab">...</div>
  </div>
</template>
```

#### 下拉刷新

下拉刷新时骨架屏不显示，依赖 `van-pull-refresh` 的内置下拉指示器。刷新完成后数据自然更新。

理由：下拉刷新是用户主动操作，内置指示器已提供足够的视觉反馈；骨架屏主要用于首次加载的被动等待场景。

### 4. Skeleton Component Structure

#### WishListSkeleton

基于 WishListPage 页面结构设计：

```
┌─────────────────────────────────┐
│  NavBar (可选，路由级已覆盖)      │
├─────────────────────────────────┤
│  Tabs 骨架 (3个 tab 占位)        │
│  ┌─────┬─────┬─────┐            │
│  │     │     │     │            │
│  └─────┴─────┴─────┘            │
├─────────────────────────────────┤
│  Sort bar 骨架                  │
│  ┌────┐ ┌────┐ ┌────┐           │
│  │    │ │    │ │    │           │
│  └────┘ └────┘ └────┘           │
├─────────────────────────────────┤
│  List 骨架 (3-4个 wish-item)    │
│  ┌──┬────┬──────────────────┐  │
│  │▌│ ○  │ ██████  ████████ │  │  <- priority stripe + icon + body
│  │▌│    │ ████    ████      │  │
│  └──┴────┴──────────────────┘  │
│  ┌──┬────┬──────────────────┐  │
│  │▌│ ○  │ ██████  ████████ │  │
│  │▌│    │ ████    ████      │  │
│  └──┴────┴──────────────────┘  │
│  ┌──┬────┬──────────────────┐  │
│  │▌│ ○  │ ██████  ████████ │  │
│  │▌│    │ ████    ████      │  │
│  └──┴────┴──────────────────┘  │
└─────────────────────────────────┘
```

关键元素：
- Priority stripe: 4px 左侧色条（灰色占位）
- Icon anchor: 44px 宽度，圆形骨架
- Body: 两行骨架（name行 + badge行）
- 使用 Vant `van-skeleton` 和 `van-skeleton-avatar` 组件

#### LiabilityListSkeleton

基于 LiabilityListPage 页面结构设计：

```
┌─────────────────────────────────┐
│  PageHeader (可选，路由级已覆盖) │
├─────────────────────────────────┤
│  Tabs 骨架 (2个 tab 占位)        │
│  ┌─────────┬─────────┐          │
│  │         │         │          │
│  └─────────┴─────────┘          │
├─────────────────────────────────┤
│  Filter bar 骨架                │
│  ┌───┬───┬───┬───┐ ┌────┐      │
│  │   │   │   │   │ │    │      │
│  └───┴───┴───┴───┘ └────┘      │
├─────────────────────────────────┤
│  Summary Banner 骨架            │
│  ┌─────────────────────────────┐│
│  │ ████████████████████████████││ <- 红色渐变背景
│  │ ████████        ████████    ││ <- 金额 + 数量
│  │ ██████████████████████████  ││ <- 进度条
│  │ ████████        ██████      ││ <- 进度文字
│  └─────────────────────────────┘│
├─────────────────────────────────┤
│  List 骨架 (3个 liability-card) │
│  ┌─────────────────────────────┐│
│  │ ████████████████████████████││
│  │ ████████    ████            ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ ████████████████████████████││
│  │ ████████    ████            ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ ████████████████████████████││
│  │ ████████    ████            ││
│  └─────────────────────────────┘│
└─────────────────────────────────┘
```

关键元素：
- Summary Banner: 红色渐变背景（`linear-gradient(135deg, #991b1b, #dc2626, #ea580c)`）
- Banner 内骨架使用白色半透明骨架条（`rgba(255, 255, 255, 0.2)`）
- 负债卡片相对简单，无 priority stripe
- 使用 Vant `van-skeleton` 组件

## Implementation Plan

### Phase 1: Route Configuration

1. 为 WishList、LiabilityList、Dashboard、AssetList 路由添加 `meta.hasSkeleton`
2. 修改 `router.afterEach` 添加条件判断逻辑

### Phase 2: WishListSkeleton Component

1. 创建 `frontend/apps/main/src/components/wishes/WishListSkeleton.vue`
2. 实现骨架结构（tabs + sort bar + wish items）
3. 在 WishListPage 中集成骨架屏显示逻辑

### Phase 3: LiabilityListSkeleton Component

1. 创建 `frontend/apps/main/src/components/liability/LiabilityListSkeleton.vue`
2. 实现骨架结构（tabs + filter bar + summary banner + liability cards）
3. 在 LiabilityListPage 中集成骨架屏显示逻辑

### Phase 4: Verification

1. 模拟弱网环境测试骨架屏显示效果
2. 验证 NProgress 与骨架屏的分层协作
3. 确保下拉刷新不触发骨架屏

## Technical Constraints

1. 使用 Vant 4 的 `van-skeleton` 和 `van-skeleton-avatar` 组件
2. 遵循现有 DashboardSkeleton 和 AssetCardSkeleton 的实现模式
3. 骨架屏样式需适配 dark mode（使用 CSS 变量）
4. 所有 UI 字串已 i18n 化，骨架屏不需要文字（纯视觉占位）

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| 骨架屏与实际内容结构不一致 | 严格按照页面实际结构设计骨架屏 |
| NProgress 条件判断遗漏页面 | 为所有骨架屏页面添加 meta 标识，包括现有页面 |
| 下拉刷新时误触发骨架屏 | 使用 `loading && data.length === 0` 条件，刷新时数据已存在 |

## Success Criteria

1. WishListPage 和 LiabilityListPage 在弱网首次加载时显示骨架屏
2. 有骨架屏的页面，路由级 NProgress 在 afterEach 立即完成
3. 无骨架屏的页面，NProgress 保持现有行为
4. 下拉刷新时骨架屏不显示，依赖 van-pull-refresh 内置指示器
5. Dark mode 下骨架屏样式正确显示