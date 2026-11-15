<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-verdict="feedbackVerdict"
    :has-any-placement="hasStepped"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :allow-early-continue="allowEarlyContinue"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <!-- Tap-only numeric input: step the value up or down, no slider -->
    <div class="estimate-controls">
      <button
        class="estimate-step"
        :disabled="completed || value <= minValue"
        :aria-label="t('learning.challenge.estimate.step')"
        @click="step(-1)"
      >
        −
      </button>

      <div class="estimate-value">
        <span class="estimate-value__number">{{ value }}</span>
        <span class="estimate-value__unit">{{ unitLabel }}</span>
      </div>

      <button
        class="estimate-step"
        :disabled="completed || value >= maxValue"
        :aria-label="t('learning.challenge.estimate.step')"
        @click="step(1)"
      >
        +
      </button>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  ChallengeJudgement,
  EstimateChallenge,
} from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { useChallengeState } from './useChallengeState'

defineOptions({ name: 'EstimateChallenge' })

const props = defineProps<{
  config: EstimateChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

const { state, completed, feedbackMessage, feedbackVerdict, showTutorSuggestion, allowEarlyContinue, applyJudgement, clearState } =
  useChallengeState<{ value: number; hasStepped: boolean }>({
    id: props.config.id,
    initial: { value: props.config.startValue, hasStepped: false },
  })

const value = computed(() => state.value)
const hasStepped = computed(() => state.hasStepped)
const isZh = computed(() => locale.value.startsWith('zh'))

const unitLabel = computed(() =>
  isZh.value && props.config.unitLabelZh ? props.config.unitLabelZh : props.config.unitLabel,
)

/**
 * Bound the stepper so it cannot run away, while leaving room to step down
 * from the start value (a child needs to be able to correct an overshoot).
 */
const minValue = computed(() => Math.max(0, props.config.startValue - props.config.step * 2))
const maxValue = computed(
  () =>
    props.config.targetValue +
    props.config.wideTolerance +
    props.config.step * 2,
)

const statusText = computed(() => t('learning.challenge.estimate.step'))

function step(direction: 1 | -1) {
  if (completed.value) return
  state.value += direction * props.config.step
  state.hasStepped = true
}

/** Evaluate the estimate against the tolerance bands. */
function judgeEstimate(
  guess: number,
  config: EstimateChallenge,
): ChallengeJudgement {
  const error = Math.abs(guess - config.targetValue)
  if (error <= config.narrowTolerance) {
    return { verdict: 'correct', hint: '' }
  }
  if (error <= config.wideTolerance) {
    return { verdict: 'close', hint: t('learning.challenge.estimate.hintClose') }
  }
  return { verdict: 'wrong', hint: t('learning.challenge.estimate.hintWrong') }
}

function checkAnswer() {
  const judgement = judgeEstimate(state.value, props.config)
  const success = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
  applyJudgement(judgement, success)
}

function onContinue() {
  clearState()
  emit('complete')
}
</script>

<style scoped>
.estimate-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 12px;
}

.estimate-step {
  /* R10: large tap targets for a child's finger */
  min-width: 56px;
  min-height: 56px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  color: var(--color-ink);
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.1s;
}

.estimate-step:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.estimate-step:active:not(:disabled) {
  transform: scale(0.95);
}

.estimate-value {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 120px;
  padding: 8px 12px;
  background: var(--continent-canvas-bg);
  border-radius: var(--radius-md);
}

.estimate-value__number {
  font-family: Inter, sans-serif;
  font-size: 32px;
  font-weight: 700;
  color: var(--color-ink);
  line-height: 1.1;
}

.estimate-value__unit {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted);
}

@media (prefers-reduced-motion: reduce) {
  .estimate-step {
    transition: none;
  }
}
</style>
