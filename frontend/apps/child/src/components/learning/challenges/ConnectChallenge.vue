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
    <!-- Two columns; tapping one item then another pairs them -->
    <div class="connect-board">
      <div class="connect-column">
        <button
          v-for="item in config.leftItems"
          :key="item.id"
          class="connect-item"
          :class="{
            'connect-item--selected': selectedLeftId === item.id,
            'connect-item--paired': pairs[item.id] !== undefined,
          }"
          :disabled="completed"
          @click="selectLeft(item.id)"
        >
          <span class="connect-item__label">{{ localizedLabel(item.label, item.labelZh) }}</span>
          <span v-if="pairs[item.id]" class="connect-item__partner">
            → {{ pairLabel(pairs[item.id]!) }}
          </span>
        </button>
      </div>

      <div class="connect-column">
        <button
          v-for="item in config.rightItems"
          :key="item.id"
          class="connect-item"
          :class="{
            'connect-item--selected': selectedRightId === item.id,
            'connect-item--paired': pairedRightIds.has(item.id),
          }"
          :disabled="completed"
          @click="selectRight(item.id)"
        >
          <span class="connect-item__label">{{ localizedLabel(item.label, item.labelZh) }}</span>
          <span v-if="pairedRightIds.has(item.id)" class="connect-item__partner">
            ↩ {{ leftLabelForRight(item.id) }}
          </span>
        </button>
      </div>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  ChallengeJudgement,
  ConnectChallenge,
} from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { useChallengeState } from './useChallengeState'

defineOptions({ name: 'ConnectChallenge' })

const props = defineProps<{
  config: ConnectChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

const { state, completed, feedbackMessage, feedbackVerdict, showTutorSuggestion, allowEarlyContinue, applyJudgement, clearState } =
  useChallengeState<{
    pairs: Record<string, string>
    selectedLeftId: string | null
    selectedRightId: string | null
  }>({
    id: props.config.id,
    initial: { pairs: {}, selectedLeftId: null, selectedRightId: null },
  })

const pairs = computed(() => state.pairs)
const selectedLeftId = computed(() => state.selectedLeftId)
const selectedRightId = computed(() => state.selectedRightId)
const isZh = computed(() => locale.value.startsWith('zh'))

const pairedRightIds = computed(() => new Set(Object.values(state.pairs)))

const hasAnyPlacement = computed(() => Object.keys(state.pairs).length > 0)

const statusText = computed(() =>
  t('learning.challenge.placedCount', {
    placed: Object.keys(state.pairs).length,
    total: props.config.leftItems.length,
  }),
)

function localizedLabel(en: string, zh?: string): string {
  return isZh.value && zh ? zh : en
}

function pairLabel(rightId: string): string {
  const item = props.config.rightItems.find((r) => r.id === rightId)
  return item ? localizedLabel(item.label, item.labelZh) : rightId
}

function leftLabelForRight(rightId: string): string {
  const entry = Object.entries(state.pairs).find(([, rid]) => rid === rightId)
  if (!entry) return ''
  const item = props.config.leftItems.find((l) => l.id === entry[0])
  return item ? localizedLabel(item.label, item.labelZh) : ''
}

/** Tapping a left item selects it (or unpairs it if already paired). */
function selectLeft(leftId: string) {
  if (completed.value) return
  if (state.pairs[leftId] !== undefined) {
    delete state.pairs[leftId]
    return
  }
  state.selectedLeftId = state.selectedLeftId === leftId ? null : leftId
}

/** Tapping a right item completes the pair if a left item is selected. */
function selectRight(rightId: string) {
  if (completed.value) return
  // Unpair an already-paired right item
  const existing = Object.entries(state.pairs).find(([, rid]) => rid === rightId)
  if (existing) {
    delete state.pairs[existing[0]]
    return
  }
  if (state.selectedLeftId) {
    state.pairs[state.selectedLeftId] = rightId
    state.selectedLeftId = null
  } else {
    state.selectedRightId = state.selectedRightId === rightId ? null : rightId
  }
}

/** Evaluate all pairs against the target mapping. */
function judgeConnect(
  current: Record<string, string>,
  config: ConnectChallenge,
): ChallengeJudgement {
  const allPaired = config.leftItems.every((l) => current[l.id] !== undefined)
  if (!allPaired) {
    return { verdict: 'wrong', hint: t('learning.challenge.connect.hintIncomplete') }
  }
  const wrongPairs = config.leftItems.filter(
    (l) => current[l.id] !== config.correctPairs[l.id],
  ).length
  if (wrongPairs === 0) {
    return { verdict: 'correct', hint: '' }
  }
  const isClose = wrongPairs === 1
  return {
    verdict: isClose ? 'close' : 'wrong',
    hint: isClose
      ? t('learning.challenge.connect.hintClose')
      : t('learning.challenge.connect.hintWrong'),
  }
}

function checkAnswer() {
  const judgement = judgeConnect(state.pairs, props.config)
  const success = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
  applyJudgement(judgement, success)
}

function onContinue() {
  clearState()
  emit('complete')
}
</script>

<style scoped>
.connect-board {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.connect-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.connect-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  /* R10: every pairable item is a tap target */
  min-height: 48px;
  padding: 10px 12px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, background 0.15s;
}

.connect-item--selected {
  border-color: var(--color-brand-ochre);
  background: var(--challenge-object-active);
}

.connect-item--paired {
  border-color: var(--color-brand-mint);
  background: rgba(var(--color-brand-mint-rgb), 0.08);
}

.connect-item__label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
}

.connect-item__partner {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-muted);
}

@media (prefers-reduced-motion: reduce) {
  .connect-item {
    transition: none;
  }
}
</style>
