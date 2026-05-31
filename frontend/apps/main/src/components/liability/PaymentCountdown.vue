<template>
  <div v-if="shouldShow" class="payment-countdown" :class="urgencyClass">
    <van-icon name="clock-o" class="countdown-icon" />
    <span class="countdown-text">{{ countdownText }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getDaysUntilPayment } from '@/utils/date'

const props = defineProps<{
  startDate: string | null
  endDate: string | null
  isActive: boolean
}>()

const { t } = useI18n()

const daysUntil = computed(() => getDaysUntilPayment(props.startDate))

const isEndDatePast = computed(() => {
  if (!props.endDate) return false
  const end = new Date(props.endDate)
  end.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return end < today
})

const shouldShow = computed(() => {
  if (!props.isActive) return false
  if (!props.startDate) return false
  if (isEndDatePast.value) return false
  return daysUntil.value !== null
})

const urgencyClass = computed(() => {
  const days = daysUntil.value
  if (days === null) return ''
  if (days <= 3) return 'countdown--danger'
  if (days <= 7) return 'countdown--warning'
  return 'countdown--default'
})

const countdownText = computed(() => {
  const days = daysUntil.value
  if (days === null) return ''
  if (days === 0) return t('liability.countdown.today')
  return t('liability.countdown.daysLeft', { days })
})
</script>

<style scoped>
.payment-countdown {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
}

.countdown-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.countdown--danger {
  background: rgba(220, 38, 38, 0.08);
  color: #dc2626;
}

[data-theme='dark'] .countdown--danger {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.countdown--warning {
  background: rgba(217, 119, 6, 0.08);
  color: #d97706;
}

[data-theme='dark'] .countdown--warning {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.countdown--default {
  background: rgba(0, 0, 0, 0.04);
  color: var(--text-secondary);
}

[data-theme='dark'] .countdown--default {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary);
}
</style>
