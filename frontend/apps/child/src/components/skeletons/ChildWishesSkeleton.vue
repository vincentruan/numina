<template>
  <div class="wishes-skeleton">
    <!-- Balance hero skeleton — peach feature card (matches BalanceHero variant="wishes") -->
    <div class="balance-hero-skeleton">
      <van-skeleton :row="1" row-width="35%" animate class="hero-balance-skeleton" />
      <van-skeleton :row="1" row-width="55%" animate class="hero-coins-skeleton" />
    </div>

    <!-- Stats strip skeleton — below the hero -->
    <div class="stats-strip-skeleton">
      <div class="stats-item-skeleton">
        <van-skeleton :row="1" row-width="28px" animate />
        <van-skeleton :row="1" row-width="40px" animate />
      </div>
      <div class="stats-divider-skeleton" />
      <div class="stats-item-skeleton">
        <van-skeleton :row="1" row-width="28px" animate />
        <van-skeleton :row="1" row-width="50px" animate />
      </div>
    </div>

    <!-- Constellation placeholder -->
    <div class="constellation-skeleton">
      <van-skeleton-avatar avatar-size="64px" avatar-shape="round" animate v-for="i in 3" :key="i" />
    </div>

    <!-- Section title skeleton -->
    <div class="section-title-skeleton">
      <van-skeleton :row="1" row-width="30%" animate />
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

/* Balance hero — peach feature card (matches BalanceHero variant="wishes") */
.balance-hero-skeleton {
  background: var(--color-brand-peach);
  border-radius: var(--radius-xl);
  padding: 24px 20px;
  margin-bottom: var(--space-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

[data-theme="dark"] .balance-hero-skeleton {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-peach-rgb), 0.14), rgba(var(--color-brand-peach-rgb), 0.06)),
    var(--color-surface-card);
}

.balance-hero-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.hero-balance-skeleton :deep(.van-skeleton__row) {
  height: 32px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.1);
}
[data-theme="dark"] .hero-balance-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

.hero-coins-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.1);
}
[data-theme="dark"] .hero-coins-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

/* Stats strip — matches .stats-strip */
.stats-strip-skeleton {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  background: var(--color-surface-soft);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
  margin-bottom: var(--space-lg);
}

.stats-item-skeleton {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stats-item-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.stats-item-skeleton :deep(.van-skeleton__row) {
  border-radius: 4px;
  background: var(--skeleton-bg);
}

.stats-item-skeleton :deep(.van-skeleton__row:first-child) {
  height: 22px;
}

.stats-item-skeleton :deep(.van-skeleton__row:last-child) {
  height: 14px;
}

.stats-divider-skeleton {
  width: 1px;
  height: 28px;
  background: var(--color-hairline);
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
