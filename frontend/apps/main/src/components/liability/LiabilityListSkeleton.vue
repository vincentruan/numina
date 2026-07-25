<template>
  <div class="liability-list-skeleton">
    <!-- Tabs: 进行中 / 已结清 -->
    <div class="skeleton-tabs">
      <div class="tab-item">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
      <div class="tab-item">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
    </div>

    <!-- EducationRewardCard (conditional, show placeholder) -->
    <div class="skeleton-education-card">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- Filter bar: chips + sort button -->
    <div class="skeleton-filter-bar">
      <div class="filter-chips">
        <div class="chip">
          <van-skeleton :row="1" row-width="40px" animate />
        </div>
        <div class="chip">
          <van-skeleton :row="1" row-width="52px" animate />
        </div>
        <div class="chip">
          <van-skeleton :row="1" row-width="48px" animate />
        </div>
        <div class="chip">
          <van-skeleton :row="1" row-width="56px" animate />
        </div>
      </div>
      <div class="sort-btn">
        <van-skeleton :row="1" row-width="52px" animate />
      </div>
    </div>

    <!-- LiabilityStrategyCard (conditional, show placeholder) -->
    <div class="skeleton-strategy-card">
      <van-skeleton :row="2" row-width="60% 80%" title-width="40%" animate />
    </div>

    <!-- Summary Banner (red gradient) -->
    <div class="summary-banner">
      <div class="summary-top">
        <div class="summary-main">
          <van-skeleton :row="2" row-width="80px 120px" animate />
        </div>
        <div class="summary-count">
          <van-skeleton :row="1" row-width="60px" animate />
        </div>
      </div>
      <div class="progress-bar">
        <van-skeleton :row="1" row-width="100%" animate />
      </div>
      <div class="progress-text">
        <van-skeleton :row="1" row-width="80px" animate />
      </div>
    </div>

    <!-- Monthly payment banner -->
    <div class="skeleton-monthly-banner">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- Liability cards: 3 cards -->
    <div class="skeleton-list">
      <div v-for="i in 3" :key="i" class="liability-card">
        <van-skeleton :row="2" row-width="100% 60%" animate />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton for LiabilityListPanel loading state
</script>

<style scoped>
.liability-list-skeleton {
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

/* ── EducationRewardCard (conditional) ── */
.skeleton-education-card {
  margin: 8px 12px;
  padding: 12px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-education-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.skeleton-education-card :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-education-card :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}

/* ── Filter bar (mirrors actual filter-bar) ── */
.skeleton-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  overflow-x: auto;
}
[data-theme='dark'] .skeleton-filter-bar {
  border-bottom-color: rgba(255, 255, 255, 0.06);
}
.filter-chips {
  display: flex;
  gap: 6px;
  flex: 1;
}
.chip {
  flex-shrink: 0;
  padding: 4px 14px;
  border-radius: 30px;
  border: 1px solid rgba(0, 0, 0, 0.18);
  background: transparent;
  display: flex;
  align-items: center;
}
[data-theme='dark'] .chip {
  border-color: rgba(255, 255, 255, 0.2);
}
.chip :deep(.van-skeleton) {
  padding: 0;
}
.chip :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}
.sort-btn {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(0, 0, 0, 0.12);
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

/* ── LiabilityStrategyCard (conditional) ── */
.skeleton-strategy-card {
  margin: 8px 16px;
  padding: 12px;
  background: var(--card-bg);
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-strategy-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.skeleton-strategy-card :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-strategy-card :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
}
.skeleton-strategy-card :deep(.van-skeleton__title) {
  margin-bottom: 8px;
}

/* ── Summary Banner (mirrors actual gradient) ── */
.summary-banner {
  margin: 12px 12px 4px;
  background: linear-gradient(135deg, #991b1b 0%, #dc2626 60%, #ea580c 100%);
  border-radius: 16px;
  padding: 20px;
}
.summary-banner :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.2) !important;
}
.summary-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}
.summary-main {
  flex: 1;
}
.summary-main :deep(.van-skeleton) {
  padding: 0;
}
.summary-main :deep(.van-skeleton__row) {
  height: 13px;
  margin-top: 6px;
  border-radius: 4px;
}
.summary-main :deep(.van-skeleton__row:last-child) {
  height: 36px;
  margin-top: 6px;
}
.summary-count {
  padding-top: 4px;
}
.summary-count :deep(.van-skeleton) {
  padding: 0;
}
.summary-count :deep(.van-skeleton__row) {
  height: 28px;
  width: 60px !important;
  border-radius: 4px;
}
.progress-bar {
  height: 6px;
  margin-bottom: 8px;
}
.progress-bar :deep(.van-skeleton) {
  padding: 0;
}
.progress-bar :deep(.van-skeleton__row) {
  height: 6px;
  border-radius: 3px;
}
.progress-text {
  display: flex;
  justify-content: flex-end;
}
.progress-text :deep(.van-skeleton) {
  padding: 0;
}
.progress-text :deep(.van-skeleton__row) {
  height: 12px;
  width: 80px !important;
  border-radius: 4px;
}

/* ── Monthly payment banner ── */
.skeleton-monthly-banner {
  margin: 8px 12px 4px;
  padding: 12px 16px;
  background: var(--card-bg);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 12px;
}
[data-theme='dark'] .skeleton-monthly-banner {
  border-color: rgba(255, 255, 255, 0.12);
}
.skeleton-monthly-banner :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-monthly-banner :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}

/* ── Liability cards list ── */
.skeleton-list {
  padding: 8px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.liability-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .liability-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.liability-card :deep(.van-skeleton) {
  padding: 0;
}
.liability-card :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
}
.liability-card :deep(.van-skeleton__row:first-child) {
  height: 16px;
  margin-top: 0;
}
</style>
