<template>
  <div class="day-detail-skeleton">
    <!-- PageHeader skeleton -->
    <PageHeaderSkeleton class="with-margin" />

    <!-- Chores section -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="30%" animate class="section-title-skeleton" />
      <div v-for="i in 2" :key="'c' + i" class="event-card-skeleton">
        <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate />
        <div class="event-info-skeleton">
          <van-skeleton :row="2" row-width="60% 30%" animate />
        </div>
        <div class="status-tag-skeleton">
          <van-skeleton :row="1" row-width="32px" animate />
        </div>
      </div>
    </div>

    <!-- Wishes section -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="25%" animate class="section-title-skeleton" />
      <div v-for="i in 1" :key="'w' + i" class="event-card-skeleton">
        <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate />
        <div class="event-info-skeleton">
          <van-skeleton :row="2" row-width="50% 35%" animate />
        </div>
        <div class="status-tag-skeleton">
          <van-skeleton :row="1" row-width="32px" animate />
        </div>
      </div>
    </div>

    <!-- Milestones section -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="35%" animate class="section-title-skeleton" />
      <div v-for="i in 1" :key="'m' + i" class="event-card-skeleton">
        <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate />
        <div class="event-info-skeleton">
          <van-skeleton :row="1" row-width="50%" animate />
        </div>
        <div class="status-tag-skeleton">
          <van-skeleton :row="1" row-width="40px" animate />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import PageHeaderSkeleton from './PageHeaderSkeleton.vue'
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

/* Event card — matches .event-card in ChildDayDetailPage */
.event-card-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  border: 1px solid var(--color-hairline);
  margin-bottom: 8px;
}

.event-card-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
  flex-shrink: 0;
}

.event-info-skeleton {
  flex: 1;
}

.event-info-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.event-info-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

.event-info-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

.status-tag-skeleton {
  flex-shrink: 0;
}

.status-tag-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.status-tag-skeleton :deep(.van-skeleton__row) {
  height: 24px;
  border-radius: var(--radius-pill);
  background: var(--skeleton-bg);
}
</style>
