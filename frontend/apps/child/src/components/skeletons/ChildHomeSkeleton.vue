<template>
  <div class="home-skeleton">
    <!-- Hero card skeleton — ochre feature card -->
    <div class="hero-card-skeleton">
      <van-skeleton :row="1" row-width="40%" animate class="label-skeleton" />
      <van-skeleton :row="1" row-width="60%" animate class="balance-skeleton" />
      <van-skeleton-avatar avatar-size="80px" avatar-shape="round" animate class="ring-skeleton" />
    </div>

    <!-- Today's chores section -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="30%" animate class="section-title-skeleton" />
      <ChoreCardSkeleton v-for="i in 3" :key="i" />
    </div>

    <!-- Wish preview skeleton -->
    <div class="wish-preview-skeleton">
      <van-skeleton-avatar avatar-size="32px" avatar-shape="round" animate />
      <div class="wish-preview-info-skeleton">
        <van-skeleton :row="2" row-width="50% 80%" animate />
      </div>
    </div>

    <!-- Calendar section -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="30%" animate class="section-title-skeleton" />
      <van-skeleton :row="1" row-width="100%" animate class="calendar-skeleton" />
    </div>
  </div>
</template>

<script setup lang="ts">
import ChoreCardSkeleton from './ChoreCardSkeleton.vue'
// Skeleton for ChildHomePage
</script>

<style scoped>
.home-skeleton {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* Hero card — ochre feature card */
.hero-card-skeleton {
  background: var(--color-brand-ochre);
  border-radius: var(--radius-xl);
  padding: 32px 20px;
  text-align: center;
  margin-bottom: var(--space-lg);
}

[data-theme="dark"] .hero-card-skeleton {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-ochre-rgb), 0.16), rgba(var(--color-brand-ochre-rgb), 0.08)),
    var(--color-surface-card);
}

.hero-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.hero-card-skeleton :deep(.van-skeleton__row) {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}

[data-theme="dark"] .hero-card-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

.label-skeleton :deep(.van-skeleton__row) {
  height: 13px;
}

.balance-skeleton :deep(.van-skeleton__row) {
  height: 32px;
}

.ring-skeleton {
  margin-top: 20px;
}

.ring-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.1);
}

[data-theme="dark"] .ring-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.08);
}

/* Sections */
.section-skeleton {
  margin-bottom: var(--space-lg);
}

.section-title-skeleton :deep(.van-skeleton) {
  padding: 0;
  margin-bottom: 12px;
}

.section-title-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

/* Wish preview */
.wish-preview-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  margin-bottom: var(--space-lg);
  border: 1px solid var(--color-hairline);
}

.wish-preview-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}

.wish-preview-info-skeleton {
  flex: 1;
}

.wish-preview-info-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.wish-preview-info-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

.wish-preview-info-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

/* Calendar placeholder */
.calendar-skeleton :deep(.van-skeleton__row) {
  height: 100px;
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
}

[data-theme="dark"] .calendar-skeleton :deep(.van-skeleton__row) {
  background: var(--color-surface-card);
}
</style>