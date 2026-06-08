<template>
  <div class="ai-hub-skeleton">
    <!-- Header skeleton -->
    <div class="hub-header-skeleton">
      <div class="hub-header-main-skeleton">
        <!-- Greeting skeleton -->
        <div class="hub-greeting-skeleton">
          <van-skeleton :row="1" row-width="60px" animate />
          <van-skeleton :row="1" row-width="140px" animate />
        </div>
        <!-- Score ring skeleton -->
        <div class="hub-score-ring-skeleton">
          <van-skeleton :row="1" row-width="64px" animate />
        </div>
      </div>
      <!-- Stats row skeleton -->
      <div class="hub-stats-skeleton">
        <div class="hub-stat-item-skeleton">
          <van-skeleton :row="1" row-width="30px" animate />
          <van-skeleton :row="1" row-width="50px" animate />
        </div>
        <div class="hub-stat-divider-skeleton" />
        <div class="hub-stat-item-skeleton">
          <van-skeleton :row="1" row-width="30px" animate />
          <van-skeleton :row="1" row-width="40px" animate />
        </div>
        <div class="hub-stat-divider-skeleton" />
        <div class="hub-stat-item-skeleton">
          <van-skeleton :row="1" row-width="30px" animate />
          <van-skeleton :row="1" row-width="60px" animate />
        </div>
        <div class="hub-stat-divider-skeleton" />
        <div class="hub-stat-meta-skeleton">
          <van-skeleton :row="1" row-width="80px" animate />
        </div>
      </div>
    </div>

    <!-- Report card skeleton -->
    <div class="report-card-skeleton">
      <div class="report-title-skeleton">
        <van-skeleton :row="1" row-width="100px" animate />
      </div>
      <div class="report-text-skeleton">
        <van-skeleton :row="2" row-width="100% 80%" animate />
      </div>
      <div class="report-cta-skeleton">
        <van-skeleton :row="1" row-width="80px" animate />
      </div>
    </div>

    <!-- Feature section skeleton -->
    <div class="feature-section-skeleton">
      <!-- Numina agent featured card skeleton -->
      <div class="numina-card-skeleton">
        <van-skeleton :row="3" row-width="60px 100% 70%" animate />
      </div>

      <!-- My agents section skeleton -->
      <div class="agent-section-skeleton">
        <div class="agent-section-header-skeleton">
          <van-skeleton :row="1" row-width="80px" animate />
          <van-skeleton :row="1" row-width="30px" animate />
        </div>
        <div class="agent-grid-skeleton">
          <div class="agent-card-skeleton">
            <van-skeleton :row="2" row-width="40px 100%" animate />
          </div>
          <div class="agent-card-skeleton">
            <van-skeleton :row="2" row-width="40px 100%" animate />
          </div>
        </div>
      </div>

      <!-- Analysis apps section skeleton -->
      <div class="agent-section-skeleton">
        <div class="agent-section-header-skeleton">
          <van-skeleton :row="1" row-width="80px" animate />
          <van-skeleton :row="1" row-width="30px" animate />
        </div>
        <div class="app-list-skeleton">
          <div class="app-item-skeleton">
            <van-skeleton :row="2" row-width="100% 60%" animate />
          </div>
        </div>
      </div>
    </div>

    <!-- Chat entry skeleton (fixed bottom) -->
    <div class="chat-entry-skeleton">
      <van-skeleton :row="1" row-width="100%" animate />
    </div>
  </div>
</template>

<style scoped>
.ai-hub-skeleton {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 140px;
}

/* Header skeleton */
.hub-header-skeleton {
  position: relative;
  padding: 20px 16px 16px;
  background:
    linear-gradient(135deg,
      rgba(239, 44, 193, 0.10) 0%,
      rgba(189, 187, 255, 0.18) 45%,
      rgba(160, 195, 255, 0.14) 100%),
    #ffffff;
  color: #000000;
  overflow: hidden;
}

[data-theme='dark'] .hub-header-skeleton {
  background:
    linear-gradient(135deg,
      rgba(189, 187, 255, 0.08) 0%,
      rgba(189, 187, 255, 0.04) 50%,
      transparent 100%),
    #010120;
}

.hub-header-main-skeleton {
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
}

