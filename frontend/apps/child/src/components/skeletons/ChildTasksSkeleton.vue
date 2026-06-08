<template>
  <div class="tasks-skeleton">
    <!-- Date navigation skeleton -->
    <div class="date-nav-skeleton">
      <van-skeleton-avatar avatar-size="36px" avatar-shape="round" animate />
      <van-skeleton :row="1" row-width="40%" animate class="date-text-skeleton" />
      <van-skeleton-avatar avatar-size="36px" avatar-shape="round" animate />
    </div>

    <!-- Balance hero skeleton — ochre gradient -->
    <div class="balance-card-skeleton">
      <van-skeleton :row="2" row-width="30% 50%" animate />
    </div>

    <!-- Chore list skeleton -->
    <ChoreCardSkeleton v-for="i in 4" :key="i" />
  </div>
</template>

<script setup lang="ts">
import ChoreCardSkeleton from './ChoreCardSkeleton.vue'
// Skeleton for ChildTasksPage
</script>

<style scoped>
.tasks-skeleton {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Date navigation */
.date-nav-skeleton {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  border: 1px solid var(--color-hairline);
  min-height: 48px;
}

.date-nav-skeleton :deep(.van-skeleton-avatar) {
  background: var(--color-surface-card);
}

[data-theme="dark"] .date-nav-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.08);
}

.date-text-skeleton {
  flex: 1;
  text-align: center;
}

.date-text-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.date-text-skeleton :deep(.van-skeleton__row) {
  height: 15px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

[data-theme="dark"] .date-text-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
}

/* Balance card — ochre/peach gradient */
.balance-card-skeleton {
  background: linear-gradient(135deg, var(--color-brand-ochre), var(--color-brand-peach));
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

[data-theme="dark"] .balance-card-skeleton {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-ochre-rgb), 0.16), rgba(var(--color-brand-peach-rgb), 0.10)),
    var(--color-surface-card);
}

.balance-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.balance-card-skeleton :deep(.van-skeleton__row) {
  height: 16px;
  margin-top: 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.1);
}

[data-theme="dark"] .balance-card-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

.balance-card-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}
</style>