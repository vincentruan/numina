<template>
  <div ref="containerRef">
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
    <!-- Drag-to-sort object pool -->
    <div ref="poolRef" class="challenge-pool">
      <div
        v-for="obj in poolObjects"
        :key="obj.id"
        ref="objectRefs"
        class="challenge-object"
        :class="{
          'challenge-object--dragging': dragState.objectId === obj.id,
          'challenge-object--snap': snapState.objectId === obj.id,
        }"
        :style="dragState.objectId === obj.id ? dragStyle : {}"
        @pointerdown.stop="startDrag($event, obj.id)"
      >
        <span v-if="obj.icon" class="challenge-object__icon">{{ obj.icon }}</span>
        <span class="challenge-object__label">{{ localizedLabel(obj.label, obj.labelZh) }}</span>
      </div>
    </div>

    <!-- Zone drop targets with hover highlight -->
    <div class="challenge-zones">
      <div
        v-for="zone in config.zones"
        :key="zone.id"
        class="challenge-zone"
        :data-zone-id="zone.id"
        :class="{
          'challenge-zone--hover': hoverZoneId === zone.id,
          'challenge-zone--correct': correctZoneId === zone.id,
        }"
        @pointerenter="hoverZoneId = zone.id"
        @pointerleave="hoverZoneId = null"
      >
        <div class="challenge-zone__label">{{ localizedLabel(zone.label, zone.labelZh) }}</div>
        <div class="challenge-zone__items">
          <span
            v-for="objId in placements[zone.id]"
            :key="objId"
            class="challenge-zone__placed"
            @click="returnToPool(objId, zone.id)"
          >
            {{ getObjectIcon(objId) }}
          </span>
        </div>
        <div class="challenge-zone__count">{{ placements[zone.id].length }}</div>
      </div>
    </div>
  </ChallengeShell>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ClassifyChallenge, ChallengeObject, ChallengeVerdict } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { playClickPop, resumeAudio } from '@/audio/sfx'
import { triggerSuccessFeedback, triggerErrorFeedback } from './feedback'

defineOptions({ name: 'ClassifyChallenge' })

const props = defineProps<{ config: ClassifyChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t, locale } = useI18n()

// ── Refs ──
const containerRef = ref<HTMLElement | null>(null)
const poolRef = ref<HTMLElement | null>(null)
const objectRefs = ref<HTMLElement[]>([])

// ── Interaction state ──
const placements = reactive<Record<string, string[]>>({})
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackVerdict = ref<ChallengeVerdict | null>(null)
const attemptCount = ref(0)
const hoverZoneId = ref<string | null>(null)
const correctZoneId = ref<string | null>(null)

for (const zone of props.config.zones) {
  placements[zone.id] = []
}

// ── Drag state ──
interface DragState {
  objectId: string | null
  startX: number
  startY: number
  currentX: number
  currentY: number
  el: HTMLElement | null
}
const dragState = reactive<DragState>({ objectId: null, startX: 0, startY: 0, currentX: 0, currentY: 0, el: null })
const snapState = reactive<{ objectId: string | null }>({ objectId: null })

const dragStyle = computed(() => {
  if (!dragState.objectId) return {}
  const dx = dragState.currentX - dragState.startX
  const dy = dragState.currentY - dragState.startY
  return {
    transform: `translate(${dx}px, ${dy}px) scale(1.08)`,
    zIndex: 100,
    position: 'relative' as const,
    touchAction: 'none' as const,
  }
})

// ── Drag handlers ──
function startDrag(e: PointerEvent, objId: string) {
  if (completed.value) return
  resumeAudio()
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture?.(e.pointerId)
  dragState.objectId = objId
  dragState.startX = e.clientX
  dragState.startY = e.clientY
  dragState.currentX = e.clientX
  dragState.currentY = e.clientY
  dragState.el = el
  playClickPop()
}

function onPointerMove(e: PointerEvent) {
  if (!dragState.objectId) return
  dragState.currentX = e.clientX
  dragState.currentY = e.clientY
}

function onPointerUp(e: PointerEvent) {
  if (!dragState.objectId) return
  const objId = dragState.objectId
  // Find drop target zone via elementFromPoint
  const dropEl = document.elementFromPoint(e.clientX, e.clientY)
  const zoneEl = dropEl?.closest('[data-zone-id]') as HTMLElement | null
  const zoneId = zoneEl?.dataset.zoneId

  if (zoneId && placements[zoneId] !== undefined) {
    placeInZone(objId, zoneId)
  }

  // Reset drag
  dragState.objectId = null
  dragState.el = null
  hoverZoneId.value = null
}

onMounted(() => {
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})

