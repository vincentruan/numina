<template>
  <div class="baby-page-skeleton">
    <!-- Page header skeleton -->
    <div class="skeleton-header">
      <van-skeleton :row="1" row-width="80px" animate />
    </div>

    <!-- Child tabs skeleton -->
    <div class="skeleton-child-tabs">
      <div class="tab-item-skeleton">
        <van-skeleton :row="1" row-width="40px" animate />
      </div>
      <div class="tab-item-skeleton tab-avatar-skeleton">
        <van-skeleton-avatar avatar-size="22px" avatar-shape="round" animate />
        <van-skeleton :row="1" row-width="36px" animate />
      </div>
      <div class="tab-item-skeleton tab-avatar-skeleton">
        <van-skeleton-avatar avatar-size="22px" avatar-shape="round" animate />
        <van-skeleton :row="1" row-width="36px" animate />
      </div>
    </div>

    <!-- Pending Approvals skeleton (owner-visible section) -->
    <div class="skeleton-pending-approvals">
      <van-skeleton :row="1" row-width="100px" animate />
      <div class="approval-items-skeleton">
        <div v-for="i in 2" :key="i" class="approval-item-skeleton">
          <van-skeleton-avatar avatar-size="32px" avatar-shape="round" animate />
          <van-skeleton :row="2" row-width="60% 40%" animate />
        </div>
      </div>
    </div>

    <!-- Summary card skeleton -->
    <div class="skeleton-summary-card">
      <div class="summary-row-skeleton">
        <van-skeleton :row="1" row-width="60px" animate />
        <div class="summary-value-skeleton">
          <van-skeleton :row="1" row-width="80px" animate />
          <van-skeleton :row="1" row-width="50px" animate />
        </div>
      </div>
      <div class="summary-row-skeleton">
        <van-skeleton :row="1" row-width="80px" animate />
        <van-skeleton :row="1" row-width="40px" animate />
      </div>
      <div class="summary-row-skeleton">
        <van-skeleton :row="1" row-width="70px" animate />
        <van-skeleton :row="1" row-width="30px" animate />
      </div>
      <div class="summary-row-skeleton">
        <van-skeleton :row="1" row-width="80px" animate />
      </div>
      <div class="summary-row-skeleton">
        <van-skeleton :row="1" row-width="80px" animate />
      </div>
      <div class="summary-row-skeleton">
        <van-skeleton :row="1" row-width="80px" animate />
      </div>
    </div>

    <!-- Content tabs skeleton -->
    <div class="skeleton-content-tabs">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>

    <!-- Content area skeleton (representing all 3 tabs: Diary/Wishes/Chores) -->
    <div class="skeleton-content-area">
      <!-- Tab header skeleton -->
      <div class="content-tab-header-skeleton">
        <van-skeleton :row="1" row-width="120px" animate />
      </div>

      <!-- Calendar grid skeleton (Diary tab representative) -->
      <div class="calendar-header-skeleton">
        <van-skeleton :row="1" row-width="120px" animate />
      </div>
      <div class="calendar-grid-skeleton">
        <div v-for="i in 7" :key="'week-' + i" class="calendar-day-skeleton">
          <van-skeleton :row="1" row-width="20px" animate />
        </div>
        <div v-for="i in 14" :key="'day-' + i" class="calendar-cell-skeleton">
          <van-skeleton-avatar avatar-size="28px" avatar-shape="round" animate />
        </div>
      </div>

      <!-- List items skeleton (Wishes/Chores tabs representative) -->
      <div class="list-items-skeleton">
        <div v-for="i in 2" :key="'item-' + i" class="list-item-skeleton">
          <van-skeleton-avatar avatar-size="20px" avatar-shape="round" animate />
          <div class="item-body-skeleton">
            <van-skeleton :row="2" row-width="70% 50%" animate />
          </div>
        </div>
      </div>
    </div>

    <!-- FAB skeleton -->
    <div class="fab-skeleton">
      <van-skeleton-avatar avatar-size="52px" avatar-shape="round" animate />
    </div>
  </div>
</template>

<script setup lang="ts">
// Skeleton component for BabyPage loading state
</script>

<style scoped>
.baby-page-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 80px;
}

/* Header skeleton */
.skeleton-header {
  background: var(--bg-primary);
  padding: 14px 16px;
  display: flex;
  align-items: center;
}
.skeleton-header :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-header :deep(.van-skeleton__row) {
  height: 18px;
  border-radius: 4px;
}

/* Child tabs skeleton */
.skeleton-child-tabs {
  background: var(--card-bg);
  padding: 8px 16px;
  display: flex;
  gap: 12px;
  overflow-x: auto;
}
.tab-item-skeleton {
  flex-shrink: 0;
  min-height: 32px;
  display: flex;
  align-items: center;
}
.tab-item-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.tab-item-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
}
.tab-avatar-skeleton {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 2px 2px;
}
.tab-avatar-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .tab-avatar-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}

/* Pending Approvals skeleton */
.skeleton-pending-approvals {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-pending-approvals {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.skeleton-pending-approvals :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-pending-approvals :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.approval-items-skeleton {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.approval-item-skeleton {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}
.approval-item-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .approval-item-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}
.approval-item-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.approval-item-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  margin-top: 4px;
  border-radius: 4px;
}
.approval-item-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

/* Summary card skeleton */
.skeleton-summary-card {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 12px 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-summary-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.summary-row-skeleton {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
}
.summary-row-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.summary-row-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.summary-value-skeleton {
  display: flex;
  align-items: center;
  gap: 8px;
}
.summary-value-skeleton :deep(.van-skeleton__row) {
  height: 14px;
}

/* Content tabs skeleton */
.skeleton-content-tabs {
  margin-top: 12px;
  background: var(--card-bg);
  padding: 12px 16px;
}
.skeleton-content-tabs :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-content-tabs :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}

/* Content area skeleton */
.skeleton-content-area {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
}
.content-tab-header-skeleton {
  margin-bottom: 12px;
}
.content-tab-header-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.content-tab-header-skeleton :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}
.calendar-header-skeleton {
  margin-bottom: 12px;
}
.calendar-header-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.calendar-header-skeleton :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}
.calendar-grid-skeleton {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  margin-bottom: 16px;
}
.calendar-day-skeleton {
  text-align: center;
  padding: 4px;
}
.calendar-day-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.calendar-day-skeleton :deep(.van-skeleton__row) {
  height: 12px;
  border-radius: 2px;
}
.calendar-cell-skeleton {
  display: flex;
  justify-content: center;
  padding: 4px;
}
.calendar-cell-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .calendar-cell-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.08);
}

/* List items skeleton (Wishes/Chores) */
.list-items-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.list-item-skeleton {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
}
.list-item-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .list-item-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}
.item-body-skeleton {
  flex: 1;
}
.item-body-skeleton :deep(.van-skeleton) {
  padding: 0;
}
.item-body-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  margin-top: 4px;
  border-radius: 4px;
}
.item-body-skeleton :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}

/* FAB skeleton */
.fab-skeleton {
  position: fixed;
  right: 16px;
  bottom: 72px;
  width: 52px;
  height: 52px;
}
.fab-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(0, 0, 0, 0.08);
  width: 52px;
  height: 52px;
}
[data-theme='dark'] .fab-skeleton :deep(.van-skeleton-avatar) {
  background: rgba(255, 255, 255, 0.1);
}
</style>