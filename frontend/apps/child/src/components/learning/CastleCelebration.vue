<template>
  <div
    class="castle-celebration"
    :class="{ 'castle-celebration--static': reducedMotion }"
    data-test="castle-celebration"
    role="status"
    aria-live="polite"
  >
    <!-- Reduced motion: toast-equivalent text path instead of confetti -->
    <p v-if="reducedMotion" class="castle-celebration__toast">
      {{ t('learning.castle.reducedMotionToast') }}
    </p>

    <template v-else>
      <div class="castle-celebration__confetti" aria-hidden="true">
        <i
          v-for="n in CONFETTI_COUNT"
          :key="n"
          class="confetti"
          :style="confettiStyle(n)"
        />
      </div>
      <p class="castle-celebration__title">
        {{ t('learning.castle.celebrationTitle') }}
      </p>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'CastleCelebration' })

import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReducedMotion } from '@/composables/useReducedMotion'

const emit = defineEmits<{ done: [] }>()

const { t } = useI18n()
const reducedMotion = useReducedMotion()

const CONFETTI_COUNT = 24
const DURATION_MS = 2400

/** Deterministic scatter so tests are stable (no Math.random). */
function confettiStyle(index: number): Record<string, string> {
  const left = (index * 37) % 100
  const delay = (index % 6) * 0.12
  const hue = (index * 47) % 360
  return {
    left: `${left}%`,
    animationDelay: `${delay}s`,
    background: `hsl(${hue} 70% 60%)`,
  }
}

function scheduleDone(): void {
  window.setTimeout(() => emit('done'), reducedMotion.value ? 1500 : DURATION_MS)
}

onMounted(scheduleDone)
watch(reducedMotion, scheduleDone)
</script>

<style scoped>
.castle-celebration {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 100;
}
.castle-celebration__confetti {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.confetti {
  position: absolute;
  top: -12px;
  width: 8px;
  height: 12px;
  border-radius: 2px;
  animation: confetti-fall 2.2s ease-in forwards;
}
.castle-celebration__title,
.castle-celebration__toast {
  position: relative;
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg, 16px);
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-size: 16px;
  box-shadow: var(--shadow-lg, 0 8px 24px rgb(0 0 0 / 18%));
}

@keyframes confetti-fall {
  from {
    transform: translateY(0) rotate(0deg);
    opacity: 1;
  }
  to {
    transform: translateY(100vh) rotate(540deg);
    opacity: 0;
  }
}

/* Reduced motion: no animation at all (KTD6 / OQ3). */
@media (prefers-reduced-motion: reduce) {
  .confetti {
    animation: none !important;
    display: none;
  }
}
.castle-celebration--static .confetti {
  animation: none !important;
  display: none;
}
</style>
