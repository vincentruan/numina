<template>
  <div
    v-if="signedAt"
    class="anniversary-display"
    :class="{ 'is-milestone': isMilestone }"
  >
    <span class="anniversary-text">
      {{ t('manifesto.companionDays', { days: daysSinceSigned }) }}
    </span>
    <span
      v-if="isMilestone"
      class="anniversary-confetti"
      aria-hidden="true"
    ></span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  signedAt: string | null
}>()

const { t } = useI18n()

const daysSinceSigned = computed<number>(() => {
  if (!props.signedAt) return 0
  const signedDate = new Date(props.signedAt)
  if (Number.isNaN(signedDate.getTime())) return 0
  const now = new Date()
  const diffMs = now.getTime() - signedDate.getTime()
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)))
})

const isMilestone = computed<boolean>(() => {
  const d = daysSinceSigned.value
  return d === 30 || d === 365
})
</script>

<style scoped>
.anniversary-display {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: linear-gradient(
    135deg,
    rgba(200, 150, 60, 0.08),
    rgba(200, 150, 60, 0.02)
  );
  border-radius: var(--radius-md, 12px);
  border: 1px solid rgba(200, 150, 60, 0.18);
}

.anniversary-text {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-brand-ochre, #c8963c);
  font-weight: 500;
  line-height: 1.4;
}

.is-milestone .anniversary-text {
  font-weight: 600;
}

.anniversary-confetti {
  position: relative;
  display: inline-block;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.anniversary-confetti::before,
.anniversary-confetti::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--color-brand-ochre, #c8963c);
  opacity: 0;
  animation: anniversary-pulse 1500ms ease-out;
}

.anniversary-confetti::after {
  animation-delay: 300ms;
}

@keyframes anniversary-pulse {
  0% {
    opacity: 0.6;
    transform: scale(0.3);
  }
  50% {
    opacity: 0.3;
  }
  100% {
    opacity: 0;
    transform: scale(1.4);
  }
}

@media (prefers-reduced-motion: reduce) {
  .anniversary-confetti::before,
  .anniversary-confetti::after {
    animation: none;
  }
}
</style>
