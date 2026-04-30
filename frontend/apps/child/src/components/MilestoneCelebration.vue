<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="milestone-overlay"
      :aria-label="t('milestone.overlayLabel')"
      role="dialog"
      aria-modal="true"
      @click="dismiss"
    >
      <div class="confetti-container" aria-hidden="true">
        <span v-for="i in 20" :key="i" class="confetti" :style="confettiStyle(i)" />
      </div>
      <div class="milestone-card" @click.stop>
        <div class="milestone-icon" aria-hidden="true">{{ icon }}</div>
        <div class="milestone-title">{{ title }}</div>
        <div class="milestone-desc">{{ desc }}</div>
        <button class="dismiss-btn" @click="dismiss">{{ t('milestone.dismissBtn') }}</button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MilestoneType } from '@/api/milestones'

const props = defineProps<{
  visible: boolean
  milestoneType: MilestoneType | string
}>()

const emit = defineEmits<{ (e: 'dismiss'): void }>()
const { t } = useI18n()

function dismiss() {
  emit('dismiss')
}

const icon  = computed(() => t(`milestone.icons.${props.milestoneType}`, t('milestone.icons.default')))
const title = computed(() => t(`milestone.titles.${props.milestoneType}`, t('milestone.titles.default')))
const desc  = computed(() => t(`milestone.descs.${props.milestoneType}`, t('milestone.descs.default')))

/* Clay brand palette for confetti */
const COLORS = ['#ff4d8b', '#e8b94a', '#a4d4c5', '#b8a4ed', '#ffb084', '#ff6b5a']

function confettiStyle(i: number) {
  const color = COLORS[i % COLORS.length]
  const left = ((i * 37 + 11) % 100)
  const delay = ((i * 0.15) % 1.5).toFixed(2)
  const size = 8 + (i % 5) * 2
  return {
    left: `${left}%`,
    animationDelay: `${delay}s`,
    background: color,
    width: `${size}px`,
    height: `${size}px`,
  }
}
</script>

<style scoped>
.milestone-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.confetti-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}
.confetti {
  position: absolute;
  top: -10px;
  border-radius: 2px;
  animation: fall 2s ease-in forwards;
}
@keyframes fall {
  0%   { transform: translateY(0) rotate(0deg); opacity: 1; }
  100% { transform: translateY(110vh) rotate(720deg); opacity: 0; }
}

/* Card — cream surface */
.milestone-card {
  background: var(--color-canvas);
  border-radius: var(--radius-xl);
  padding: 32px 28px;
  text-align: center;
  max-width: 300px;
  width: 90%;
  position: relative;
  z-index: 1;
  border: 1px solid var(--color-hairline);
}
.milestone-icon  { font-size: 56px; margin-bottom: 12px; }
.milestone-title {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
  margin-bottom: 8px;
  letter-spacing: -0.3px;
}
.milestone-desc {
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-body);
  margin-bottom: 24px;
  line-height: 1.55;
}

/* Dismiss — primary CTA */
.dismiss-btn {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border: none;
  border-radius: var(--radius-md);
  padding: 12px 32px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  height: 44px;
  min-width: 44px;
}
.dismiss-btn:active { transform: scale(0.96); }
</style>
