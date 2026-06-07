<template>
  <div class="wish-list-skeleton">
    <!-- Tabs skeleton -->
    <div class="skeleton-tabs">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- Sort bar skeleton -->
    <div class="skeleton-sort-bar">
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
      <div class="sort-btn-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
      </div>
    </div>

    <!-- Wish items skeleton (3 items) -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="wish-item-skeleton">
        <!-- Priority stripe -->
        <div class="priority-stripe-skeleton" />
        <!-- Icon anchor -->
        <div class="wish-icon-skeleton">
          <van-skeleton-avatar avatar-size="44px" avatar-shape="round" animate />
        </div>
        <!-- Body: two rows -->
        <div class="wish-body-skeleton">
          <van-skeleton :row="2" row-width="70% 50%" animate />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton component for WishListPage loading state
</script>

<style scoped>
.wish-list-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
}

/* Tabs skeleton */
.skeleton-tabs {
  background: var(--card-bg);
  padding: 12px 16px;
}
.skeleton-tabs :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-tabs :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}

/* Sort bar skeleton */
.skeleton-sort-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--separator);
}
.sort-btn-skeleton {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 30px;
  background: rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
}
[data-theme='dark'] .sort-btn-skeleton {
  background: rgba(255, 255, 255, 0.06);
}
.sort-btn-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.sort-btn-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

/* List skeleton */
.skeleton-list {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Wish item skeleton */
.wish-item-skeleton {
  display: flex;
  align-items: stretch;
  background: var(--card-bg);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  min-height: 72px;
}
[data-theme='dark'] .wish-item-skeleton {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

/* Priority stripe skeleton (gray placeholder) */
.priority-stripe-skeleton {
  width: 4px;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.12);
}
[data-theme='dark'] .priority-stripe-skeleton {
  background: rgba(255, 255, 255, 0.12);
}

/* Icon anchor */
.wish-icon-skeleton {
  width: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 2px;
}
.wish-icon-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .wish-icon-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}

/* Body skeleton */
.wish-body-skeleton {
  flex: 1;
  min-width: 0;
  padding: 12px 12px 12px 0;
  display: flex;
  flex-direction: column;
}
.wish-body-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.wish-body-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
}
.wish-body-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}
</style>
