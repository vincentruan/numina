<template>
  <div v-if="config" class="manipulate-challenge">
    <!-- Scenario text -->
    <div class="challenge-scenario">
      <p class="challenge-scenario__text">{{ localizedScenario }}</p>
    </div>

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

    <!-- Feedback bar -->
    <div class="challenge-feedback">
      <div v-if="feedbackMessage" class="challenge-feedback__message" :class="feedbackClass">
        {{ feedbackMessage }}
      </div>
      <div v-else class="challenge-feedback__status">
        {{ statusText }}
      </div>
      <button
        v-if="!completed"
        class="challenge-check-btn"
        :disabled="!hasAnyPlacement"
        @click="checkAnswer"
      >
        {{ t('learning.challenge.check') }}
      </button>
      <button
        v-else
        class="challenge-next-btn"
        @click="$emit('complete')"
      >
        {{ t('learning.challenge.continue') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ChallengeConfig, ChallengeObject } from '@/types/learning-challenge'

const props = defineProps<{
  config: ChallengeConfig
}>()

defineEmits<{
  complete: []
}>()

const { t, locale } = useI18n()

// ── Interaction state ──

const selectedObjectId = ref<string | null>(null)
/** zoneId → objectIds placed in that zone */
const placements = reactive<Record<string, string[]>>({})
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackIsCorrect = ref(false)

// Initialize placements for all zones
for (const zone of props.config.zones) {
  placements[zone.id] = []
}

// ── Computed ──

const isZh = computed(() => locale.value.startsWith('zh'))

const localizedScenario = computed(() =>
  isZh.value ? props.config.scenarioZh : props.config.scenario,
)

/** Consolidated placement summary — single traversal instead of 3 separate .flat() calls. */
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

const feedbackClass = computed(() =>
  feedbackIsCorrect.value ? 'challenge-feedback__message--correct' : 'challenge-feedback__message--wrong',
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
  if (!placements[zoneId]) placements[zoneId] = []
  placements[zoneId].push(objId)
  selectedObjectId.value = null
}

function returnToPool(objId: string, zoneId: string) {
  if (completed.value) return
  const idx = placements[zoneId]?.indexOf(objId) ?? -1
  if (idx >= 0) placements[zoneId].splice(idx, 1)
}

function checkAnswer() {
  const result = evaluate()
  feedbackIsCorrect.value = result.isCorrect
  if (result.isCorrect) {
    completed.value = true
    feedbackMessage.value = isZh.value
      ? props.config.discoveryMessageZh
      : props.config.discoveryMessage
  } else {
    feedbackMessage.value = isZh.value ? result.hintZh : result.hint
  }
}

/**
 * Evaluate the current placement against the challenge rule.
 * P1 supports 'equal_distribution' — each zone must have the same count.
 */
function evaluate(): { isCorrect: boolean; hint: string; hintZh: string } {
  if (props.config.type === 'distribute') {
    return evaluateDistribute(props.config, placements)
  }
  if (props.config.type === 'classify') {
    return evaluateClassify(props.config, placements)
  }
  return { isCorrect: false, hint: 'Try again', hintZh: '再试一次' }
}

function evaluateDistribute(
  config: ChallengeConfig,
  currentPlacements: Record<string, string[]>,
): { isCorrect: boolean; hint: string; hintZh: string } {
  if (config.type !== 'distribute') return { isCorrect: false, hint: '', hintZh: '' }
  const zoneCounts = config.zones.map((z) => (currentPlacements[z.id] ?? []).length)
  const allEqual = zoneCounts.every((c) => c === zoneCounts[0]) && zoneCounts[0] > 0
  const allPlaced = zoneCounts.reduce((a, b) => a + b, 0) === config.objects.length

  if (allEqual && allPlaced) {
    return { isCorrect: true, hint: '', hintZh: '' }
  }

  // Generate a helpful hint
  const maxCount = Math.max(...zoneCounts)
  const minCount = Math.min(...zoneCounts)
  if (maxCount - minCount > 1) {
    return {
      isCorrect: false,
      hint: t('learning.challenge.hintUnequal'),
      hintZh: t('learning.challenge.hintUnequal'),
    }
  }
  return {
    isCorrect: false,
    hint: t('learning.challenge.hintAlmost'),
    hintZh: t('learning.challenge.hintAlmost'),
  }
}

function evaluateClassify(
  config: ChallengeConfig,
  currentPlacements: Record<string, string[]>,
): { isCorrect: boolean; hint: string; hintZh: string } {
  if (config.type !== 'classify') return { isCorrect: false, hint: '', hintZh: '' }
  for (const [zoneId, objIds] of Object.entries(currentPlacements)) {
    for (const objId of objIds) {
      if (config.correctMapping[objId] !== zoneId) {
        const obj = config.objects.find((o: ChallengeObject) => o.id === objId)
        const label = obj ? localizedLabel(obj.label, obj.labelZh) : objId
        return {
          isCorrect: false,
          hint: t('learning.challenge.hintMisplaced', { label }),
          hintZh: t('learning.challenge.hintMisplaced', { label }),
        }
      }
    }
  }
  const allPlaced = placementSummary.value.totalPlaced === config.objects.length
  if (allPlaced) {
    return { isCorrect: true, hint: '', hintZh: '' }
  }
  return { isCorrect: false, hint: t('learning.challenge.hintPlaceAll'), hintZh: t('learning.challenge.hintPlaceAll') }
}
</script>

<style scoped>
.manipulate-challenge {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

/* Scenario */
.challenge-scenario {
  padding: 12px 16px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
}

.challenge-scenario__text {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0;
  line-height: 1.5;
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

/* Feedback bar */
.challenge-feedback {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.challenge-feedback__message {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  text-align: center;
  width: 100%;
}

.challenge-feedback__message--correct {
  background: rgba(var(--color-brand-mint-rgb), 0.2);
  color: var(--color-ink);
}

.challenge-feedback__message--wrong {
  background: rgba(var(--color-brand-coral-rgb), 0.12);
  color: var(--color-ink);
}

.challenge-feedback__status {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-muted);
}

.challenge-check-btn,
.challenge-next-btn {
  min-height: 48px;
  min-width: 120px;
  padding: 12px 24px;
  border: none;
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.challenge-check-btn {
  background: var(--color-primary);
  color: var(--color-on-primary);
}

.challenge-check-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.challenge-next-btn {
  background: var(--color-brand-mint);
  color: var(--color-ink);
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .challenge-object,
  .challenge-zone {
    transition: none;
  }
}
</style>
