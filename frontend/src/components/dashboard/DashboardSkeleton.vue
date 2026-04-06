<template>
  <div class="dashboard-skeleton">
    <!-- NetWorth Card Skeleton -->
    <div class="skeleton-overview">
      <van-skeleton :row="2" row-width="50% 80%" title-width="30%" animate />
      <div class="skeleton-detail">
        <van-skeleton :row="1" row-width="100%" animate />
        <van-skeleton :row="1" row-width="100%" animate />
      </div>
    </div>

    <!-- Status Summary Skeleton -->
    <div class="skeleton-status">
      <van-skeleton-avatar avatar-size="24px" />
      <van-skeleton-avatar avatar-size="24px" />
      <van-skeleton-avatar avatar-size="24px" />
      <van-skeleton-avatar avatar-size="24px" />
    </div>

    <!-- Asset Cards Skeleton -->
    <div class="skeleton-assets">
      <AssetCardSkeleton v-for="i in 3" :key="i" />
    </div>
  </div>
</template>

<script setup lang="ts">
import AssetCardSkeleton from '@/components/common/AssetCardSkeleton.vue'
</script>

<style scoped>
.dashboard-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding: 0 12px;
}
.skeleton-overview {
  background: linear-gradient(135deg, #1677ff 0%, #0052d9 50%, #2b3a8e 100%);
  padding: 24px 20px 16px;
  border-radius: 0;
}
.skeleton-overview :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-overview :deep(.van-skeleton__row),
.skeleton-overview :deep(.van-skeleton__title) {
  background: rgba(255, 255, 255, 0.2);
}
.skeleton-detail {
  display: flex;
  gap: 16px;
  margin-top: 16px;
  padding-top: 12px;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 12px 16px;
}
.skeleton-detail :deep(.van-skeleton) {
  flex: 1;
}
.skeleton-status {
  display: flex;
  justify-content: space-around;
  padding: 16px;
  background: var(--card-bg);
  margin-top: 8px;
}
.skeleton-assets {
  margin-top: 12px;
}
</style>