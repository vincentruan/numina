<template>
  <div class="progress-ring-wrapper">
    <!-- Empty state: no tasks assigned today -->
    <div v-if="total === 0 && !loading" class="ring-empty">
      <p class="ring-empty-text">{{ t('home.progressRingNoTasks') }}</p>
    </div>

    <!-- Skeleton: loading with no data yet -->
    <div v-else-if="total === 0 && loading" class="ring-container">
      <div
        class="ring ring-skeleton"
        role="progressbar"
        aria-valuenow="0"
        aria-valuemin="0"
        aria-valuemax="0"
      />
      <div class="ring-center">
        <span class="ring-center-icon">⭐</span>
        <span class="ring-center-coins">—</span>
      </div>
    </div>

    <!-- Normal ring -->
    <div v-else class="ring-container">
      <div
        class="ring"
        :class="{ 'ring-all-done': allDone, 'no-transition': reducedMotion }"
        :style="ringStyle"
        role="progressbar"
        :aria-valuenow="completed"
        aria-valuemin="0"
        :aria-valuemax="total"
        :aria-label="t('home.progressRingAriaLabel', { completed, total })"
      />
      <div class="ring-center">
        <span class="ring-center-icon">⭐</span>
        <span v-if="allDone" class="ring-center-done">{{ t('home.progressRingAllDone') }}</span>
        <span v-else class="ring-center-coins">{{ remainingCoins }}</span>
      </div>
    </div>

    <!-- Graphical denominator: one dot per task (filled = done) -->
    <div v-if="total > 0" class="ring-dots" :aria-hidden="true">
      <span
        v-for="i in total"
        :key="i"
        class="ring-dot"
        :class="{ done: i <= completed, pending: i > completed && i <= completed + pending }"
      />
    </div>

    <!-- Subtitle: child-facing "X stars left to finish" -->
    <p v-if="total > 0" class="ring-subtitle">
      <template v-if="allDone">{{ t('home.progressRingAllDone') }}</template>
      <template v-else>{{ t('home.progressRingSubtitle', { remaining: remainingCoins }) }}</template>
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useReducedMotion } from '@/composables/useReducedMotion'

const props = defineProps<{
  completed: number
  pending: number
  total: number
  totalCoins: number
  loading?: boolean
}>()

const { t } = useI18n()
const reducedMotion = useReducedMotion()

const allDone = computed(() => props.total > 0 && props.completed === props.total)

// Stars still earnable today = coins from tasks not yet approved.
const remainingCoins = computed(() => Math.max(0, props.totalCoins - completedCoins(props)))

function completedCoins(p: { total: number; totalCoins: number; completed: number }): number {
  // Even split across tasks is an approximation; totalCoins is the sum of all
  // task rewards, so the per-task average gives a fair "earned so far" share.
  if (p.total <= 0) return 0
  return Math.round((p.totalCoins / p.total) * p.completed)
}

// Build conic-gradient: gold (completed) → teal (pending) → gray (remaining)
// Each segment is a fraction of 360deg
const ringStyle = computed(() => {
  if (props.total === 0) return {}

  const completedFrac = props.completed / props.total
  const pendingFrac = props.pending / props.total
  // remaining = 1 - completedFrac - pendingFrac (clamped to ≥ 0)
  const remainingFrac = Math.max(0, 1 - completedFrac - pendingFrac)

  const completedDeg = completedFrac * 360
  const pendingDeg = pendingFrac * 360
  const remainingDeg = remainingFrac * 360

  // Build stops: gold → teal → gray
  const stops: string[] = []
  let cursor = 0

  if (completedDeg > 0) {
    stops.push(`var(--color-brand-ochre) ${cursor}deg ${cursor + completedDeg}deg`)
    cursor += completedDeg
  }
  if (pendingDeg > 0) {
    stops.push(`var(--color-brand-teal) ${cursor}deg ${cursor + pendingDeg}deg`)
    cursor += pendingDeg
  }
  if (remainingDeg > 0) {
    stops.push(`var(--color-neutral-200, var(--color-surface-strong)) ${cursor}deg ${cursor + remainingDeg}deg`)
  }

  // Fallback: if all remaining (no progress), show full gray ring
  const gradient =
    stops.length > 0
      ? `conic-gradient(from -90deg, ${stops.join(', ')})`
      : `conic-gradient(from -90deg, var(--color-neutral-200, var(--color-surface-strong)) 0deg 360deg)`

  return { background: gradient }
})
</script>

<style scoped>
.progress-ring-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

/* ── Ring container: positions the donut and center label ── */
.ring-container {
  position: relative;
  width: 140px;
  height: 140px;
}

.ring {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  /* Donut via mask */
  -webkit-mask: radial-gradient(farthest-side, transparent 62%, #000 63%);
  mask: radial-gradient(farthest-side, transparent 62%, #000 63%);
  /* Default: full gray ring */
  background: var(--color-neutral-200, var(--color-surface-strong));
  transition: background 0.5s ease;
}

.ring.no-transition {
  transition: none;
}

/* Skeleton: static gray ring, no animation */
.ring-skeleton {
  background: var(--color-surface-strong);
  opacity: 0.5;
}

/* All-done celebration: subtle pulse (respects reduced-motion via .no-transition) */
.ring.ring-all-done:not(.no-transition) {
  animation: ring-pulse 1.2s ease-in-out 2;
}

@keyframes ring-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.04); }
}

/* ── Center label ── */
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  pointer-events: none;
}

.ring-center-icon {
  font-size: 20px;
  line-height: 1;
}

.ring-center-coins {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
  line-height: 1;
}
.ring-center-done {
  font-family: Inter, sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: var(--color-brand-ochre);
  line-height: 1.1;
  text-align: center;
  padding: 0 6px;
}

/* ── Graphical denominator: one dot per task ── */
.ring-dots {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 5px;
  max-width: 130px;
}
.ring-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-hairline);
  transition: background 0.3s ease, border-color 0.3s ease, transform 0.2s ease;
}
.ring-dot.done {
  background: var(--color-brand-ochre);
  border-color: var(--color-brand-ochre);
}
.ring-dot.pending {
  background: var(--color-brand-teal);
  border-color: var(--color-brand-teal);
  opacity: 0.55;
}

/* ── Subtitle ── */
.ring-subtitle {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-muted);
  margin: 0;
  text-align: center;
}

/* ── Empty state ── */
.ring-empty {
  padding: 16px 0;
}

.ring-empty-text {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted-soft);
  text-align: center;
  margin: 0;
}
</style>
