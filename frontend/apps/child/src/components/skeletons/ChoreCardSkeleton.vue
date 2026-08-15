<template>
  <div class="chore-card-skeleton">
    <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate />
    <div class="chore-info-skeleton">
      <van-skeleton :row="2" row-width="60% 30%" animate />
    </div>
    <van-skeleton :row="1" row-width="20%" animate class="btn-skeleton" />
  </div>
</template>

<script setup lang="ts">
// Skeleton for chore cards used in Home, Tasks, and DayDetail pages
</script>

<style scoped>
.chore-card-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  border: 1px solid var(--color-hairline);
  min-height: 56px;
}

.chore-card-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}

.chore-info-skeleton {
  flex: 1;
}

.chore-info-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.chore-info-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

.chore-info-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

.btn-skeleton :deep(.van-skeleton__row) {
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--skeleton-bg);
}
</style>