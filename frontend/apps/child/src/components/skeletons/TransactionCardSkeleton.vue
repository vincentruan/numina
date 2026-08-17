<template>
  <div class="tx-card-skeleton">
    <van-skeleton-avatar avatar-size="24px" avatar-shape="round" animate />
    <div class="tx-info-skeleton">
      <van-skeleton :row="2" row-width="50% 30%" animate />
    </div>
    <van-skeleton :row="1" row-width="15%" animate class="amount-skeleton" />
  </div>
</template>

<script setup lang="ts">
// Skeleton for transaction cards used in Ledger page
</script>

<style scoped>
.tx-card-skeleton {
  display: flex;
  align-items: center;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  gap: 12px;
  border: 1px solid var(--color-hairline);
  min-height: 56px;
}

.tx-card-skeleton :deep(.van-skeleton-avatar) {
  background: var(--skeleton-bg);
}

.tx-info-skeleton {
  flex: 1;
}

.tx-info-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.tx-info-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}

.tx-info-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

.amount-skeleton :deep(.van-skeleton__row) {
  height: 18px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}
</style>