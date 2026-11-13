<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-verdict="feedbackVerdict"
    :has-any-placement="true"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :allow-early-continue="allowEarlyContinue"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <!-- Tap a cell to fill it; tap again to empty it. No free drawing. -->
    <div
      class="draw-grid"
      :style="{ gridTemplateColumns: `repeat(${config.gridCols}, minmax(0, 1fr))` }"
    >
      <button
        v-for="cell in cells"
        :key="cell.key"
        class="draw-cell"
        :class="{ 'draw-cell--filled': filledCells.includes(cell.key) }"
        :disabled="completed"
        :aria-label="cell.key"
        @click="toggleCell(cell.key)"
      />
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  ChallengeJudgement,
  DrawGridChallenge,
} from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { useChallengeState } from './useChallengeState'

defineOptions({ name: 'DrawGridChallenge' })

const props = defineProps<{
  config: DrawGridChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

const { state, completed, feedbackMessage, feedbackVerdict, showTutorSuggestion, allowEarlyContinue, applyJudgement, clearState } =
  useChallengeState<{ filledCells: string[] }>({
    id: props.config.id,
    initial: { filledCells: [] },
  })

const filledCells = computed(() => state.filledCells)
const isZh = computed(() => locale.value.startsWith('zh'))

/** Every cell key, row-major: `row-col`. */
const cells = computed(() => {
  const out: Array<{ key: string }> = []
  for (let row = 0; row < props.config.gridRows; row++) {
    for (let col = 0; col < props.config.gridCols; col++) {
      out.push({ key: `${row}-${col}` })
    }
  }
  return out
})

const statusText = computed(() =>
  t('learning.challenge.placedCount', {
    placed: filledCells.value.length,
    total: props.config.targetCells.length,
  }),
)

function toggleCell(key: string) {
  if (completed.value) return
  const index = state.filledCells.indexOf(key)
  if (index >= 0) {
    state.filledCells.splice(index, 1)
  } else {
    state.filledCells.push(key)
  }
}

/** Evaluate the filled set against the target set (order-independent). */
function judgeDrawGrid(
  filled: string[],
  config: DrawGridChallenge,
): ChallengeJudgement {
  if (filled.length === 0) {
    return { verdict: 'wrong', hint: t('learning.challenge.drawGrid.hintIncomplete') }
  }
  const filledSet = new Set(filled)
  const targetSet = new Set(config.targetCells)
  const differing = config.targetCells.filter((k) => !filledSet.has(k)).length +
    filled.filter((k) => !targetSet.has(k)).length

  if (differing === 0) {
    return { verdict: 'correct', hint: '' }
  }
  const isClose = differing === 1
  return {
    verdict: isClose ? 'close' : 'wrong',
    hint: isClose
      ? t('learning.challenge.drawGrid.hintClose')
      : t('learning.challenge.drawGrid.hintWrong'),
  }
}

function checkAnswer() {
  const judgement = judgeDrawGrid(state.filledCells, props.config)
  const success = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
  applyJudgement(judgement, success)
}

function onContinue() {
  clearState()
  emit('complete')
}
</script>

<style scoped>
.draw-grid {
  display: grid;
  gap: 4px;
  padding: 10px;
  background: var(--continent-canvas-bg);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-hairline);
  /* Keeps cell edges at or above the 48px tap floor on a 320px viewport */
  max-width: 100%;
}

.draw-cell {
  aspect-ratio: 1;
  min-width: 40px;
  min-height: 44px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-sm, 8px);
  background: var(--challenge-object-bg);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.draw-cell--filled {
  background: var(--color-brand-ochre);
  border-color: var(--color-brand-ochre);
}

@media (prefers-reduced-motion: reduce) {
  .draw-cell {
    transition: none;
  }
}
</style>
