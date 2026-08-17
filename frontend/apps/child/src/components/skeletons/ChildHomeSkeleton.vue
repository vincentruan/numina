<template>
  <div class="home-skeleton">
    <!-- Hero card skeleton — matches BalanceHero variant="home" (vertical layout) -->
    <div class="hero-card-skeleton">
      <van-skeleton :row="1" row-width="55%" animate class="greeting-skeleton" />
      <van-skeleton :row="1" row-width="40%" animate class="balance-skeleton" />
      <van-skeleton :row="2" row-width="30% 50%" animate class="coin-tiers-skeleton" />
    </div>

    <!-- Progress ring — separate row below the hero -->
    <div class="progress-ring-skeleton">
      <div class="ring-placeholder" />
    </div>

    <!-- Today's chores section -->
    <div class="section-skeleton">
      <van-skeleton :row="1" row-width="30%" animate class="section-title-skeleton" />
      <ChoreCardSkeleton v-for="i in 3" :key="i" />
    </div>

    <!-- Active challenges section -->
    <div class="challenge-skeleton">
      <div class="skeleton-challenge-card">
        <div class="skeleton-challenge-header">
          <van-skeleton-avatar avatar-size="22px" avatar-shape="square" animate />
          <van-skeleton :row="1" row-width="40%" animate />
        </div>
        <van-skeleton :row="1" row-width="100%" animate class="skeleton-challenge-bar" />
      </div>
    </div>

    <!-- Scenario entry card -->
    <div class="badge-entry-skeleton">
      <div class="badge-entry-info-skeleton">
        <van-skeleton-avatar avatar-size="28px" avatar-shape="square" animate />
        <div class="badge-entry-text-skeleton">
          <van-skeleton :row="2" row-width="50% 70%" animate />
        </div>
      </div>
    </div>

    <!-- Badge wall entry card -->
    <div class="badge-entry-skeleton">
      <div class="badge-entry-info-skeleton">
        <van-skeleton-avatar avatar-size="28px" avatar-shape="square" animate />
        <div class="badge-entry-text-skeleton">
          <van-skeleton :row="2" row-width="50% 70%" animate />
        </div>
      </div>
    </div>

    <!-- Manifesto summary card (always shown in skeleton — self-gates via v-if on real page) -->
    <div class="manifesto-skeleton">
      <div class="manifesto-head-skeleton">
        <van-skeleton-avatar avatar-size="20px" avatar-shape="square" animate />
        <van-skeleton :row="1" row-width="40%" animate />
      </div>
      <van-skeleton :row="1" row-width="60%" animate class="manifesto-excerpt-skeleton" />
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

/* Hero card — matches BalanceHero variant="home" (vertical layout) */
.hero-card-skeleton {
  background: var(--color-surface-soft);
  border-radius: var(--radius-xl);
  padding: 24px 20px;
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
  margin: 0 auto 12px;
}
.greeting-skeleton :deep(.van-skeleton__row) {
  height: 16px;
  margin: 0 auto;
}

.balance-skeleton {
  margin: 0 auto 12px;
}
.balance-skeleton :deep(.van-skeleton__row) {
  height: 32px;
  margin: 0 auto;
}

.coin-tiers-skeleton :deep(.van-skeleton__row) {
  height: 12px;
  margin: 0 auto;
  margin-top: 6px;
}
.coin-tiers-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

/* Progress ring — separate row below hero */
.progress-ring-skeleton {
  margin-bottom: var(--space-lg);
  display: flex;
  justify-content: center;
}
.ring-placeholder {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--color-surface-soft);
  border: 6px solid var(--color-surface-strong);
}
[data-theme="dark"] .ring-placeholder {
  background: var(--color-surface-card);
  border-color: rgba(255, 255, 255, 0.08);
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

/* Challenge section */
.challenge-skeleton {
  margin-top: var(--space-lg);
  margin-bottom: var(--space-lg);
}
.skeleton-challenge-card {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--color-hairline);
}
.skeleton-challenge-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.skeleton-challenge-header :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-challenge-header :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}
.skeleton-challenge-header :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}
.skeleton-challenge-bar :deep(.van-skeleton__row) {
  height: 8px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

/* Badge entry card (scenario / badges) */
.badge-entry-skeleton {
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  margin-bottom: var(--space-lg);
  border: 1px solid var(--color-hairline);
}
.badge-entry-info-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
}
.badge-entry-info-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}
.badge-entry-text-skeleton {
  flex: 1;
}
.badge-entry-text-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.badge-entry-text-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}
.badge-entry-text-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

/* Manifesto summary card */
.manifesto-skeleton {
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
  padding: 16px;
  border: 1px solid var(--color-hairline);
  margin-bottom: var(--space-lg);
}
.manifesto-head-skeleton {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.manifesto-head-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.manifesto-head-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}
.manifesto-head-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}
.manifesto-excerpt-skeleton :deep(.van-skeleton__row) {
  height: 16px;
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
