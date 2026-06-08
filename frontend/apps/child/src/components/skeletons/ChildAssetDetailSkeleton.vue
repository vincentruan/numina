<template>
  <div class="asset-detail-skeleton">
    <!-- PageHeader skeleton -->
    <div class="header-skeleton">
      <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate class="back-icon-skeleton" />
      <van-skeleton :row="1" row-width="40%" animate class="title-skeleton" />
    </div>

    <!-- Asset card skeleton -->
    <div class="asset-card-skeleton">
      <van-skeleton-avatar avatar-size="200px" avatar-shape="square" animate class="img-skeleton" />
      <div class="asset-info-skeleton">
        <van-skeleton :row="1" row-width="50%" animate class="name-skeleton" />
        <van-skeleton :row="3" row-width="40% 60% 50%" animate class="info-rows-skeleton" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton for ChildAssetDetailPage
</script>

<style scoped>
.asset-detail-skeleton {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: var(--space-md);
}

/* Header skeleton */
.header-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  margin-bottom: var(--space-md);
}

.back-icon-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}

[data-theme="dark"] .back-icon-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}

.title-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.title-skeleton :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

[data-theme="dark"] .title-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
}

/* Asset card */
.asset-card-skeleton {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-hairline);
  overflow: hidden;
}

.img-skeleton {
  width: 100%;
  border-radius: var(--radius-lg);
}

.img-skeleton :deep(.van-skeleton-avatar) {
  background: var(--color-surface-card);
  width: 100%;
  height: 200px;
}

[data-theme="dark"] .img-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.08);
}

.asset-info-skeleton {
  padding: var(--space-lg);
}

.name-skeleton :deep(.van-skeleton) {
  padding: 0;
  margin-bottom: 16px;
}

.name-skeleton :deep(.van-skeleton__row) {
  height: 20px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

[data-theme="dark"] .name-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
}

.info-rows-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.info-rows-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 10px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

[data-theme="dark"] .info-rows-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
}

.info-rows-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}
</style>