// ── Session persistence ──
const STORAGE_KEY = `numina:challenge:${props.config.id}`
interface PersistedState {
  placements: Record<string, string[]>
  attemptCount: number
  completed: boolean
  feedbackMessage: string
  feedbackVerdict: ChallengeVerdict | null
}
function restoreState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as PersistedState
    for (const zone of props.config.zones) {
      const savedIds = saved.placements?.[zone.id] ?? []
      placements[zone.id] = savedIds.filter((id) => props.config.objects.some((o) => o.id === id))
    }
    attemptCount.value = saved.attemptCount ?? 0
    completed.value = saved.completed ?? false
    feedbackMessage.value = saved.feedbackMessage ?? ''
    feedbackVerdict.value = saved.feedbackVerdict ?? null
  } catch { /* Storage unavailable */ }
}
function clearState() {
  try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
}
restoreState()
watch([placements, attemptCount, completed, feedbackMessage, feedbackVerdict], () => {
  try {
    const state: PersistedState = {
      placements: Object.fromEntries(props.config.zones.map((z) => [z.id, [...(placements[z.id] ?? [])]])),
      attemptCount: attemptCount.value, completed: completed.value,
      feedbackMessage: feedbackMessage.value, feedbackVerdict: feedbackVerdict.value,
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch { /* ignore */ }
}, { deep: true })

// ── Computed ──
const isZh = computed(() => locale.value.startsWith('zh'))
const placementSummary = computed(() => {
  const allPlaced = Object.values(placements).flat()
  return { placedIds: new Set(allPlaced), totalPlaced: allPlaced.length }
})
const poolObjects = computed(() => props.config.objects.filter((o) => !placementSummary.value.placedIds.has(o.id)))
const hasAnyPlacement = computed(() => placementSummary.value.totalPlaced > 0)
const statusText = computed(() => t('learning.challenge.placedCount', { placed: placementSummary.value.totalPlaced, total: props.config.objects.length }))
const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)
const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)

// ── Interaction methods ──
function localizedLabel(en: string, zh?: string): string { return isZh.value && zh ? zh : en }
function getObjectIcon(objId: string): string { return props.config.objects.find((o) => o.id === objId)?.icon ?? '●' }

function placeInZone(objId: string, zoneId: string) {
  if (placementSummary.value.placedIds.has(objId)) return
  if (!placements[zoneId]) placements[zoneId] = []
  placements[zoneId].push(objId)
  playClickPop()
  // Snap animation
  snapState.objectId = objId
  setTimeout(() => { snapState.objectId = null }, 300)
}

function returnToPool(objId: string, zoneId: string) {
  if (completed.value) return
  const idx = placements[zoneId]?.indexOf(objId) ?? -1
  if (idx >= 0) placements[zoneId].splice(idx, 1)
}

function onContinue() { clearState(); emit('complete') }

function checkAnswer() {
  attemptCount.value++
  const result = evaluateClassify()
  feedbackVerdict.value = result.isCorrect ? 'correct' : 'wrong'
  if (result.isCorrect) {
    completed.value = true
    feedbackMessage.value = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
    if (containerRef.value) triggerSuccessFeedback(containerRef.value)
  } else {
    feedbackMessage.value = result.hint
    if (containerRef.value) triggerErrorFeedback(containerRef.value)
  }
}

function evaluateClassify(): { isCorrect: boolean; hint: string } {
  for (const [zoneId, objIds] of Object.entries(placements)) {
    for (const objId of objIds) {
      if (props.config.correctMapping[objId] !== zoneId) {
        const obj = props.config.objects.find((o: ChallengeObject) => o.id === objId)
        const label = obj ? localizedLabel(obj.label, obj.labelZh) : objId
        return { isCorrect: false, hint: t('learning.challenge.hintMisplaced', { label }) }
      }
    }
  }
  if (placementSummary.value.totalPlaced === props.config.objects.length) {
    return { isCorrect: true, hint: '' }
  }
  return { isCorrect: false, hint: t('learning.challenge.hintPlaceAll') }
}
</script>

<style scoped>
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
  min-width: 56px;
  min-height: 56px;
  padding: 8px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  cursor: grab;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
  touch-action: none;
  user-select: none;
}
.challenge-object--dragging {
  border-color: var(--color-brand-ochre);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  cursor: grabbing;
}
.challenge-object--snap {
  animation: classify-snap 300ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.challenge-object__icon { font-size: 24px; line-height: 1; }
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
.challenge-zones { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
.challenge-zone {
  flex: 1;
  min-width: 80px;
  min-height: 80px;
  padding: 10px;
  border: 2px dashed var(--color-hairline);
  border-radius: var(--radius-lg);
  background: var(--challenge-zone-bg);
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.challenge-zone--hover {
  border-color: var(--color-brand-ochre);
  background: rgba(var(--color-brand-ochre-rgb), 0.08);
  transform: scale(1.02);
}
.challenge-zone--correct {
  border-color: var(--color-brand-mint);
  background: var(--challenge-zone-active);
  border-style: solid;
}
.challenge-zone__label { font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; color: var(--color-ink); }
.challenge-zone__items { display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; }
.challenge-zone__placed { font-size: 20px; cursor: pointer; min-width: 56px; min-height: 56px; display: flex; align-items: center; justify-content: center; }
.challenge-zone__count { font-family: Inter, sans-serif; font-size: 12px; color: var(--color-muted); }
@keyframes classify-snap {
  0% { transform: scale(1.15); }
  100% { transform: scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  .challenge-object, .challenge-zone { transition: none; }
  .challenge-object--snap { animation: none; }
}
</style>
