<template>
  <ChallengeShell
    :config="config"
    :feedback-message="feedbackMessage"
    :feedback-is-correct="feedbackIsCorrect"
    :has-any-placement="hasAnyPlacement"
    :completed="completed"
    :show-tutor-suggestion="showTutorSuggestion"
    :status-text="statusText"
    @check="checkAnswer"
    @continue="onContinue"
    @request-tutor="emit('requestTutor')"
  >
    <!-- Sequence slots — tap placed items or empty slots -->
    <div class="challenge-sequence">
      <div
        v-for="(_, idx) in config.correctOrder"
        :key="idx"
        class="challenge-slot"
        :class="{
          'challenge-slot--filled': sequence[idx] !== null,
          'challenge-slot--active': selectedObjectId !== null && sequence[idx] === null,
        }"
        @click="handleSlotClick(idx)"
      >
        <span v-if="sequence[idx] !== null" class="challenge-slot__icon">
          {{ getObjectIcon(sequence[idx]!) }}
        </span>
        <span v-else class="challenge-slot__placeholder">{{ idx + 1 }}</span>
      </div>
    </div>

    <!-- Object pool — remaining items to place -->
    <div class="challenge-pool">
      <button
        v-for="obj in remainingObjects"
        :key="obj.id"
        class="challenge-object"
        :class="{ 'challenge-object--selected': selectedObjectId === obj.id }"
        @click="selectObject(obj.id)"
      >
        <span v-if="obj.icon" class="challenge-object__icon">{{ obj.icon }}</span>
        <span class="challenge-object__label">{{ localizedLabel(obj.label, obj.labelZh) }}</span>
      </button>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { OrderChallenge } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'

defineOptions({ name: 'OrderChallenge' })

const props = defineProps<{
  config: OrderChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

// ── Interaction state ──

const selectedObjectId = ref<string | null>(null)
/** Slot index → object id (null = empty). */
const sequence = reactive<(string | null)[]>(
  props.config.correctOrder.map(() => null),
)
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackIsCorrect = ref(false)
const attemptCount = ref(0)

// ── Session persistence (AE5) ──

const STORAGE_KEY = `numina:challenge:${props.config.id}`

interface PersistedState {
  sequence: (string | null)[]
  attemptCount: number
  completed: boolean
  feedbackMessage: string
  feedbackIsCorrect: boolean
}

function restoreState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as PersistedState
    const savedSeq = saved.sequence ?? []
    for (let i = 0; i < props.config.correctOrder.length; i++) {
      const objId = savedSeq[i] ?? null
      // Only restore if the object still exists in the config
      sequence[i] = objId && props.config.objects.some((o) => o.id === objId) ? objId : null
    }
    attemptCount.value = saved.attemptCount ?? 0
    completed.value = saved.completed ?? false
    feedbackMessage.value = saved.feedbackMessage ?? ''
    feedbackIsCorrect.value = saved.feedbackIsCorrect ?? false
  } catch {
    // Storage unavailable
  }
}

function clearState() {
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage unavailable
  }
}

restoreState()

watch(
  [sequence, attemptCount, completed, feedbackMessage, feedbackIsCorrect],
  () => {
    try {
      const state: PersistedState = {
        sequence: [...sequence],
        attemptCount: attemptCount.value,
        completed: completed.value,
        feedbackMessage: feedbackMessage.value,
        feedbackIsCorrect: feedbackIsCorrect.value,
      }
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
      // Storage unavailable
    }
  },
  { deep: true },
)

// ── Computed ──

const isZh = computed(() => locale.value.startsWith('zh'))

/** Objects not yet placed in any slot. */
const placedIds = computed(() => new Set(sequence.filter((id): id is string => id !== null)))

const remainingObjects = computed(() =>
  props.config.objects.filter((o) => !placedIds.value.has(o.id)),
)

const hasAnyPlacement = computed(() => placedIds.value.size > 0)

const statusText = computed(() =>
  t('learning.challenge.placedCount', {
    placed: placedIds.value.size,
    total: props.config.objects.length,
  }),
)

const showTutorSuggestion = computed(() =>
  attemptCount.value >= 2 && !completed.value,
)

// ── Interaction methods ──

function localizedLabel(en: string, zh?: string): string {
  if (isZh.value && zh) return zh
  return en
}

function getObjectIcon(objId: string): string {
  const obj = props.config.objects.find((o) => o.id === objId)
  return obj?.icon ?? '●'
}

function selectObject(objId: string) {
  if (completed.value) return
  selectedObjectId.value = selectedObjectId.value === objId ? null : objId
}

/** Tap a slot: if empty + object selected → place it; if filled → return to pool. */
function handleSlotClick(idx: number) {
  if (completed.value) return

  if (sequence[idx] !== null) {
    // Slot is filled — return the object to the pool
    sequence[idx] = null
    return
  }

  if (selectedObjectId.value) {
    // Place the selected object in this slot
    sequence[idx] = selectedObjectId.value
    selectedObjectId.value = null
  }
}

function onContinue() {
  clearState()
  emit('complete')
}

function checkAnswer() {
  attemptCount.value++
  const result = evaluateOrder()
  feedbackIsCorrect.value = result.isCorrect
  if (result.isCorrect) {
    completed.value = true
    feedbackMessage.value = isZh.value
      ? props.config.discoveryMessageZh
      : props.config.discoveryMessage
  } else {
    feedbackMessage.value = result.hint
  }
}

/** Check if the current sequence matches the correct order. */
function evaluateOrder(): { isCorrect: boolean; hint: string } {
  // All slots must be filled
  const allFilled = sequence.every((id) => id !== null)
  if (!allFilled) {
    return { isCorrect: false, hint: t('learning.challenge.hintOrderIncomplete') }
  }

  // Check each position
  for (let i = 0; i < props.config.correctOrder.length; i++) {
    if (sequence[i] !== props.config.correctOrder[i]) {
      return { isCorrect: false, hint: t('learning.challenge.hintOrderWrong') }
    }
  }

  return { isCorrect: true, hint: '' }
}
</script>

<style scoped>
/* Sequence slots */
.challenge-sequence {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  min-height: 64px;
  padding: 12px;
  background: var(--continent-canvas-bg);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-hairline);
}

.challenge-slot {
  width: 64px;
  height: 64px;
  border: 2px dashed var(--color-hairline);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  position: relative;
}

.challenge-slot--filled {
  border-style: solid;
  border-color: var(--color-brand-mint);
  background: rgba(var(--color-brand-mint-rgb), 0.08);
}

.challenge-slot--active {
  border-color: var(--color-brand-ochre);
  background: rgba(var(--color-brand-ochre-rgb), 0.08);
}

.challenge-slot__icon {
  font-size: 28px;
  line-height: 1;
}

.challenge-slot__placeholder {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-muted);
}

/* Object pool */
.challenge-pool {
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

.challenge-object {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 52px;
  min-height: 52px;
  padding: 8px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.1s;
}

.challenge-object:active {
  transform: scale(0.95);
}

.challenge-object--selected {
  border-color: var(--color-brand-ochre);
  background: var(--challenge-object-active);
  box-shadow: 0 0 0 2px rgba(var(--color-brand-ochre-rgb), 0.25);
}

.challenge-object__icon {
  font-size: 24px;
  line-height: 1;
}

.challenge-object__label {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-body);
  text-align: center;
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .challenge-slot,
  .challenge-object {
    transition: none;
  }
}
</style>
