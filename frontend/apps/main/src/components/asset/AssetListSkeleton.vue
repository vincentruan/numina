<template>
  <div class="asset-list-skeleton">
    <!-- StatusSummaryGrid: 5 status tabs + toolbar -->
    <div class="skeleton-status-bar">
      <div class="status-tabs">
        <div v-for="i in 5" :key="i" class="status-tab">
          <van-skeleton :row="1" :row-width="i === 1 ? '32px' : '42px'" animate />
        </div>
      </div>
      <div class="toolbar-btn">
        <van-skeleton-avatar avatar-size="32px" avatar-shape="square" animate />
      </div>
    </div>

    <!-- Type tabs: 全部 / 实物 / 金融 -->
    <div class="skeleton-type-tabs">
      <div class="type-tab">
        <van-skeleton :row="1" row-width="28px" animate />
      </div>
      <div class="type-tab">
        <van-skeleton :row="1" row-width="28px" animate />
      </div>
      <div class="type-tab">
        <van-skeleton :row="1" row-width="28px" animate />
      </div>
    </div>

    <!-- Category nav: scrollable pill tabs -->
    <div class="skeleton-category-nav">
      <div class="cat-pill">
        <van-skeleton :row="1" row-width="32px" animate />
      </div>
      <div class="cat-pill">
        <van-skeleton :row="1" row-width="56px" animate />
      </div>
      <div class="cat-pill">
        <van-skeleton :row="1" row-width="52px" animate />
      </div>
      <div class="cat-pill">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
    </div>

    <!-- Search bar + sort button -->
    <div class="skeleton-search-bar">
      <div class="search-input">
        <van-skeleton :row="1" row-width="100%" animate />
      </div>
      <div class="sort-btn">
        <van-skeleton :row="1" row-width="56px" animate />
      </div>
    </div>

    <!-- Section header + view toggle -->
    <div class="skeleton-section-header">
      <van-skeleton :row="1" row-width="80px" animate />
      <van-skeleton-avatar avatar-size="28px" avatar-shape="square" animate />
    </div>

    <!-- Asset cards: 3 cards -->
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

/* ── Status bar (mirrors StatusSummaryGrid exactly) ── */
.skeleton-status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--card-bg);
  gap: 8px;
  border-bottom: 1px solid var(--color-hairline);
}
.status-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  flex: 1;
}
.status-tabs::-webkit-scrollbar {
  display: none;
}
.status-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--bg-secondary);
  flex-shrink: 0;
  min-height: 44px;
}
.status-tab :deep(.van-skeleton) {
  padding: 0;
}
.status-tab :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.toolbar-btn {
  flex-shrink: 0;
}

/* ── Type tabs (mirrors van-tabs) ── */
.skeleton-type-tabs {
  display: flex;
  justify-content: space-around;
  padding: 12px 16px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--color-hairline);
}
.type-tab {
  display: flex;
  justify-content: center;
}
.type-tab :deep(.van-skeleton) {
  padding: 0;
}
.type-tab :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}

/* ── Category nav (scrollable pill tabs) ── */
.skeleton-category-nav {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--color-hairline);
  overflow-x: auto;
}
.skeleton-category-nav::-webkit-scrollbar {
  display: none;
}
.cat-pill {
  flex-shrink: 0;
  padding: 6px 16px;
  border-radius: 30px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .cat-pill {
  background: rgba(255, 255, 255, 0.06);
}
.cat-pill :deep(.van-skeleton) {
  padding: 0;
}
.cat-pill :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}

/* ── Search bar ── */
.skeleton-search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--card-bg);
}
.search-input {
  flex: 1;
  min-height: 36px;
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  padding: 0 12px;
}
[data-theme='dark'] .search-input {
  background: rgba(255, 255, 255, 0.06);
}
.search-input :deep(.van-skeleton) {
  padding: 0;
}
.search-input :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.sort-btn {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 20px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .sort-btn {
  background: rgba(255, 255, 255, 0.06);
}
.sort-btn :deep(.van-skeleton) {
  padding: 0;
}
.sort-btn :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}

/* ── Section header ── */
.skeleton-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
}
.skeleton-section-header :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-section-header :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}

/* ── Asset cards list ── */
.skeleton-list {
  padding: 0 12px;
}
</style>
