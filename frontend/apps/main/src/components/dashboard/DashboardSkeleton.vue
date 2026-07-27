<template>
  <div class="dashboard-skeleton">
    <!-- Hero section: OverviewStatCard (net worth + sub-stats) -->
    <div class="hero-section">
      <div class="skeleton-overview">
        <van-skeleton :row="2" row-width="50% 80%" title-width="30%" animate />
        <div class="skeleton-detail">
          <van-skeleton :row="1" row-width="100%" animate />
          <van-skeleton :row="1" row-width="100%" animate />
        </div>
      </div>
    </div>

    <!-- Finance Coach Card (collapsed header) -->
    <div class="skeleton-card">
      <div class="skeleton-card-header">
        <van-skeleton-avatar avatar-size="18px" avatar-shape="square" animate />
        <van-skeleton :row="1" row-width="80px" animate />
        <van-skeleton :row="1" row-width="50px" animate />
      </div>
    </div>

    <!-- Smart Reminders Card (collapsed header) -->
    <div class="skeleton-card">
      <div class="skeleton-card-header">
        <van-skeleton-avatar avatar-size="18px" avatar-shape="square" animate />
        <van-skeleton :row="1" row-width="80px" animate />
        <van-skeleton :row="1" row-width="100px" animate />
      </div>
    </div>

    <!-- Pending Approvals Section (owner-only; skeleton always shown since role is
         not known during initial load; self-gates via v-if on auth store) -->
    <div v-if="authStore.user?.role === 'owner'" class="skeleton-card skeleton-approvals">
      <div class="skeleton-approvals-header">
        <van-skeleton :row="1" row-width="64px" animate />
        <div class="skeleton-badge">
          <van-skeleton :row="1" row-width="16px" animate />
        </div>
      </div>
    </div>

    <!-- Focus Top-3 Card: tab bar + 3 item rows + footer link -->
    <div class="skeleton-card skeleton-top3">
      <div class="skeleton-top3-tabs">
        <van-skeleton :row="1" row-width="32px" animate />
        <van-skeleton :row="1" row-width="32px" animate />
        <van-skeleton :row="1" row-width="32px" animate />
      </div>
      <div class="skeleton-top3-list">
        <div v-for="i in 3" :key="i" class="skeleton-top3-item">
          <van-skeleton :row="2" row-width="60% 40%" title-width="45%" animate />
          <div class="skeleton-top3-progress">
            <van-skeleton :row="1" row-width="100%" animate />
          </div>
        </div>
      </div>
      <div class="skeleton-top3-footer">
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
</script>

<style scoped>
.dashboard-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
}

/* ── Hero / Overview ── */
.hero-section {
  background: var(--bg-secondary);
}
.skeleton-overview {
  background: var(--color-primary);
  padding: 24px 20px 16px;
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
  background: rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 12px 16px;
}
.skeleton-detail :deep(.van-skeleton) {
  flex: 1;
}

/* ── Shared card skeleton ── */
.skeleton-card {
  background: var(--card-bg);
  border-radius: 12px;
  margin: 12px;
  padding: 12px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.skeleton-card :deep(.van-skeleton) {
  padding: 0;
}

/* ── Coach & Reminders collapsed header ── */
.skeleton-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Pending Approvals ── */
.skeleton-approvals {
  padding: 12px 16px;
}
.skeleton-approvals-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.skeleton-badge {
  background: var(--color-danger, #ee0a24);
  border-radius: 10px;
  padding: 2px 8px;
  opacity: 0.6;
}
.skeleton-badge :deep(.van-skeleton__row) {
  height: 12px !important;
  background: rgba(255, 255, 255, 0.5) !important;
}

/* ── Focus Top-3 Card ── */
.skeleton-top3 {
  padding: 0;
  overflow: hidden;
}
.skeleton-top3-tabs {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
}
.skeleton-top3-tabs :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
}
.skeleton-top3-list {
  padding: 4px 12px;
}
.skeleton-top3-item {
  padding: 10px 4px;
  border-bottom: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
}
.skeleton-top3-item:last-child {
  border-bottom: none;
}
.skeleton-top3-item :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.skeleton-top3-item :deep(.van-skeleton__title) {
  height: 14px;
  margin-bottom: 6px;
}
.skeleton-top3-progress {
  margin-top: 6px;
}
.skeleton-top3-progress :deep(.van-skeleton__row) {
  height: 4px !important;
  border-radius: 2px;
}
.skeleton-top3-footer {
  padding: 10px 0;
  text-align: center;
}
.skeleton-top3-footer :deep(.van-skeleton__row) {
  height: 14px;
  margin: 0 auto;
}
</style>
