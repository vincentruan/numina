<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-verdict="feedbackVerdict"
    :has-any-placement="selectedId !== null"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :allow-early-continue="allowEarlyContinue"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <!-- The sequence so far -->
    <div class="pattern-sequence">
      <span
        v-for="item in config.sequence"
        :key="item.id"
        class="pattern-sequence__item"
      >
        {{ item.icon ?? item.label }}
      </span>
      <span class="pattern-sequence__item pattern-sequence__item--blank">?</span>
    </div>

    <!-- Candidate answers -->
    <div class="pattern-options">
      <button
        v-for="option in config.options"
        :key="option.id"
        class="pattern-option"
        :class="{ 'pattern-option--selected': selectedId === option.id }"
        :disabled="completed"
        @click="selectOption(option.id)"
      >
        <span v-if="option.icon" class="pattern-option__icon">{{ option.icon }}</span>
        <span class="pattern-option__label">{{ localizedLabel(option.label, option.labelZh) }}</span>
      </button>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  ChallengeJudgement,
  PatternChallenge,
} from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { useChallengeState } from './useChallengeState'

defineOptions({ name: 'PatternChallenge' })

const props = defineProps<{
  config: PatternChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

const { state, completed, feedbackMessage, feedbackVerdict, showTutorSuggestion, allowEarlyContinue, applyJudgement, clearState } =
  useChallengeState<{ selectedId: string | null }>({
    id: props.config.id,
    initial: { selectedId: null },
  })

const selectedId = computed(() => state.selectedId)
const isZh = computed(() => locale.value.startsWith('zh'))

const statusText = computed(() =>
  selectedId.value ? t('learning.challenge.check') : t('learning.challenge.pattern.hintIncomplete'),
)

function localizedLabel(en: string, zh?: string): string {
  return isZh.value && zh ? zh : en
}

function selectOption(id: string) {
  if (completed.value) return
  state.selectedId = state.selectedId === id ? null : id
}

/** Evaluate the chosen option against the next item in the sequence. */
function judgePattern(
  selectedIdToCheck: string | null,
  config: PatternChallenge,
): ChallengeJudgement {
  if (!selectedIdToCheck) {
    return { verdict: 'wrong', hint: '' }
  }
  if (selectedIdToCheck === config.correctAnswer) {
    return { verdict: 'correct', hint: '' }
  }
  // A sibling option that sits next to the answer reads as a near miss.
  const answerIndex = config.options.findIndex((o) => o.id === config.correctAnswer)
  const chosenIndex = config.options.findIndex((o) => o.id === selectedIdToCheck)
  const isNeighbour = Math.abs(answerIndex - chosenIndex) === 1
  return {
    verdict: isNeighbour ? 'close' : 'wrong',
    hint: isNeighbour
      ? t('learning.challenge.pattern.hintClose')
      : t('learning.challenge.pattern.hintWrong'),
  }
}

function checkAnswer() {
  const hintIncomplete = t('learning.challenge.pattern.hintIncomplete')
  if (!selectedId.value) {
    feedbackMessage.value = hintIncomplete
    feedbackVerdict.value = 'wrong'
    return
  }
  const judgement = judgePattern(selectedId.value, props.config)
  const success = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
  applyJudgement(judgement, success)
}

function onContinue() {
  clearState()
  emit('complete')
}
</script>

<style scoped>
.pattern-sequence {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px 12px;
  background: var(--continent-canvas-bg);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-hairline);
}

.pattern-sequence__item {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  min-height: 48px;
  font-size: 26px;
  font-family: Inter, sans-serif;
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
}

.pattern-sequence__item--blank {
  border: 2px dashed var(--color-brand-ochre);
  color: var(--color-brand-ochre);
  font-weight: 700;
}

.pattern-options {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.pattern-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 64px;
  min-height: 64px;
  padding: 10px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.1s;
}

.pattern-option:active {
  transform: scale(0.95);
}

.pattern-option--selected {
  border-color: var(--color-brand-ochre);
  background: var(--challenge-object-active);
  box-shadow: 0 0 0 2px rgba(var(--color-brand-ochre-rgb), 0.25);
}

.pattern-option__icon {
  font-size: 26px;
  line-height: 1;
}

.pattern-option__label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
}

@media (prefers-reduced-motion: reduce) {
  .pattern-option {
    transition: none;
  }
}
</style>
