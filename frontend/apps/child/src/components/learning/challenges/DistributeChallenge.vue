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
    <!-- Object pool — tappable items -->
    <div class="challenge-pool">
      <button
        v-for="obj in poolObjects"
        :key="obj.id"
        class="challenge-object"
        :class="{ 'challenge-object--selected': selectedObjectId === obj.id }"
        @click="selectObject(obj.id)"
      >
        <span v-if="obj.icon" class="challenge-object__icon">{{ obj.icon }}</span>
        <span class="challenge-object__label">{{ localizedLabel(obj.label, obj.labelZh) }}</span>
      </button>
    </div>

    <!-- Zone area — tappable drop targets -->
    <div class="challenge-zones">
      <div
        v-for="zone in config.zones"
        :key="zone.id"
        class="challenge-zone"
        :class="{ 'challenge-zone--active': selectedObjectId && placements[zone.id].length }"
        @click="placeInZone(zone.id)"
      >
        <div class="challenge-zone__label">{{ localizedLabel(zone.label, zone.labelZh) }}</div>
        <div class="challenge-zone__items">
          <span
            v-for="objId in placements[zone.id]"
            :key="objId"
            class="challenge-zone__placed"
            @click.stop="returnToPool(objId, zone.id)"
          >
            {{ getObjectIcon(objId) }}
          </span>
        </div>
        <div class="challenge-zone__count">
          {{ placements[zone.id].length }}
        </div>
      </div>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DistributeChallenge } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'

defineOptions({ name: 'DistributeChallenge' })

const props = defineProps<{
  config: DistributeChallenge
}>()

const emit = defineEmits<{
  complete: []
  requestTutor: []
}>()

const { t, locale } = useI18n()

// ── Interaction state ──

const selectedObjectId = ref<string | null>(null)
/** zoneId → objectIds placed in that zone */
const placements = reactive<Record<string, string[]>>({})
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackIsCorrect = ref(false)
const attemptCount = ref(0)

// Initialize placements for all zones
for (const zone of props.config.zones) {
  placements[zone.id] = []
}

// ── Session persistence (AE5) ──

const STORAGE_KEY = `numina:challenge:${props.config.id}`

interface PersistedState {
  placements: Record<string, string[]>
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
    for (const zone of props.config.zones) {
      const savedIds = saved.placements?.[zone.id] ?? []
      placements[zone.id] = savedIds.filter((id) =>
        props.config.objects.some((o) => o.id === id),
      )
    }
    attemptCount.value = saved.attemptCount ?? 0
    completed.value = saved.completed ?? false
    feedbackMessage.value = saved.feedbackMessage ?? ''
    feedbackIsCorrect.value = saved.feedbackIsCorrect ?? false
  } catch {
    // Storage unavailable — start fresh
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
  [placements, attemptCount, completed, feedbackMessage, feedbackIsCorrect],
  () => {
    try {
      const state: PersistedState = {
        placements: Object.fromEntries(
          props.config.zones.map((z) => [z.id, [...(placements[z.id] ?? [])]]),
        ),
        attemptCount: attemptCount.value,
        completed: completed.value,
        feedbackMessage: feedbackMessage.value,
        feedbackIsCorrect: feedbackIsCorrect.value,
      }
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
      // Storage unavailable — persistence is best-effort
    }
  },
  { deep: true },
)

// ── Computed ──

const isZh = computed(() => locale.value.startsWith('zh'))

/** Consolidated placement summary — single traversal. */
const placementSummary = computed(() => {
  const allPlaced = Object.values(placements).flat()
  return {
    placedIds: new Set(allPlaced),
    totalPlaced: allPlaced.length,
  }
})

/** Objects not yet placed in any zone. */
const poolObjects = computed(() =>
  props.config.objects.filter((o) => !placementSummary.value.placedIds.has(o.id)),
)

const hasAnyPlacement = computed(() => placementSummary.value.totalPlaced > 0)

const statusText = computed(() =>
  t('learning.challenge.placedCount', {
    placed: placementSummary.value.totalPlaced,
    total: props.config.objects.length,
  }),
)

/** After 2 failed attempts, suggest asking the AI tutor (F3). */
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

function placeInZone(zoneId: string) {
  if (!selectedObjectId.value || completed.value) return
  const objId = selectedObjectId.value
  // An object lives in exactly one zone — a retained selection must not be able
  // to push the same object into a second zone and inflate the placed count.
  if (placementSummary.value.placedIds.has(objId)) {
    selectedObjectId.value = null
    return
  }
  if (!placements[zoneId]) placements[zoneId] = []
  placements[zoneId].push(objId)
  selectedObjectId.value = null
}

function returnToPool(objId: string, zoneId: string) {
  if (completed.value) return
  const idx = placements[zoneId]?.indexOf(objId) ?? -1
  if (idx >= 0) placements[zoneId].splice(idx, 1)
}

/** Challenge finished — drop the saved state so a re-entry starts fresh. */
function onContinue() {
  clearState()
  emit('complete')
}

function checkAnswer() {
  attemptCount.value++
  const result = evaluateDistribute()
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

/** Each zone must have the same count and all objects must be placed. */
function evaluateDistribute(): { isCorrect: boolean; hint: string } {
  const zoneCounts = props.config.zones.map((z) => (placements[z.id] ?? []).length)
  const allEqual = zoneCounts.every((c) => c === zoneCounts[0]) && zoneCounts[0] > 0
  const allPlaced = zoneCounts.reduce((a, b) => a + b, 0) === props.config.objects.length

  if (allEqual && allPlaced) {
    return { isCorrect: true, hint: '' }
  }

  const maxCount = Math.max(...zoneCounts)
  const minCount = Math.min(...zoneCounts)
  if (maxCount - minCount > 1) {
    return { isCorrect: false, hint: t('learning.challenge.hintUnequal') }
  }
  return { isCorrect: false, hint: t('learning.challenge.hintAlmost') }
}
</script>

<style scoped>
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

/* Zones */
.challenge-zones {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.challenge-zone {
  flex: 1;
  min-width: 80px;
  min-height: 80px;
  padding: 10px;
  border: 2px dashed var(--color-hairline);
  border-radius: var(--radius-lg);
  background: var(--challenge-zone-bg);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.challenge-zone--active {
  border-color: var(--color-brand-mint);
  background: var(--challenge-zone-active);
  border-style: solid;
}

.challenge-zone__label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
}

.challenge-zone__items {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
}

.challenge-zone__placed {
  font-size: 20px;
  cursor: pointer;
  min-width: 28px;
  min-height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.challenge-zone__count {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .challenge-object,
  .challenge-zone {
    transition: none;
  }
}
</style>
