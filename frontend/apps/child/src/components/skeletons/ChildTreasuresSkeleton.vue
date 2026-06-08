<template>
  <div class="treasures-skeleton">
    <!-- Summary card skeleton — lavender feature card -->
    <div class="summary-card-skeleton">
      <van-skeleton :row="3" row-width="40% 60% 80%" animate />
    </div>

    <!-- Grid skeleton -->
    <div class="grid-skeleton">
      <TreasureCardSkeleton v-for="i in 4" :key="i" />
    </div>
  </div>
</template>

<script setup lang="ts">
import TreasureCardSkeleton from './TreasureCardSkeleton.vue'
// Skeleton for ChildTreasuresPage
</script>

<style scoped>
.treasures-skeleton {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

/* Summary card — lavender feature card */
.summary-card-skeleton {
  background: var(--color-brand-lavender);
  border-radius: var(--radius-xl);
  padding: 32px 20px;
  text-align: center;
  margin-bottom: var(--space-lg);
}

[data-theme="dark"] .summary-card-skeleton {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-lavender-rgb), 0.16), rgba(var(--color-brand-lavender-rgb), 0.08)),
    var(--color-surface-card);
}

.summary-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.summary-card-skeleton :deep(.van-skeleton__row) {
  height: 48px;
  margin-top: 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.1);
}

[data-theme="dark"] .summary-card-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

.summary-card-skeleton :deep(.van-skeleton__row:first-child) {
  height: 18px;
  margin-top: 0;
}

.summary-card-skeleton :deep(.van-skeleton__row:nth-child(2)) {
  height: 14px;
}

/* Grid layout */
.grid-skeleton {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
</style>