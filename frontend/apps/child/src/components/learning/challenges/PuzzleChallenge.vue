<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-verdict="feedbackVerdict"
    :has-any-placement="hasAnyPlacement"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :allow-early-continue="allowEarlyContinue"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <!-- Slots the child fills -->
    <div class="puzzle-slots">
      <button
        v-for="slot in config.slots"
        :key="slot.id"
        class="puzzle-slot"
        :class="{
          'puzzle-slot--filled': placement[slot.id] !== undefined,
          'puzzle-slot--active': selectedPieceId !== null && placement[slot.id] === undefined,
        }"
        :disabled="completed"
        @click="handleSlotTap(slot.id)"
      >
        <span v-if="placement[slot.id]" class="puzzle-slot__piece">
          {{ pieceIcon(placement[slot.id]!) }}
        </span>
        <span v-else class="puzzle-slot__label">{{ localizedLabel(slot.label, slot.labelZh) }}</span>
      </button>
    </div>

    <!-- Available pieces -->
    <div class="puzzle-pool">
      <button
        v-for="piece in remainingPieces"
        :key="piece.id"
        class="puzzle-piece"
        :class="{ 'puzzle-piece--selected': selectedPieceId === piece.id }"
        :disabled="completed"
        @click="selectPiece(piece.id)"
      >
        <span v-if="piece.icon" class="puzzle-piece__icon">{{ piece.icon }}</span>
        <span class="puzzle-piece__label">{{ localizedLabel(piece.label, piece.labelZh) }}</span>
      </button>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  ChallengeJudgement,
  PuzzleChallenge,
} from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { useChallengeState } from './useChallengeState'

defineOptions({ name: 'PuzzleChallenge' })

const props = defineProps<{
  config: PuzzleChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

const { state, completed, feedbackMessage, feedbackVerdict, showTutorSuggestion, allowEarlyContinue, applyJudgement, clearState } =
  useChallengeState<{ placement: Record<string, string>; selectedPieceId: string | null }>({
    id: props.config.id,
    initial: { placement: {}, selectedPieceId: null },
  })

const placement = computed(() => state.placement)
const selectedPieceId = computed(() => state.selectedPieceId)
const isZh = computed(() => locale.value.startsWith('zh'))

const placedPieceIds = computed(() => new Set(Object.values(state.placement)))

const remainingPieces = computed(() =>
  props.config.objects.filter((o) => !placedPieceIds.value.has(o.id)),
)

const hasAnyPlacement = computed(() => Object.keys(state.placement).length > 0)

const statusText = computed(() =>
  t('learning.challenge.placedCount', {
    placed: Object.keys(state.placement).length,
    total: props.config.slots.length,
  }),
)

function localizedLabel(en: string, zh?: string): string {
  return isZh.value && zh ? zh : en
}

function pieceIcon(pieceId: string): string {
  const piece = props.config.objects.find((o) => o.id === pieceId)
  return piece?.icon ?? piece?.label ?? '●'
}

function selectPiece(pieceId: string) {
  if (completed.value) return
  state.selectedPieceId = state.selectedPieceId === pieceId ? null : pieceId
}

/** Tap empty slot with a piece selected → place; tap filled slot → return. */
function handleSlotTap(slotId: string) {
  if (completed.value) return
  if (state.placement[slotId] !== undefined) {
    delete state.placement[slotId]
    return
  }
  if (state.selectedPieceId) {
    state.placement[slotId] = state.selectedPieceId
    state.selectedPieceId = null
  }
}

/** Evaluate the placement against the target arrangement. */
function judgePuzzle(
  current: Record<string, string>,
  config: PuzzleChallenge,
): ChallengeJudgement {
  const allFilled = config.slots.every((s) => current[s.id] !== undefined)
  if (!allFilled) {
    return { verdict: 'wrong', hint: t('learning.challenge.puzzle.hintIncomplete') }
  }
  const wrongSlots = config.slots.filter(
    (s) => current[s.id] !== config.correctPlacement[s.id],
  ).length
  if (wrongSlots === 0) {
    return { verdict: 'correct', hint: '' }
  }
  // A single misplaced piece is a near miss.
  const isClose = wrongSlots === 1
  return {
    verdict: isClose ? 'close' : 'wrong',
    hint: isClose
      ? t('learning.challenge.puzzle.hintClose')
      : t('learning.challenge.puzzle.hintWrong'),
  }
}

function checkAnswer() {
  const judgement = judgePuzzle(state.placement, props.config)
  const success = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
  applyJudgement(judgement, success)
}

function onContinue() {
  clearState()
  emit('complete')
}
</script>

<style scoped>
.puzzle-slots {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  padding: 12px;
  background: var(--continent-canvas-bg);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-hairline);
}

.puzzle-slot {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  min-height: 48px;
  padding: 8px;
  border: 2px dashed var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.puzzle-slot--filled {
  border-style: solid;
  border-color: var(--color-brand-mint);
  background: rgba(var(--color-brand-mint-rgb), 0.08);
}

.puzzle-slot--active {
  border-color: var(--color-brand-ochre);
  background: rgba(var(--color-brand-ochre-rgb), 0.08);
}

.puzzle-slot__piece {
  font-size: 24px;
  line-height: 1;
}

.puzzle-slot__label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted);
  text-align: center;
}

.puzzle-pool {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  min-height: 52px;
  padding: 8px;
  background: var(--continent-canvas-bg);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-hairline);
}

.puzzle-piece {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 52px;
  min-height: 48px;
  padding: 8px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.1s;
}

.puzzle-piece:active {
  transform: scale(0.95);
}

.puzzle-piece--selected {
  border-color: var(--color-brand-ochre);
  background: var(--challenge-object-active);
  box-shadow: 0 0 0 2px rgba(var(--color-brand-ochre-rgb), 0.25);
}

.puzzle-piece__icon {
  font-size: 22px;
  line-height: 1;
}

.puzzle-piece__label {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-body);
  text-align: center;
}

@media (prefers-reduced-motion: reduce) {
  .puzzle-slot,
  .puzzle-piece {
    transition: none;
  }
}
</style>
