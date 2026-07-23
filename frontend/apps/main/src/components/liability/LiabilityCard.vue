<template>
  <van-swipe-cell :disabled="selectMode" class="liability-swipe-cell">
    <div
      class="liability-card"
      :class="{ 'is-selected': selected, 'select-mode': selectMode }"
      role="button"
      tabindex="0"
      @click="handleClick"
      @keydown.enter="handleClick"
      @keydown.space.prevent="handleClick"
      @touchstart="onTouchStart"
      @touchend="onTouchEnd"
      @touchmove="onTouchMove"
    >
      <!-- Selection checkbox overlay -->
      <div v-if="selectMode" class="select-overlay">
        <van-checkbox :model-value="selected" @click.stop />
      </div>

      <div class="card-header">
        <div class="card-icon" :style="{ background: categoryColor }">
          <svg class="icon-svg" aria-hidden="true">
            <use :href="`#${categoryIcon}`" />
          </svg>
        </div>
        <div class="card-header-text">
          <div class="card-title">
            <span class="name">{{ liability.name }}</span>
            <van-tag :type="liability.is_active ? 'danger' : 'success'" class="status-tag">
              {{ liability.is_active ? t('liabilityCard.active') : t('liabilityCard.inactive') }}
            </van-tag>
          </div>
          <div class="card-meta">
            <span class="meta-item">{{ categoryText }}</span>
            <span v-if="liability.institution" class="meta-item meta-divider">{{ liability.institution }}</span>
          </div>
        </div>
      </div>

      <div class="card-body">
        <div class="amount-section">
          <div class="amount-label">{{ t('liabilityCard.remainingPrincipal') }}</div>
          <div class="amount-value">{{ formatAmountDisplay(liability.remaining_amount) }}</div>
        </div>
        <div class="details-grid">
          <div class="detail-item">
            <span class="detail-label">{{ t('liabilityCard.monthlyPayment') }}</span>
            <span class="detail-value">{{ liability.monthly_payment ? formatAmountDisplay(liability.monthly_payment) : '—' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t('liabilityCard.annualRate') }}</span>
            <span class="detail-value">{{ liability.interest_rate }}%</span>
          </div>
        </div>
      </div>

      <div v-if="liability.is_active" class="card-footer">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: repaidPercent + '%' }" />
        </div>
        <div class="progress-text">
          <span class="progress-label">{{ t('liabilityCard.repaidPercent', { pct: repaidPercent }) }}</span>
          <span class="progress-remaining">{{ t('liabilityCard.remaining', { amount: formatAmountDisplay(liability.remaining_amount) }) }}</span>
        </div>
      </div>
    </div>

    <!-- Swipe right slot: actions -->
    <template #right>
      <div class="swipe-actions">
        <button v-if="liability.is_active" class="swipe-btn swipe-btn--pay" @click.stop="$emit('pay', liability)">
          <van-icon name="gold-coin-o" size="20" />
          <span>{{ t('liabilityCard.pay') }}</span>
        </button>
        <button class="swipe-btn swipe-btn--edit" @click.stop="$emit('edit', liability)">
          <van-icon name="edit" size="20" />
          <span>{{ t('liabilityCard.edit') }}</span>
        </button>
        <button class="swipe-btn swipe-btn--delete" @click.stop="$emit('delete', liability)">
          <van-icon name="delete-o" size="20" />
          <span>{{ t('liabilityCard.delete') }}</span>
        </button>
      </div>
    </template>
  </van-swipe-cell>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Liability } from '@/types'

const props = defineProps<{
  liability: Liability
  selectMode?: boolean
  selected?: boolean
}>()

const emit = defineEmits<{
  click: []
  pay: [liability: Liability]
  edit: [liability: Liability]
  delete: [liability: Liability]
  longpress: [liability: Liability]
}>()

const { t } = useI18n()

const categoryMap = computed<Record<string, { text: string; icon: string; color: string }>>(() => ({
  mortgage: { text: t('liability.mortgage'), icon: 'icon-mortgage', color: '#d97706' },
  car_loan: { text: t('liability.carLoan'), icon: 'icon-car-loan', color: '#0891b2' },
  credit_card: { text: t('liability.creditCard'), icon: 'icon-credit-card', color: '#dc2626' },
  consumer_loan: { text: t('liability.consumerLoan'), icon: 'icon-personal-loan', color: '#7c3aed' },
  personal_loan: { text: t('liability.personalLoan'), icon: 'icon-personal-loan', color: '#ea580c' },
  other: { text: t('liability.other'), icon: 'icon-other-liability', color: '#64748b' },
}))

const categoryText = computed(() => categoryMap.value[props.liability.category]?.text || props.liability.category)
const categoryIcon = computed(() => categoryMap.value[props.liability.category]?.icon || 'icon-other-liability')
const categoryColor = computed(() => categoryMap.value[props.liability.category]?.color || '#64748b')

