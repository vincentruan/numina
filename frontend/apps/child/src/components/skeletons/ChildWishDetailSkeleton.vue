<template>
  <div class="wish-detail-skeleton">
    <!-- PageHeader skeleton -->
    <div class="header-skeleton">
      <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate class="back-icon-skeleton" />
      <van-skeleton :row="1" row-width="40%" animate class="title-skeleton" />
    </div>

    <!-- Wish card skeleton -->
    <WishCardSkeleton />
  </div>
</template>

<script setup lang="ts">
import WishCardSkeleton from './WishCardSkeleton.vue'
// Skeleton for ChildWishDetailPage
</script>

<style scoped>
.wish-detail-skeleton {
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
</style>