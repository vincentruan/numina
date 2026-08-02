<template>
  <div class="dashboard-skeleton">
    <!-- Hero section: OverviewStatCard (net worth + 2×2 sub-stats) -->
    <div class="hero-section">
      <div class="skeleton-overview">
        <!-- Main area: label + large amount + sub-row -->
        <div class="skeleton-main">
          <van-skeleton :row="1" row-width="28%" title-width="0" animate />
          <div class="skeleton-amount">
            <van-skeleton :row="1" row-width="55%" animate />
            <div class="skeleton-trend-btn">
              <van-skeleton :row="1" row-width="48px" animate />
            </div>
          </div>
          <van-skeleton :row="1" row-width="65%" animate />
        </div>
        <!-- 2×2 sub-stat grid -->
        <div class="skeleton-detail">
          <div v-for="i in 4" :key="i" class="skeleton-detail-cell">
            <van-skeleton :row="1" row-width="60%" animate />
            <van-skeleton :row="1" row-width="45%" animate />
          </div>
        </div>
      </div>
    </div>

    <!-- Finance Coach Card (collapsed header) -->
    <div class="skeleton-card">
      <div class="skeleton-card-header">
        <div class="skeleton-icon-circle">
          <van-skeleton :row="1" row-width="18px" animate />
        </div>
        <van-skeleton :row="1" row-width="80px" animate />
        <div class="skeleton-card-header-spacer" />
        <van-skeleton :row="1" row-width="50px" animate />
      </div>
    </div>

    <!-- Literacy Status Card (header + child rows) -->
    <div class="skeleton-card skeleton-literacy">
      <div class="skeleton-literacy-header">
        <van-skeleton :row="1" row-width="72px" animate />
        <van-skeleton :row="1" row-width="48px" animate />
      </div>
      <div class="skeleton-literacy-list">
        <div v-for="i in 2" :key="i" class="skeleton-literacy-row">
          <van-skeleton-avatar avatar-size="28px" avatar-shape="round" animate />
          <van-skeleton :row="1" row-width="48px" animate />
          <div class="skeleton-literacy-badge">
            <van-skeleton :row="1" row-width="32px" animate />
          </div>
        </div>
      </div>
    </div>

    <!-- Smart Reminders Card (collapsed header) -->
    <div class="skeleton-card">
      <div class="skeleton-card-header">
        <div class="skeleton-icon-circle">
          <van-skeleton :row="1" row-width="18px" animate />
        </div>
        <van-skeleton :row="1" row-width="64px" animate />
        <div class="skeleton-card-header-spacer" />
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

    <!-- Family Manifesto Card (collapsed header) -->
    <div class="skeleton-card">
      <div class="skeleton-card-header">
        <div class="skeleton-icon-circle">
          <van-skeleton :row="1" row-width="18px" animate />
        </div>
        <van-skeleton :row="1" row-width="56px" animate />
        <div class="skeleton-card-header-spacer" />
        <van-skeleton :row="1" row-width="40px" animate />
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

/* ── Hero / Overview (mirrors OverviewStatCard layout) ── */
.hero-section {
  background: var(--card-bg);
}
.skeleton-overview {
  background: var(--card-bg);
  padding: 20px 16px 16px;
}
.skeleton-overview :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-overview :deep(.van-skeleton__row),
.skeleton-overview :deep(.van-skeleton__title) {
  background: rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-overview :deep(.van-skeleton__row),
[data-theme='dark'] .skeleton-overview :deep(.van-skeleton__title) {
  background: rgba(255, 255, 255, 0.1);
}
.skeleton-main {
  display: flex;
  flex-direction: column;
}
.skeleton-main :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-main :deep(.van-skeleton__row) {
  height: 12px;
  margin-top: 8px;
  border-radius: 4px;
}
.skeleton-main :deep(.van-skeleton__row:first-child) {
  margin-top: 0;
}
.skeleton-amount {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 6px 0 8px;
}
.skeleton-amount :deep(.van-skeleton__row) {
  height: 32px !important;
  border-radius: 6px;
}
.skeleton-trend-btn {
  flex-shrink: 0;
}
.skeleton-trend-btn :deep(.van-skeleton__row) {
  height: 26px !important;
  border-radius: 4px;
}

/* 2×2 sub-stat grid (mirrors .osc-detail) */
.skeleton-detail {
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  border-radius: 8px;
  margin-top: 12px;
  overflow: hidden;
}
.skeleton-detail-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px 8px;
  min-height: 64px;
  /* Hairline separators between cells */
  position: relative;
}
.skeleton-detail-cell:nth-child(odd) {
  border-right: 1px solid var(--separator);
}
.skeleton-detail-cell:nth-child(-n + 2) {
  border-bottom: 1px solid var(--separator);
}
.skeleton-detail-cell :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-detail-cell :deep(.van-skeleton__row) {
  height: 12px;
  margin-top: 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
}
[data-theme='dark'] .skeleton-detail-cell :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.1);
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

/* ── Collapsed card header (icon + title + spacer + summary) ── */
.skeleton-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.skeleton-card-header-spacer {
  flex: 1;
}
.skeleton-icon-circle {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.skeleton-icon-circle :deep(.van-skeleton__row) {
  height: 18px !important;
  width: 18px !important;
  border-radius: 50%;
}

/* ── Literacy Status Card ── */
.skeleton-literacy {
  padding: 12px 16px;
}
.skeleton-literacy-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.skeleton-literacy-header :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.skeleton-literacy-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.skeleton-literacy-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.skeleton-literacy-row :deep(.van-skeleton) {
  padding: 0;
}
.skeleton-literacy-row :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
}
.skeleton-literacy-badge {
  margin-left: auto;
}
.skeleton-literacy-badge :deep(.van-skeleton__row) {
  height: 20px !important;
  border-radius: 10px;
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