.hub-greeting-skeleton {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.hub-greeting-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.hub-greeting-skeleton :deep(.van-skeleton__row) {
  height: 16px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .hub-greeting-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

.hub-greeting-skeleton :deep(.van-skeleton__row:last-child) {
  height: 24px;
}

.hub-score-ring-skeleton {
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .hub-score-ring-skeleton {
  background: rgba(255, 255, 255, 0.10);
}

.hub-score-ring-skeleton :deep(.van-skeleton) {
  padding: 0;
  height: 64px;
}

.hub-score-ring-skeleton :deep(.van-skeleton__row) {
  height: 64px;
  border-radius: 50%;
}

/* Stats row skeleton */
.hub-stats-skeleton {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 12px;
  box-shadow: rgba(1, 1, 32, 0.08) 0px 2px 8px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

[data-theme='dark'] .hub-stats-skeleton {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: rgba(1, 1, 32, 0.4) 0px 2px 8px;
}

.hub-stat-item-skeleton {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.hub-stat-item-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.hub-stat-item-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .hub-stat-item-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

.hub-stat-divider-skeleton {
  width: 1px;
  height: 28px;
  background: rgba(0, 0, 0, 0.10);
  flex-shrink: 0;
}

[data-theme='dark'] .hub-stat-divider-skeleton {
  background: rgba(255, 255, 255, 0.12);
}

.hub-stat-meta-skeleton {
  flex-shrink: 0;
  padding-left: 8px;
}

.hub-stat-meta-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.hub-stat-meta-skeleton :deep(.van-skeleton__row) {
  height: 11px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .hub-stat-meta-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

/* Report card skeleton */
.report-card-skeleton {
  margin: 12px 16px;
  background: var(--card-bg);
  border-radius: 8px;
  padding: 14px 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: rgba(1, 1, 32, 0.06) 0px 2px 8px;
}

[data-theme='dark'] .report-card-skeleton {
  border-color: rgba(255, 255, 255, 0.10);
  box-shadow: rgba(1, 1, 32, 0.3) 0px 2px 8px;
}

.report-title-skeleton {
  margin-bottom: 10px;
}

.report-title-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.report-title-skeleton :deep(.van-skeleton__row) {
  height: 11px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .report-title-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

.report-text-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.report-text-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  margin-top: 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .report-text-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

.report-cta-skeleton {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}

.report-cta-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.report-cta-skeleton :deep(.van-skeleton__row) {
  height: 12px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .report-cta-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

/* Feature section skeleton */
.feature-section-skeleton {
  padding: 0 16px;
  margin-top: 4px;
}

/* Numina featured card skeleton */
.numina-card-skeleton {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--van-border-color);
  margin-top: 12px;
}

.numina-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.numina-card-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .numina-card-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

.numina-card-skeleton :deep(.van-skeleton__row:first-child) {
  height: 32px;
  width: 40px !important;
  margin-top: 0;
  border-radius: 8px;
}

/* Agent section skeleton */
.agent-section-skeleton {
  margin-top: 12px;
}

.agent-section-header-skeleton {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--card-bg);
  border-radius: 8px;
  margin-bottom: 8px;
}

.agent-section-header-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.agent-section-header-skeleton :deep(.van-skeleton__row) {
  height: 13px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .agent-section-header-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

/* Agent grid skeleton */
.agent-grid-skeleton {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.agent-card-skeleton {
  background: var(--van-background-2);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid var(--van-border-color);
  min-height: 100px;
}

.agent-card-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.agent-card-skeleton :deep(.van-skeleton__row) {
  height: 14px;
  margin-top: 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .agent-card-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

.agent-card-skeleton :deep(.van-skeleton__row:first-child) {
  height: 24px;
  width: 40px !important;
  margin-top: 0;
}

/* App list skeleton */
.app-list-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.app-item-skeleton {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 14px 16px;
  border: 1px solid var(--van-border-color);
}

.app-item-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.app-item-skeleton :deep(.van-skeleton__row) {
  height: 15px;
  margin-top: 4px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .app-item-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}

.app-item-skeleton :deep(.van-skeleton__row:first-child) {
  height: 15px;
  margin-top: 0;
}

/* Chat entry skeleton (fixed bottom) */
.chat-entry-skeleton {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  z-index: 10;
  padding: 12px 16px;
  background: var(--bg-primary, #fff);
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .chat-entry-skeleton {
  border-top-color: rgba(255, 255, 255, 0.10);
}

.chat-entry-skeleton :deep(.van-skeleton) {
  padding: 0;
}

.chat-entry-skeleton :deep(.van-skeleton__row) {
  height: 36px;
  border-radius: 18px;
  background: rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .chat-entry-skeleton :deep(.van-skeleton__row) {
  background: rgba(255, 255, 255, 0.10);
}
</style>