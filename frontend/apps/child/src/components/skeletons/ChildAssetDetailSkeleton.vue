<template>
  <div class="asset-detail-skeleton">
    <!-- PageHeader skeleton -->
    <PageHeaderSkeleton />

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
import PageHeaderSkeleton from './PageHeaderSkeleton.vue'
// Skeleton for ChildAssetDetailPage
</script>

<style scoped>
.asset-detail-skeleton {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: var(--space-md);
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

.info-rows-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.info-rows-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 10px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

.info-rows-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}
</style>