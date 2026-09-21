<template>
  <div class="travel-list-skeleton">
    <!-- Month summary card -->
    <div class="skeleton-summary">
      <van-skeleton :row="2" row-width="60% 40%" animate />
    </div>

    <!-- Trip cards: 3 cards -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="trip-card">
        <van-skeleton :row="4" row-width="30% 60% 80% 50%" animate />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton for TravelTripPanel loading state
</script>

<style scoped>
.travel-list-skeleton {
  background: var(--bg-secondary);
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
.skeleton-summary :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-summary :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 10px;
  border-radius: 4px;
}
.skeleton-list {
  padding: 8px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.trip-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .trip-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.trip-card :deep(.van-skeleton) {
  padding: 0;
}
.trip-card :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 10px;
  border-radius: 4px;
}
</style>
