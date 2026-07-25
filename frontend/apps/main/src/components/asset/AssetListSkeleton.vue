<template>
  <div class="asset-list-skeleton">
    <!-- StatusSummaryGrid: 5 status tabs (全部/使用中/闲置/已售/已退休) + toolbar -->
    <div class="skeleton-status-bar">
      <div v-for="i in 5" :key="i" class="status-tab-skeleton">
        <van-skeleton :row="1" :row-width="i === 1 ? '28px' : '36px'" animate />
      </div>
      <div class="toolbar-btn-skeleton">
        <van-skeleton-avatar avatar-size="28px" avatar-shape="square" animate />
      </div>
    </div>

    <!-- Type tabs: 全部 / 实物 / 金融 -->
    <div class="skeleton-type-tabs">
      <div class="type-tab-skeleton">
        <van-skeleton :row="1" row-width="24px" animate />
      </div>
      <div class="type-tab-skeleton">
        <van-skeleton :row="1" row-width="24px" animate />
      </div>
      <div class="type-tab-skeleton">
        <van-skeleton :row="1" row-width="24px" animate />
      </div>
    </div>

    <!-- Category nav: scrollable pill tabs -->
    <div class="skeleton-category-nav">
      <div class="cat-pill-skeleton">
        <van-skeleton :row="1" row-width="28px" animate />
      </div>
      <div class="cat-pill-skeleton">
        <van-skeleton :row="1" row-width="52px" animate />
      </div>
      <div class="cat-pill-skeleton">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
      <div class="cat-pill-skeleton">
        <van-skeleton :row="1" row-width="56px" animate />
      </div>
    </div>

    <!-- Search bar + sort button -->
    <div class="skeleton-search-bar">
      <div class="search-input-skeleton">
        <van-skeleton :row="1" row-width="100%" animate />
      </div>
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="52px" animate />
      </div>
    </div>

    <!-- Section header + view toggle -->
    <div class="skeleton-section-header">
      <van-skeleton :row="1" row-width="72px" animate />
      <van-skeleton-avatar avatar-size="24px" avatar-shape="square" animate />
    </div>

    <!-- Asset cards: 3 cards (matching AssetCardSkeleton layout) -->
    <div class="skeleton-list">
      <AssetCardSkeleton v-for="i in 3" :key="i" />
    </div>
  </div>
</template>

<script setup lang="ts">
import AssetCardSkeleton from '@/components/common/AssetCardSkeleton.vue'
</script>

<style scoped>
.asset-list-skeleton {
  background: var(--bg-secondary);
}

/* ── Status bar (mirrors StatusSummaryGrid) ── */
.skeleton-status-bar {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: var(--card-bg);
}
.status-tab-skeleton {
  flex: 1;
  display: flex;
  justify-content: center;
}
.status-tab-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.status-tab-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.toolbar-btn-skeleton {
  flex-shrink: 0;
  margin-left: 4px;
  padding-left: 8px;
  border-left: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
}

/* ── Type tabs (mirrors van-tabs: 全部/实物/金融) ── */
.skeleton-type-tabs {
  display: flex;
  justify-content: space-around;
  padding: 10px 16px;
  background: var(--card-bg);
  border-top: 1px solid var(--separator, rgba(0, 0, 0, 0.04));
}
.type-tab-skeleton {
  display: flex;
  justify-content: center;
}
.type-tab-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.type-tab-skeleton :deep(.van-skeleton__row) {
  height: 15px;
  border-radius: 4px;
}

/* ── Category nav (scrollable pill tabs) ── */
.skeleton-category-nav {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--card-bg);
  border-top: 1px solid var(--separator, rgba(0, 0, 0, 0.04));
  overflow-x: auto;
}
.cat-pill-skeleton {
  flex-shrink: 0;
  padding: 4px 14px;
  border-radius: 30px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .cat-pill-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.cat-pill-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.cat-pill-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

/* ── Search bar ── */
.skeleton-search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px 8px;
  background: var(--card-bg);
}
.search-input-skeleton {
  flex: 1;
  min-height: 36px;
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  padding: 0 12px;
}
[data-theme='dark'] .search-input-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.search-input-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.search-input-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.sort-btn-skeleton {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 20px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .sort-btn-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.sort-btn-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.sort-btn-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

/* ── Section header ── */
.skeleton-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px 6px;
}
.skeleton-section-header :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-section-header :deep(.van-skeleton__row) {
  height: 15px;
  border-radius: 4px;
}

/* ── Asset cards list ── */
.skeleton-list {
  padding: 0 12px;
}
</style>
