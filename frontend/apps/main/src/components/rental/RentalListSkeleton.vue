<template>
  <div class="rental-list-skeleton">
    <!-- Tabs: 生效中 / 历史租约 -->
    <div class="skeleton-tabs">
      <div class="tab-item">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
      <div class="tab-item">
        <van-skeleton :row="1" row-width="64px" animate />
      </div>
    </div>

    <!-- Summary banner -->
    <div class="skeleton-summary">
      <div class="summary-row">
        <div v-for="i in 3" :key="i" class="summary-item">
          <van-skeleton :row="2" row-width="48px 72px" animate />
        </div>
      </div>
    </div>

    <!-- Contract cards: 3 cards -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="rental-card">
        <van-skeleton :row="3" row-width="30% 60% 80%" animate />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton for RentalListPanel loading state
</script>

<style scoped>
.rental-list-skeleton {
  background: var(--bg-secondary);
}
.skeleton-tabs {
  display: flex;
  justify-content: space-around;
  padding: 12px 16px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--color-hairline);
}
.tab-item {
  display: flex;
  justify-content: center;
}
.tab-item :deep(.van-skeleton) {
  padding: 0;
}
.tab-item :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}
.skeleton-summary {
  margin: 8px 12px;
  padding: 14px 16px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-summary {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.summary-row {
  display: flex;
  gap: 8px;
}
.summary-item {
  flex: 1;
  display: flex;
  justify-content: center;
}
.summary-item :deep(.van-skeleton) {
  padding: 0;
}
.summary-item :deep(.van-skeleton__row) {
  height: 12px;
  margin-top: 8px;
  border-radius: 4px;
}
.summary-item :deep(.van-skeleton__row:last-child) {
  height: 20px;
}
.skeleton-list {
  padding: 8px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rental-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .rental-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.rental-card :deep(.van-skeleton) {
  padding: 0;
}
.rental-card :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 10px;
  border-radius: 4px;
}
</style>