const repaidPercent = computed(() => {
  const orig = Number(props.liability.original_amount)
  const remaining = Number(props.liability.remaining_amount)
  if (!orig) return 0
  return Math.round(((orig - remaining) / orig) * 100)
})

function formatAmountDisplay(amount: number | string): string {
  const n = Number(amount)
  if (n >= 100000000) return (n / 100000000).toFixed(2) + t('common.unitHundredMillion')
  if (n >= 10000) return (n / 10000).toFixed(1) + t('common.unitTenThousand')
  if (n >= 1000) return (n / 1000).toFixed(1) + t('common.unitThousand')
  return n.toLocaleString('zh-CN')
}

// Long-press detection
const longPressTimer = ref<ReturnType<typeof setTimeout> | null>(null)
const touchMoved = ref(false)

function onTouchStart() {
  touchMoved.value = false
  longPressTimer.value = setTimeout(() => {
    if (!touchMoved.value) {
      emit('longpress', props.liability)
    }
  }, 500)
}

function onTouchMove() {
  touchMoved.value = true
  if (longPressTimer.value) {
    clearTimeout(longPressTimer.value)
    longPressTimer.value = null
  }
}

function onTouchEnd() {
  if (longPressTimer.value) {
    clearTimeout(longPressTimer.value)
    longPressTimer.value = null
  }
}

function handleClick() {
  if (props.selectMode) {
    // toggle selection via parent
    emit('click')
  } else {
    emit('click')
  }
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Crimson+Pro:wght@600&display=swap');

.liability-swipe-cell {
  margin-bottom: 12px;
}

.liability-card {
  background: var(--card-bg);
  border-radius: 16px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(0, 0, 0, 0.06);
  position: relative;
  overflow: hidden;
}

[data-theme='dark'] .liability-card {
  border-color: rgba(255, 255, 255, 0.08);
}

.liability-card:active {
  transform: scale(0.98);
}

.liability-card.is-selected {
  border-color: #dc2626;
  background: rgba(220, 38, 38, 0.04);
}

[data-theme='dark'] .liability-card.is-selected {
  background: rgba(220, 38, 38, 0.1);
}

.liability-card.select-mode {
  padding-left: 48px;
}

/* Selection overlay */
.select-overlay {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1;
}

/* Swipe action buttons */
.swipe-actions {
  display: flex;
  height: 100%;
}

.swipe-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 64px;
  border: none;
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
  color: #fff;
  padding: 0;
}

.swipe-btn--pay {
  background: #059669;
}

.swipe-btn--edit {
  background: #0891b2;
}

.swipe-btn--delete {
  background: #dc2626;
  border-radius: 0 16px 16px 0;
}

/* Card internals (unchanged) */
.card-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.card-icon {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  overflow: hidden;
}

[data-theme='dark'] .card-icon {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.card-icon::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    115deg,
    transparent 30%,
    rgba(255, 255, 255, 0.5) 50%,
    transparent 70%
  );
  transform: translateX(-150%);
  animation: icon-shimmer 3s ease-in-out infinite;
  pointer-events: none;
}

.icon-svg {
  position: relative;
  z-index: 1;
  width: 24px;
  height: 24px;
  fill: white;
  color: white;
}

@keyframes icon-shimmer {
  0% {
    transform: translateX(-150%);
  }
  60%,
  100% {
    transform: translateX(150%);
  }
}

@media (prefers-reduced-motion: reduce) {
  .card-icon::before {
    animation: none;
    display: none;
  }
}

.card-header-text {
  flex: 1;
  min-width: 0;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.name {
  font-family: 'IBM Plex Sans', -apple-system, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-tag {
  flex-shrink: 0;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-tertiary);
}

.meta-item {
  white-space: nowrap;
}

.meta-divider::before {
  content: '·';
  margin-right: 8px;
  color: var(--text-quaternary);
}

.card-body {
  padding: 16px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

[data-theme='dark'] .card-body {
  border-color: rgba(255, 255, 255, 0.08);
}

.amount-section {
  margin-bottom: 16px;
}

.amount-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.amount-value {
  font-family: 'Crimson Pro', Georgia, serif;
  font-size: 32px;
  font-weight: 600;
  color: #dc2626;
  line-height: 1.2;
  letter-spacing: -0.5px;
}

[data-theme='dark'] .amount-value {
  color: #f87171;
}

.details-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.detail-value {
  font-family: 'IBM Plex Sans', -apple-system, sans-serif;
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.card-footer {
  margin-top: 16px;
}

.progress-bar {
  height: 8px;
  background: rgba(220, 38, 38, 0.1);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

[data-theme='dark'] .progress-bar {
  background: rgba(248, 113, 113, 0.15);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #10b981 0%, #059669 100%);
  border-radius: 4px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.progress-text {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.progress-label {
  color: #059669;
  font-weight: 500;
}

[data-theme='dark'] .progress-label {
  color: #34d399;
}

.progress-remaining {
  color: var(--text-tertiary);
}
</style>
