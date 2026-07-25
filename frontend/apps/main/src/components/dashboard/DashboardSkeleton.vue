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

    <!-- Finance Coach Card Skeleton (collapsed style matching the real component) -->
    <div class="skeleton-coach">
      <div class="skeleton-coach-header">
        <van-skeleton-avatar avatar-size="18px" avatar-shape="square" animate />
        <van-skeleton :row="1" row-width="80px" animate />
        <van-skeleton :row="1" row-width="50px" animate />
      </div>
    </div>

    <!-- Smart Reminders Skeleton (collapsed style) -->
    <div class="skeleton-reminders">
      <div class="skeleton-reminders-header">
        <van-skeleton-avatar avatar-size="18px" avatar-shape="square" animate />
        <van-skeleton :row="1" row-width="80px" animate />
        <van-skeleton :row="1" row-width="100px" animate />
      </div>
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
  background: var(--color-primary);
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

/* Coach & reminders collapsed skeleton rows */
.skeleton-coach,
.skeleton-reminders {
  background: var(--card-bg);
  border-radius: 12px;
  margin: 8px 0;
  padding: 12px 16px;
}
.skeleton-coach-header,
.skeleton-reminders-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.skeleton-coach-header :deep(.van-skeleton),
.skeleton-reminders-header :deep(.van-skeleton) {
  padding: 0;
}

.skeleton-assets {
  margin-top: 12px;
}
</style>
