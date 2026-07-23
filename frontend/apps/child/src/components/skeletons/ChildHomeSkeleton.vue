<template>
  <div class="home-skeleton">
    <!-- Hero card skeleton — matches the greeting-on-top + coins/ring layout -->
    <div class="hero-card-skeleton">
      <van-skeleton :row="1" row-width="55%" animate class="greeting-skeleton" />
      <div class="hero-body-skeleton">
        <div class="hero-coins-skeleton">
          <van-skeleton :row="1" row-width="45%" animate class="coin-total-skeleton" />
          <van-skeleton :row="3" row-width="30%" animate class="coin-tiers-skeleton" />
        </div>
        <van-skeleton-avatar avatar-size="80px" avatar-shape="round" animate class="ring-skeleton" />
      </div>
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

/* Hero card — soft neutral card matching the real layout */
.hero-card-skeleton {
  background: var(--color-surface-soft);
  border-radius: var(--radius-xl);
  padding: 28px 20px 24px;
  margin-bottom: var(--space-lg);
  border: 1px solid var(--color-hairline-soft);
}

[data-theme="dark"] .hero-card-skeleton {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02)),
    var(--color-surface-card);
  border-color: var(--color-hairline);
}

.hero-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.hero-card-skeleton :deep(.van-skeleton__row) {
  background: var(--skeleton-bg);
  border-radius: 4px;
}

.greeting-skeleton {
  margin: 0 auto 16px;
}
.greeting-skeleton :deep(.van-skeleton__row) {
  height: 16px;
  margin: 0 auto;
}

.hero-body-skeleton {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.hero-coins-skeleton {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.coin-total-skeleton :deep(.van-skeleton__row) {
  height: 28px;
}
.coin-tiers-skeleton :deep(.van-skeleton__row) {
  height: 12px;
}

.ring-skeleton {
  flex-shrink: 0;
}

.ring-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
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