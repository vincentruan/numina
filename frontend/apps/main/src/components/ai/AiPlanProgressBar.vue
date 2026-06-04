<template>
  <div
    class="ai-plan-progress-bar"
    role="progressbar"
    :aria-valuemin="0"
    :aria-valuemax="steps.length"
    :aria-valuenow="completedCount"
    :aria-label="t('aiPlanProgress.ariaLabel', { completed: completedCount, total: steps.length })"
  >
    <!-- Track line -->
    <div class="progress-track" aria-hidden="true">
      <div
        class="progress-fill"
        :style="{ width: fillPercent + '%' }"
      />
    </div>

    <!-- Dots (visible portion) -->
    <div class="dots-row" aria-hidden="true">
      <template v-for="(step, index) in visibleSteps" :key="step.id">
        <!-- Connecting segment between dots -->
        <div
          v-if="index > 0"
          class="dot-segment"
          :class="segmentClass(index)"
        />
        <!-- Dot tap target -->
        <button
          class="dot-hit"
          :class="dotClass(step)"
          :aria-label="t('aiPlanProgress.stepAria', { index: index + 1, label: step.label, status: t('aiPlanProgress.status_' + step.status) })"
          @click="emit('step-tap', step.id)"
          @keydown.enter="emit('step-tap', step.id)"
          @keydown.space.prevent="emit('step-tap', step.id)"
        >
          <span class="dot" :class="dotClass(step)" />
        </button>
      </template>

      <!-- Overflow indicator -->
      <div v-if="hasOverflow" class="overflow-indicator" :title="t('aiPlanProgress.overflowTitle', { count: overflowCount })">
        <span class="overflow-dots">···</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PlanStep } from '@/types/agent-stream'

const MAX_VISIBLE = 6

const props = defineProps<{
  steps: PlanStep[]
  activeStepIndex: number
}>()

const emit = defineEmits<{
  (e: 'step-tap', stepId: string): void
}>()

const { t } = useI18n()

const hasOverflow = computed(() => props.steps.length > MAX_VISIBLE + 1)
const visibleSteps = computed(() =>
  hasOverflow.value ? props.steps.slice(0, MAX_VISIBLE) : props.steps,
)
const overflowCount = computed(() => props.steps.length - MAX_VISIBLE)

const completedCount = computed(
  () => props.steps.filter((s) => s.status === 'done').length,
)

// Fill percentage: based on completed steps
const fillPercent = computed(() => {
  if (props.steps.length <= 1) return 0
  return (completedCount.value / (props.steps.length - 1)) * 100
})

function dotClass(step: PlanStep): string {
  switch (step.status) {
    case 'active':
      return 'dot--active'
    case 'done':
      return 'dot--done'
    case 'error':
      return 'dot--error'
    default:
      return 'dot--pending'
  }
}

// A segment between dots[index-1] and dots[index] is "filled" if dots[index-1] is done
function segmentClass(index: number): string {
  const prevStep = visibleSteps.value[index - 1]
  if (prevStep && (prevStep.status === 'done')) return 'segment--filled'
  return 'segment--pending'
}
</script>

<style scoped>
.ai-plan-progress-bar {
  position: relative;
  height: 24px;
  display: flex;
  align-items: center;
  width: 100%;
  overflow: hidden;
}

/* Background track */
.progress-track {
  position: absolute;
  left: 12px;
  right: 12px;
  height: 2px;
  background: var(--separator);
  border-radius: 1px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--van-primary-color);
  border-radius: 1px;
  transition: width 0.3s ease;
}

/* Dots row sits above the track */
.dots-row {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  justify-content: space-between;
}

/* Invisible segment between dots (layout spacer) */
.dot-segment {
  flex: 1;
  height: 2px;
  /* purely for layout; the track line renders behind */
}

/* Tap target: 44×44 invisible button centered on the 8px dot */
.dot-hit {
  position: relative;
  width: 44px;
  height: 44px;
  /* collapse to 8px visually — center the dot inside the large tap zone */
  margin: -18px -18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  flex-shrink: 0;
  border-radius: 50%;
  z-index: 1;
}

.dot-hit:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}

/* Visual dot */
.dot {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  pointer-events: none;
}

/* Pending: 40% opacity on separator color */
.dot--pending {
  background: var(--separator);
  opacity: 0.4;
}

/* Active: primary color + pulse animation */
.dot--active {
  background: var(--van-primary-color);
  animation: dot-pulse 1.5s ease-in-out infinite;
}

/* Done: solid primary */
.dot--done {
  background: var(--van-primary-color);
  opacity: 1;
}

/* Error: red */
.dot--error {
  background: var(--color-error);
  opacity: 1;
}

@keyframes dot-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.3); }
}

/* Overflow indicator */
.overflow-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  cursor: default;
}

.overflow-dots {
  font-size: 10px;
  color: var(--text-tertiary);
  letter-spacing: 1px;
  line-height: 1;
}

/* Reduced motion: disable pulse */
@media (prefers-reduced-motion: reduce) {
  .dot--active {
    animation: none;
  }

  .progress-fill {
    transition: none;
  }
}
</style>
