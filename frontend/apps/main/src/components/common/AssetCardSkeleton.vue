<template>
  <div class="asset-card-skeleton">
    <div class="skeleton-left">
      <van-skeleton-avatar avatar-size="88px" />
    </div>
    <div class="skeleton-right">
      <van-skeleton :row="3" row-width="60% 40% 80%" title-width="40%" animate />
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton component for AssetCard loading state
</script>

<style scoped>
.asset-card-skeleton {
  display: flex;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .asset-card-skeleton {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
.skeleton-left {
  flex-shrink: 0;
  margin-right: 12px;
}
.skeleton-right {
  flex: 1;
  min-width: 0;
}
.skeleton-right :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-right :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
}
.skeleton-right :deep(.van-skeleton__title) {
  height: 15px;
}
</style>