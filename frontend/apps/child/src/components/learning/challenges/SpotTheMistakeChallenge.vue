<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-verdict="feedbackVerdict"
    :has-any-placement="selectedIndex !== null"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :allow-early-continue="allowEarlyContinue"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <!-- Each line is its own full-width row control so the tap target stays
         comfortable on a phone (R10: 48px minimum). -->
    <div class="mistake-lines">
      <button
        v-for="(line, index) in displayLines"
        :key="index"
        class="mistake-line"
        :class="{ 'mistake-line--selected': selectedIndex === index }"
        :disabled="completed"
        @click="selectLine(index)"
      >
        <span class="mistake-line__number">{{ index + 1 }}</span>
        <span class="mistake-line__text">{{ line }}</span>
        <span class="mistake-line__mark" aria-hidden="true">
          {{ selectedIndex === index ? '✗' : '' }}
        </span>
      </button>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  ChallengeJudgement,
  SpotTheMistakeChallenge,
} from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { useChallengeState } from './useChallengeState'

defineOptions({ name: 'SpotTheMistakeChallenge' })

const props = defineProps<{
  config: SpotTheMistakeChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

const { state, completed, feedbackMessage, feedbackVerdict, showTutorSuggestion, allowEarlyContinue, applyJudgement, clearState } =
  useChallengeState<{ selectedIndex: number | null }>({
    id: props.config.id,
    initial: { selectedIndex: null },
  })

const selectedIndex = computed(() => state.selectedIndex)
const isZh = computed(() => locale.value.startsWith('zh'))

const displayLines = computed(() =>
  isZh.value && props.config.linesZh ? props.config.linesZh : props.config.lines,
)

const statusText = computed(() => t('learning.challenge.spotTheMistake.hintIncomplete'))

/** Evaluate whether the tapped line is the one containing the mistake. */
function judgeSpotMistake(
  selected: number | null,
  config: SpotTheMistakeChallenge,
): ChallengeJudgement {
  if (selected === null) {
    return { verdict: 'wrong', hint: '' }
  }
  if (selected === config.mistakeLineIndex) {
    return { verdict: 'correct', hint: '' }
  }
  // An adjacent line means the child homed in on the right region.
  const isAdjacent = Math.abs(selected - config.mistakeLineIndex) === 1
  return {
    verdict: isAdjacent ? 'close' : 'wrong',
    hint: isAdjacent
      ? t('learning.challenge.spotTheMistake.hintClose')
      : t('learning.challenge.spotTheMistake.hintWrong'),
  }
}

function selectLine(index: number) {
  if (completed.value) return
  state.selectedIndex = state.selectedIndex === index ? null : index
}

function checkAnswer() {
  if (selectedIndex.value === null) {
    feedbackMessage.value = t('learning.challenge.spotTheMistake.hintIncomplete')
    feedbackVerdict.value = 'wrong'
    return
  }
  const judgement = judgeSpotMistake(selectedIndex.value, props.config)
  const success = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
  applyJudgement(judgement, success)
}

function onContinue() {
  clearState()
  emit('complete')
}
</script>

<style scoped>
.mistake-lines {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mistake-line {
  display: flex;
  align-items: center;
  gap: 10px;
  /* R10: tap targets must stay comfortable for a child's finger */
  min-height: 48px;
  width: 100%;
  padding: 10px 12px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.mistake-line--selected {
  border-color: var(--color-brand-coral);
  background: rgba(var(--color-brand-coral-rgb), 0.08);
}

.mistake-line__number {
  flex: 0 0 auto;
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: var(--color-muted);
  min-width: 16px;
}

.mistake-line__text {
  flex: 1 1 auto;
  font-family: Inter, sans-serif;
  font-size: 15px;
  line-height: 1.5;
  color: var(--color-ink);
}

.mistake-line__mark {
  flex: 0 0 auto;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-brand-coral);
  min-width: 16px;
  text-align: center;
}

@media (prefers-reduced-motion: reduce) {
  .mistake-line {
    transition: none;
  }
}
</style>
