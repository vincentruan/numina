<template>
  <div class="ledger-skeleton">
    <!-- Balance hero skeleton — teal feature card -->
    <div class="balance-card-skeleton">
      <van-skeleton :row="2" row-width="30% 60%" animate class="balance-rows" />
      <van-skeleton :row="1" row-width="30%" animate class="btn-skeleton" />
    </div>

    <!-- Transaction list skeleton -->
    <TransactionCardSkeleton v-for="i in 5" :key="i" />
  </div>
</template>

<script setup lang="ts">
import TransactionCardSkeleton from './TransactionCardSkeleton.vue'
// Skeleton for ChildLedgerPage
</script>

<style scoped>
.ledger-skeleton {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Balance card — teal feature card */
.balance-card-skeleton {
  background: var(--color-brand-teal);
  border-radius: var(--radius-xl);
  padding: 32px 24px;
  text-align: center;
  margin-bottom: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

[data-theme="dark"] .balance-card-skeleton {
  background:
    linear-gradient(135deg, rgba(var(--color-brand-mint-rgb), 0.14), rgba(var(--color-brand-mint-rgb), 0.06)),
    var(--color-surface-card);
}

.balance-rows :deep(.van-skeleton) {
  padding: 0;
}

.balance-rows :deep(.van-skeleton__row) {
  height: 32px;
  margin-top: 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.1);
}

[data-theme="dark"] .balance-rows :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.08);
}

.balance-rows :deep(.van-skeleton__row:first-child) {
  height: 13px;
  margin-top: 0;
}

.btn-skeleton :deep(.van-skeleton__row) {
  height: 44px;
  border-radius: var(--radius-md);
  background: var(--color-canvas);
}

[data-theme="dark"] .btn-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.15);
}
</style>