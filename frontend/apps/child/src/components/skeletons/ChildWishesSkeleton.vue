<template>
  <div class="wishes-skeleton">
    <!-- Hero banner skeleton — peach feature card -->
    <div class="hero-banner-skeleton">
      <div class="hero-stat-skeleton">
        <van-skeleton :row="2" row-width="100% 60%" animate />
      </div>
      <div class="hero-divider-skeleton" />
      <div class="hero-stat-skeleton">
        <van-skeleton :row="2" row-width="80% 100%" animate />
      </div>
      <div class="hero-divider-skeleton" />
      <div class="hero-stat-skeleton">
        <van-skeleton :row="2" row-width="80% 100%" animate />
      </div>
    </div>

    <!-- Section title skeleton -->
    <div class="section-title-skeleton">
      <van-skeleton :row="1" row-width="30%" animate />
    </div>

    <!-- Constellation placeholder -->
    <div class="constellation-skeleton">
      <van-skeleton-avatar avatar-size="64px" avatar-shape="round" animate v-for="i in 3" :key="i" />
    </div>

    <!-- Wish cards skeleton -->
    <WishCardSkeleton v-for="i in 2" :key="i" />

    <!-- FAB skeleton -->
    <div class="fab-skeleton">
      <van-skeleton-avatar avatar-size="52px" avatar-shape="round" animate />
    </div>
  </div>
</template>

<script setup lang="ts">
import WishCardSkeleton from './WishCardSkeleton.vue'
// Skeleton for ChildWishesPage
</script>

<style scoped>
.wishes-skeleton {
  background: var(--color-canvas);
  min-height: 100vh;
  padding: var(--space-md) var(--space-md) 140px;
}

/* Hero banner — peach feature card */
.hero-banner-skeleton {
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: var(--color-brand-peach);
  border-radius: var(--radius-xl);
  padding: 32px 16px;
  margin-bottom: var(--space-lg);
}

[data-theme="dark"] .hero-banner-skeleton {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-peach-rgb), 0.14), rgba(var(--color-brand-peach-rgb), 0.06)),
    var(--color-surface-card);
}

.hero-stat-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.hero-stat-skeleton :deep(.van-skeleton__row) {
  height: 24px;
  margin-top: 2px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.1);
}

[data-theme="dark"] .hero-stat-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

.hero-stat-skeleton :deep(.van-skeleton__row:first-child) {
  height: 32px;
  margin-top: 0;
}

.hero-divider-skeleton {
  width: 1px;
  height: 36px;
  background: var(--color-hairline);
  opacity: 0.4;
}

/* Section title */
.section-title-skeleton {
  margin-bottom: 12px;
}

.section-title-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.section-title-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

/* Constellation placeholder */
.constellation-skeleton {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-bottom: var(--space-lg);
}

.constellation-skeleton :deep(.van-skeleton-avatar) {
  background: var(--color-surface-soft);
}

[data-theme="dark"] .constellation-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.08);
}

/* FAB skeleton */
.fab-skeleton {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 52px;
  height: 52px;
  z-index: 10;
}

.fab-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
  width: 52px;
  height: 52px;
}
</style>