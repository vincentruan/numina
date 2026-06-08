<template>
  <div class="day-detail-skeleton">
    <!-- PageHeader skeleton -->
    <PageHeaderSkeleton class="with-margin" />

    <!-- Section skeleton -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="30%" animate class="section-title-skeleton" />
      <ChoreCardSkeleton v-for="i in 2" :key="i" />
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeaderSkeleton from './PageHeaderSkeleton.vue'
import ChoreCardSkeleton from './ChoreCardSkeleton.vue'
// Skeleton for ChildDayDetailPage
</script>

<style scoped>
.day-detail-skeleton {
  background: var(--color-canvas);
  min-height: 100vh;
  padding-bottom: var(--space-lg);
}

.with-margin {
  margin: var(--space-md);
  padding: 0;
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