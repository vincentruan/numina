<template>
  <div class="overview-card">
    <div class="ov-main">
      <!-- Faded upward-growth arrow watermark on the right — visual beacon for the trend entry -->
      <svg class="trend-watermark" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path d="M3 17L9 11L13 15L21 7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M15 7H21V13" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <div class="ov-label">{{ t('dashboard.totalAssets') }}</div>
      <div class="ov-amount">
        <MoneyDisplay :amount="totalAssets" size="large" />
        <router-link to="/dashboard/analytics" class="trend-entry" :aria-label="t('analyticsPage.trendEntry')">
          <svg class="trend-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M2 12L5.5 8.5L8 11L14 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M10 4H14V8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="trend-text">{{ t('analyticsPage.trendEntry') }}</span>
        </router-link>
      </div>
      <div class="ov-sub-row">
        <span v-if="totalDailyCost > 0" class="ov-daily">{{ t('dashboard.dailyCost') }} {{ currency.format(totalDailyCost) }}</span>
        <span class="ov-count">{{ t('dashboard.assetCount', { count: assetCount }) }}</span>
        <span v-if="monthOverMonthChange != null" class="ov-change" :class="changeClass">
          {{ changeText }} {{ t('dashboard.monthChange') }}
        </span>
      </div>
    </div>
    <div class="ov-detail">
      <div class="ov-detail-item">
        <div class="ov-detail-label">{{ t('dashboard.netWorth') }}</div>
        <div class="ov-detail-value">
          <MoneyDisplay :amount="netWorth" />
        </div>
      </div>
      <div class="ov-detail-divider" />
      <div class="ov-detail-item">
        <div class="ov-detail-label">{{ t('dashboard.totalLiabilities') }}</div>
        <div class="ov-detail-value">
          <MoneyDisplay :amount="totalLiabilities" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MoneyDisplay from '@/components/common/MoneyDisplay.vue'
import { useCurrency } from '@/composables/useCurrency'

const { t } = useI18n()

const props = defineProps<{
  netWorth: number
  totalAssets: number
  totalLiabilities: number
  totalDailyCost: number
  assetCount: number
  monthOverMonthChange?: number | null
}>()

const currency = useCurrency()

const changeClass = computed(() => {
  const pct = props.monthOverMonthChange || 0
  return pct >= 0 ? 'positive' : 'negative'
})

const changeText = computed(() => {
  const pct = props.monthOverMonthChange || 0
  const arrow = pct >= 0 ? '↑' : '↓'
  return `${arrow} ${Math.abs(pct).toFixed(1)}%`
})
</script>

<style scoped>
/* Light mode: Pastel Cloud Gradient (pink → lavender → soft blue) over white canvas */
.overview-card {
  background:
    linear-gradient(135deg,
      rgba(239, 44, 193, 0.10) 0%,
      rgba(189, 187, 255, 0.18) 45%,
      rgba(160, 195, 255, 0.14) 100%),
    #ffffff;
  padding: 20px 16px 16px;
  color: #000000;
  position: relative;
  overflow: hidden;
}

/* Decorative soft blob — painterly cloud effect */
.overview-card::before {
  content: '';
  position: absolute;
  top: -40px;
  right: -30px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(189, 187, 255, 0.22) 0%, transparent 70%);
  pointer-events: none;
}

/* Dark mode: midnight blue surface with subtle lavender gradient overlay */
[data-theme='dark'] .overview-card {
  background:
    linear-gradient(135deg,
      rgba(189, 187, 255, 0.08) 0%,
      rgba(189, 187, 255, 0.04) 50%,
      transparent 100%),
    #010120;
  color: var(--text-primary);
}
[data-theme='dark'] .overview-card::before {
  background: radial-gradient(circle, rgba(189, 187, 255, 0.10) 0%, transparent 70%);
}

.ov-main {
  display: flex;
  flex-direction: column;
  position: relative;
}

/* Keep label/amount/sub-row above the faded watermark (z-index 0) */
.ov-main > .ov-label,
.ov-main > .ov-amount,
.ov-main > .ov-sub-row {
  position: relative;
  z-index: 1;
}

/* Faded upward-growth arrow on the right — beckons the eye toward the trend entry */
.trend-watermark {
  position: absolute;
  top: -16px;
  right: -8px;
  width: 108px;
  height: 108px;
  color: var(--color-primary);
  opacity: 0.07;
  z-index: 0;
  pointer-events: none;
}
[data-theme='dark'] .trend-watermark {
  color: var(--color-lavender);
  opacity: 0.12;
}

