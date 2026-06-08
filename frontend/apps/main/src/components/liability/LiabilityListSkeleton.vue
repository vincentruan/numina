<template>
  <div class="liability-list-skeleton">
    <!-- Tabs skeleton (2 tabs) -->
    <div class="skeleton-tabs">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- Filter bar skeleton -->
    <div class="skeleton-filter-bar">
      <div class="filter-chips-skeleton">
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="40px" animate />
        </div>
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="50px" animate />
        </div>
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="60px" animate />
        </div>
        <div class="chip-skeleton">
          <van-skeleton :row="1" row-width="50px" animate />
        </div>
      </div>
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="50px" animate />
      </div>
    </div>

    <!-- Summary Banner skeleton -->
    <div class="summary-banner-skeleton">
      <div class="summary-top-skeleton">
        <div class="summary-main-skeleton">
          <van-skeleton :row="2" row-width="80px 120px" animate />
        </div>
        <div class="summary-count-skeleton">
          <van-skeleton :row="1" row-width="60px" animate />
        </div>
      </div>
      <div class="progress-bar-skeleton">
        <van-skeleton :row="1" row-width="100%" animate />
      </div>
      <div class="progress-text-skeleton">
        <van-skeleton :row="1" row-width="80px" animate />
      </div>
    </div>

    <!-- Liability cards skeleton (3 cards) -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="liability-card-skeleton">
        <van-skeleton :row="2" row-width="100% 60%" animate />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton component for LiabilityListPage loading state
</script>

<style scoped>
.liability-list-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
}

/* Tabs skeleton */
.skeleton-tabs {
  background: var(--card-bg);
  padding: 12px 16px;
}
.skeleton-tabs :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-tabs :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}

/* Filter bar skeleton */
.skeleton-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  overflow-x: auto;
}
[data-theme='dark'] .skeleton-filter-bar {
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

.filter-chips-skeleton {
  display: flex;
  gap: 6px;
  flex: 1;
}

.chip-skeleton {
  flex-shrink: 0;
  padding: 4px 14px;
  border-radius: 30px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .chip-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.chip-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.chip-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

.sort-btn-skeleton {
  flex-shrink: 0;
  padding: 4px 10px;
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

/* Summary Banner skeleton - matches gradient background */
.summary-banner-skeleton {
  margin: 12px 12px 4px;
  background: linear-gradient(135deg, #991b1b 0%, #dc2626 60%, #ea580c 100%);
  border-radius: 16px;
  padding: 20px;
}

/* White semi-transparent skeleton bars on gradient background */
.summary-banner-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.2) !important;
}

.summary-top-skeleton {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.summary-main-skeleton {
  flex: 1;
}
.summary-main-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.summary-main-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  margin-top: 6px;
}
.summary-main-skeleton :deep(.van-skeleton__row:last-child) {
  height: 36px;
  margin-top: 6px;
}

.summary-count-skeleton {
  padding-top: 4px;
}
.summary-count-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.summary-count-skeleton :deep(.van-skeleton__row) {
  height: 28px;
  width: 60px !important;
}

.progress-bar-skeleton {
  height: 6px;
  margin-bottom: 8px;
}
.progress-bar-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.progress-bar-skeleton :deep(.van-skeleton__row) {
  height: 6px;
  border-radius: 3px;
}

.progress-text-skeleton {
  display: flex;
  justify-content: flex-end;
}
.progress-text-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.progress-text-skeleton :deep(.van-skeleton__row) {
  height: 12px;
  width: 80px !important;
}

/* List skeleton */
.skeleton-list {
  padding: 8px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Liability card skeleton */
.liability-card-skeleton {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .liability-card-skeleton {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.liability-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.liability-card-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
}
.liability-card-skeleton :deep(.van-skeleton__row:first-child) {
  height: 16px;
  margin-top: 0;
}
</style>
