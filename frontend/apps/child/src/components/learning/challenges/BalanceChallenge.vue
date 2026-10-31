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
    <!-- Balance scale visualization -->
    <div class="challenge-balance">
      <!-- Left pan — fixed items -->
      <div class="challenge-pan challenge-pan--left">
        <div class="challenge-pan__label">{{ t('learning.challenge.balanceLeft') }}</div>
        <div class="challenge-pan__items">
          <span v-for="obj in config.leftFixed" :key="obj.id" class="challenge-pan__item">
            <span v-if="obj.icon" class="challenge-pan__icon">{{ obj.icon }}</span>
            <span class="challenge-pan__value">{{ objectValue(obj.id) }}</span>
          </span>
        </div>
        <div class="challenge-pan__total">
          {{ t('learning.challenge.balanceTotal', { value: leftTotal }) }}
        </div>
      </div>

      <!-- Fulcrum -->
      <div class="challenge-fulcrum" :class="fulcrumClass">
        <span class="challenge-fulcrum__icon">⚖️</span>
      </div>

      <!-- Right pan — slots for placement -->
      <div class="challenge-pan challenge-pan--right">
        <div class="challenge-pan__label">{{ t('learning.challenge.balanceRight') }}</div>
        <div class="challenge-pan__slots">
          <div
            v-for="idx in config.rightSlots"
            :key="idx"
            class="challenge-pan__slot"
            :class="{
              'challenge-pan__slot--filled': rightPlacements[idx - 1] !== null,
              'challenge-pan__slot--active': selectedObjectId !== null && rightPlacements[idx - 1] === null,
            }"
            @click="handleSlotClick(idx - 1)"
          >
            <span v-if="rightPlacements[idx - 1]" class="challenge-pan__item">
              <span class="challenge-pan__icon">{{ getObjectIcon(rightPlacements[idx - 1]!) }}</span>
              <span class="challenge-pan__value">{{ objectValue(rightPlacements[idx - 1]!) }}</span>
            </span>
            <span v-else class="challenge-pan__slot-placeholder">{{ idx }}</span>
          </div>
        </div>
        <div class="challenge-pan__total">
          {{ t('learning.challenge.balanceTotal', { value: rightTotal }) }}
        </div>
      </div>
    </div>

    <!-- Object pool — available items for the right side -->
    <div class="challenge-pool">
      <button
        v-for="obj in availableObjects"
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
import type { BalanceChallenge } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'

defineOptions({ name: 'BalanceChallenge' })

const props = defineProps<{
  config: BalanceChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

// ── Interaction state ──

const selectedObjectId = ref<string | null>(null)
/** Slot index → object id (null = empty). Length = config.rightSlots. */
const rightPlacements = reactive<(string | null)[]>(
  Array.from({ length: props.config.rightSlots }, () => null),
)
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackIsCorrect = ref(false)
const attemptCount = ref(0)

// ── Session persistence (AE5) ──

const STORAGE_KEY = `numina:challenge:${props.config.id}`

interface PersistedState {
  rightPlacements: (string | null)[]
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
    const savedPlacements = saved.rightPlacements ?? []
    for (let i = 0; i < props.config.rightSlots; i++) {
      const objId = savedPlacements[i] ?? null
      rightPlacements[i] = objId && props.config.objects.some((o) => o.id === objId) ? objId : null
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
  [rightPlacements, attemptCount, completed, feedbackMessage, feedbackIsCorrect],
  () => {
    try {
      const state: PersistedState = {
        rightPlacements: [...rightPlacements],
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

const placedIds = computed(
  () => new Set(rightPlacements.filter((id): id is string => id !== null)),
)

/** Objects available for placement (not yet in a slot). */
const availableObjects = computed(() =>
  props.config.objects.filter((o) => !placedIds.value.has(o.id)),
)

const hasAnyPlacement = computed(() => placedIds.value.size > 0)

function objectValue(objId: string): number {
  return props.config.objectValues[objId] ?? 0
}

const leftTotal = computed(() =>
  props.config.leftFixed.reduce((sum, obj) => sum + objectValue(obj.id), 0),
)

const rightTotal = computed(() =>
  rightPlacements.reduce(
    (sum, id) => sum + (id ? objectValue(id) : 0),
    0,
  ),
)

const statusText = computed(() =>
  t('learning.challenge.placedCount', {
    placed: placedIds.value.size,
    total: props.config.rightSlots,
  }),
)

const showTutorSuggestion = computed(() =>
  attemptCount.value >= 2 && !completed.value,
)

const fulcrumClass = computed(() => {
  if (!hasAnyPlacement.value) return ''
  if (leftTotal.value === rightTotal.value) return 'challenge-fulcrum--balanced'
  if (leftTotal.value > rightTotal.value) return 'challenge-fulcrum--left-heavy'
  return 'challenge-fulcrum--right-heavy'
})

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

/** Tap a slot: if filled → return to pool; if empty + object selected → place. */
function handleSlotClick(idx: number) {
  if (completed.value) return

  if (rightPlacements[idx] !== null) {
    rightPlacements[idx] = null
    return
  }

  if (selectedObjectId.value) {
    rightPlacements[idx] = selectedObjectId.value
    selectedObjectId.value = null
  }
}

function onContinue() {
  clearState()
  emit('complete')
}

function checkAnswer() {
  attemptCount.value++
  const result = evaluateBalance()
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

/** Both sides must have equal total weight. */
function evaluateBalance(): { isCorrect: boolean; hint: string } {
  const left = leftTotal.value
  const right = rightTotal.value

  if (left === right && right > 0) {
    return { isCorrect: true, hint: '' }
  }

  if (left > right) {
    return { isCorrect: false, hint: t('learning.challenge.hintTooLight') }
  }
  return { isCorrect: false, hint: t('learning.challenge.hintTooHeavy') }
}
</script>

<style scoped>
/* Balance scale */
.challenge-balance {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 12px;
  padding: 12px;
  background: var(--continent-canvas-bg);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-hairline);
}

.challenge-pan {
  flex: 1;
  min-width: 100px;
  padding: 12px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md);
  border: 2px solid var(--color-hairline);
  text-align: center;
}

.challenge-pan__label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-muted);
  margin-bottom: 8px;
}

.challenge-pan__items,
.challenge-pan__slots {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
  min-height: 44px;
}

.challenge-pan__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.challenge-pan__icon {
  font-size: 24px;
  line-height: 1;
}

.challenge-pan__value {
  font-family: Inter, sans-serif;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-body);
}

.challenge-pan__total {
  margin-top: 8px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}

/* Right pan slots */
.challenge-pan__slot {
  width: 48px;
  height: 48px;
  border: 2px dashed var(--color-hairline);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.challenge-pan__slot--filled {
  border-style: solid;
  border-color: var(--color-brand-mint);
  background: rgba(var(--color-brand-mint-rgb), 0.08);
}

.challenge-pan__slot--active {
  border-color: var(--color-brand-ochre);
  background: rgba(var(--color-brand-ochre-rgb), 0.08);
}

.challenge-pan__slot-placeholder {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted);
}

/* Fulcrum */
.challenge-fulcrum {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
  transition: transform 0.3s ease;
}

.challenge-fulcrum__icon {
  font-size: 32px;
}

.challenge-fulcrum--balanced {
  transform: rotate(0deg);
}

.challenge-fulcrum--left-heavy {
  transform: rotate(-10deg);
}

.challenge-fulcrum--right-heavy {
  transform: rotate(10deg);
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
  .challenge-fulcrum,
  .challenge-pan__slot,
  .challenge-object {
    transition: none;
  }
}
</style>
