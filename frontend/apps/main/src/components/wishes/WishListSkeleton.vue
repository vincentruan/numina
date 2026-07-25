<template>
  <div class="wish-list-skeleton">
    <!-- Tabs: 待实现 / 已实现 / 已取消 -->
    <div class="skeleton-tabs">
      <div class="tab-item">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
      <div class="tab-item">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
      <div class="tab-item">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
    </div>

    <!-- Sort bar: 优先级 / 价格 / 名称 -->
    <div class="skeleton-sort-bar">
      <div class="sort-btn">
        <van-skeleton :row="1" row-width="56px" animate />
      </div>
      <div class="sort-btn">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
      <div class="sort-btn">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
    </div>

    <!-- Debt warning bar (conditional) -->
    <div class="skeleton-debt-warning">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- WishAdviceCard (conditional) -->
    <div class="skeleton-advice-card">
      <van-skeleton :row="2" row-width="60% 80%" title-width="40%" animate />
    </div>

    <!-- Wish items: 3 items with priority stripe, icon, body -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="wish-item">
        <!-- Priority stripe -->
        <div class="priority-stripe" />
        <!-- Icon anchor -->
        <div class="wish-icon">
          <van-skeleton-avatar avatar-size="44px" avatar-shape="round" animate />
        </div>
        <!-- Body: name, price, priority badge, afford bar, progress -->
        <div class="wish-body">
          <van-skeleton :row="3" row-width="70% 50% 60%" animate />
          <!-- Afford bar -->
          <div class="afford-bar">
            <van-skeleton :row="1" row-width="100%" animate />
          </div>
          <!-- Progress bar -->
          <div class="progress-bar">
            <van-skeleton :row="1" row-width="100%" animate />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton for WishListPanel loading state
</script>

<style scoped>
.wish-list-skeleton {
  background: var(--bg-secondary);
}

/* ── Tabs (mirrors van-tabs) ── */
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

/* ── Sort bar (mirrors actual sort-bar) ── */
.skeleton-sort-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--separator);
}
.sort-btn {
  min-height: 32px;
  padding: 0 14px;
  border-radius: 30px;
  border: 1px solid rgba(0, 0, 0, 0.15);
  background: transparent;
  display: flex;
  align-items: center;
}
[data-theme='dark'] .sort-btn {
  border-color: rgba(255, 255, 255, 0.15);
}
.sort-btn :deep(.van-skeleton) {
  padding: 0;
}
.sort-btn :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}

/* ── Debt warning bar (conditional) ── */
.skeleton-debt-warning {
  margin: 8px 12px;
  padding: 8px 10px;
  background: rgba(255, 151, 106, 0.12);
  border-radius: 8px;
}
.skeleton-debt-warning :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-debt-warning :deep(.van-skeleton__row) {
  height: 12px;
  border-radius: 4px;
}

/* ── WishAdviceCard (conditional) ── */
.skeleton-advice-card {
  margin: 8px 12px;
  padding: 12px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-advice-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.skeleton-advice-card :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-advice-card :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
}
.skeleton-advice-card :deep(.van-skeleton__title) {
  margin-bottom: 8px;
}

/* ── List ── */
.skeleton-list {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── Wish item (mirrors actual wish-item structure) ── */
.wish-item {
  display: flex;
  align-items: stretch;
  background: var(--card-bg);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  min-height: 72px;
}
[data-theme='dark'] .wish-item {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

/* Priority stripe (4px left border) */
.priority-stripe {
  width: 4px;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.12);
}
[data-theme='dark'] .priority-stripe {
  background: rgba(255, 255, 255, 0.12);
}

/* Icon anchor */
.wish-icon {
  width: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 2px;
}
.wish-icon :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .wish-icon :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}

/* Body */
.wish-body {
  flex: 1;
  min-width: 0;
  padding: 12px 12px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.wish-body :deep(.van-skeleton) {
  padding: 0;
}
.wish-body :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 6px;
  border-radius: 4px;
}
.wish-body :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

/* Afford bar */
.afford-bar {
  margin-top: 4px;
}
.afford-bar :deep(.van-skeleton) {
  padding: 0;
}
.afford-bar :deep(.van-skeleton__row) {
  height: 12px;
  border-radius: 4px;
}

/* Progress bar */
.progress-bar {
  margin-top: 4px;
}
.progress-bar :deep(.van-skeleton) {
  padding: 0;
}
.progress-bar :deep(.van-skeleton__row) {
  height: 3px;
  border-radius: 2px;
}
</style>
