<template>
  <div class="header-skeleton">
    <van-skeleton-avatar class="back-icon-skeleton" size="40" />
    <van-skeleton class="title-skeleton" :row="1" row-width="120px" />
  </div>
</template>

<script setup lang="ts">
// Reusable PageHeader skeleton for detail pages
</script>

<style scoped>
.header-skeleton {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  margin-bottom: var(--space-md);
}

.back-icon-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}

.title-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.title-skeleton :deep(.van-skeleton__row) {
  background: var(--skeleton-bg);
}
</style>