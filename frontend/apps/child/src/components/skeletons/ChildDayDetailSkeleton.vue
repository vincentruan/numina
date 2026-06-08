<template>
  <div class="day-detail-skeleton">
    <!-- PageHeader skeleton -->
    <div class="header-skeleton">
      <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate class="back-icon-skeleton" />
      <van-skeleton :row="1" row-width="40%" animate class="title-skeleton" />
    </div>

    <!-- Section skeleton -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="30%" animate class="section-title-skeleton" />
      <ChoreCardSkeleton v-for="i in 2" :key="i" />
    </div>
  </div>
</template>

<script setup lang="ts">
import ChoreCardSkeleton from './ChoreCardSkeleton.vue'
// Skeleton for ChildDayDetailPage
</script>

<style scoped>
.day-detail-skeleton {
  background: var(--color-canvas);
  min-height: 100vh;
  padding-bottom: var(--space-lg);
}

/* Header skeleton */
.header-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  margin: var(--space-md);
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

/* Section skeleton */
.section-skeleton {
  margin: var(--space-md) var(--space-md) 0;
}

.section-title-skeleton :deep(.van-skeleton) {
  padding: 0;
  margin-bottom: 10px;
}

.section-title-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

[data-theme="dark"] .section-title-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
}
</style>