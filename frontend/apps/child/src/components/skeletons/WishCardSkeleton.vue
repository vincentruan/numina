<template>
  <div class="wish-card-skeleton">
    <div class="wish-header-skeleton">
      <van-skeleton-avatar avatar-size="48px" avatar-shape="square" animate />
      <div class="wish-meta-skeleton">
        <van-skeleton :row="2" row-width="50% 30%" animate />
      </div>
    </div>
    <van-skeleton :row="1" row-width="100%" animate class="progress-skeleton" />
  </div>
</template>

<script setup lang="ts">
// Skeleton for wish cards used in Wishes and WishDetail pages
</script>

<style scoped>
.wish-card-skeleton {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  border: 1px solid var(--color-hairline);
  border-left: 4px solid var(--color-brand-ochre);
  margin-bottom: 12px;
}

.wish-header-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.wish-header-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
  border-radius: var(--radius-lg);
}

[data-theme="dark"] .wish-header-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}

.wish-meta-skeleton {
  flex: 1;
}

.wish-meta-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.wish-meta-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

[data-theme="dark"] .wish-meta-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
}

.wish-meta-skeleton :deep(.van-skeleton__row:first-child) {
  height: 16px;
  margin-top: 0;
}

.progress-skeleton :deep(.van-skeleton__row) {
  height: 12px;
  border-radius: 6px;
  background: var(--color-surface-strong);
}

[data-theme="dark"] .progress-skeleton :deep(.van-skeleton__row) {
  background: var(--color-surface-strong);
}
</style>