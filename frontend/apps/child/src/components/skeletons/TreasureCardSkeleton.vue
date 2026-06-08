<template>
  <div class="treasure-card-skeleton">
    <van-skeleton-avatar avatar-size="100px" avatar-shape="square" animate class="img-skeleton" />
    <div class="card-body-skeleton">
      <van-skeleton :row="2" row-width="80% 50%" animate />
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton for treasure cards used in Treasures page
</script>

<style scoped>
.treasure-card-skeleton {
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--color-hairline);
}

.img-skeleton {
  width: 100%;
  height: 100px;
  border-radius: 16px 16px 0 0;
}

.img-skeleton :deep(.van-skeleton-avatar) {
  background: var(--color-surface-card);
  width: 100%;
  height: 100px;
}

.card-body-skeleton {
  padding: 10px 12px;
}

.card-body-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.card-body-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

.card-body-skeleton :deep(.van-skeleton__row:first-child) {
  height: 14px;
  margin-top: 0;
}
</style>