/* Mono label — PP Neue Montreal Mono style: uppercase, tight tracking */
.ov-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  font-family: 'Georgia', monospace;
}
[data-theme='dark'] .ov-label {
  color: var(--text-tertiary);
}

.ov-amount {
  margin: 6px 0 8px;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

/* Display number: large, tight negative tracking per design system */
.ov-amount :deep(.money-display) {
  color: #000000;
  font-size: clamp(28px, 8vw, 36px);
  font-weight: 500;
  letter-spacing: -0.03em;
  line-height: 1.05;
}
[data-theme='dark'] .ov-amount :deep(.money-display) {
  color: var(--text-primary);
}

/* Trend entry: icon + text, flex item aligned right */
.trend-entry {
  display: flex;
  align-items: center;
  gap: 4px;
  text-decoration: none;
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.08);
  transition: background 0.15s ease;
  position: relative;
  overflow: hidden;
}
[data-theme='dark'] .trend-entry {
  background: rgba(255, 255, 255, 0.10);
  border-color: rgba(255, 255, 255, 0.12);
}
.trend-entry:active {
  transform: scale(0.95);
}

/* Icon + text sit above the sweeping highlight */
.trend-entry > * {
  position: relative;
  z-index: 1;
}

/* 扫光效果 — a soft highlight band sweeps across the button left→right, looping */
.trend-entry::after {
  content: '';
  position: absolute;
  top: 0;
  left: -120%;
  width: 60%;
  height: 100%;
  background: linear-gradient(
    100deg,
    transparent 0%,
    rgba(255, 255, 255, 0.55) 50%,
    transparent 100%
  );
  transform: skewX(-18deg);
  animation: trend-entry-sweep 3.2s ease-in-out infinite;
  pointer-events: none;
  z-index: 0;
}
[data-theme='dark'] .trend-entry::after {
  background: linear-gradient(
    100deg,
    transparent 0%,
    rgba(255, 255, 255, 0.35) 50%,
    transparent 100%
  );
}

@keyframes trend-entry-sweep {
  0% {
    left: -120%;
  }
  55% {
    left: 160%;
  }
  100% {
    left: 160%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .trend-entry::after {
    animation: none;
  }
}

.trend-icon {
  width: 16px;
  height: 16px;
  color: rgba(0, 0, 0, 0.55);
}
[data-theme='dark'] .trend-icon {
  color: rgba(255, 255, 255, 0.60);
}

.trend-text {
  font-size: 12px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.65);
}
[data-theme='dark'] .trend-text {
  color: rgba(255, 255, 255, 0.70);
}

/* Responsive fallback: stack on narrow screens */
@media (max-width: 320px) {
  .ov-amount {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .trend-entry {
    align-self: flex-end;
  }
}

.ov-sub-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

/* Badge style: sharp 4px radius, glass-dark on light / glass-light on dark */
.ov-daily {
  background: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(0, 0, 0, 0.08);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}
[data-theme='dark'] .ov-daily {
  background: rgba(255, 255, 255, 0.10);
  color: rgba(255, 255, 255, 0.70);
  border-color: rgba(255, 255, 255, 0.12);
}

.ov-count {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.50);
}
[data-theme='dark'] .ov-count {
  color: var(--text-tertiary);
}

.ov-change.positive {
  color: #059669;
  font-weight: 500;
}
[data-theme='dark'] .ov-change.positive {
  color: var(--color-trend-down);
}
.ov-change.negative {
  color: #dc2626;
  font-weight: 500;
}
[data-theme='dark'] .ov-change.negative {
  color: var(--color-trend-up);
}

/* Stats row: glass container, sharp 8px radius, dark-blue-tinted shadow */
.ov-detail {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 12px 16px;
  margin-top: 12px;
  box-shadow: rgba(1, 1, 32, 0.08) 0px 2px 8px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
[data-theme='dark'] .ov-detail {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: rgba(1, 1, 32, 0.4) 0px 2px 8px;
}

.ov-detail-item {
  flex: 1;
  text-align: center;
}

.ov-detail-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.40);
  font-family: 'Georgia', monospace;
}
[data-theme='dark'] .ov-detail-label {
  color: var(--text-tertiary);
}

.ov-detail-value {
  margin-top: 4px;
}
.ov-detail-value :deep(.money-display) {
  color: #000000;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
}
[data-theme='dark'] .ov-detail-value :deep(.money-display) {
  color: var(--text-primary);
}

.ov-detail-divider {
  width: 1px;
  height: 28px;
  background: rgba(0, 0, 0, 0.10);
}
[data-theme='dark'] .ov-detail-divider {
  background: rgba(255, 255, 255, 0.12);
}
</style>
