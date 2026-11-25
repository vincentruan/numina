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
    <!-- Drag-to-reorder sequence slots -->
    <div ref="sequenceRef" class="challenge-sequence">
      <div
        v-for="(objId, idx) in sequence"
        :key="idx"
        class="challenge-slot"
        :class="{
          'challenge-slot--filled': objId !== null,
          'challenge-slot--dragging': dragState.fromIndex === idx,
          'challenge-slot--drop-target': dragState.fromIndex !== null && dragState.fromIndex !== idx && hoverIndex === idx,
        }"
        @pointerdown.stop="startDrag($event, idx)"
      >
        <span v-if="objId !== null" class="challenge-slot__icon">
          {{ getObjectIcon(objId) }}
        </span>
        <span v-else class="challenge-slot__placeholder">{{ idx + 1 }}</span>
      </div>
    </div>

    <!-- Object pool — remaining items (draggable) -->
    <div class="challenge-pool">
      <div
        v-for="obj in remainingObjects"
        :key="obj.id"
        class="challenge-object"
        :class="{ 'challenge-object--dragging': poolDragState.objectId === obj.id }"
        :style="poolDragState.objectId === obj.id ? poolDragStyle : {}"
        @pointerdown.stop="startPoolDrag($event, obj.id)"
      >
        <span v-if="obj.icon" class="challenge-object__icon">{{ obj.icon }}</span>
        <span class="challenge-object__label">{{ localizedLabel(obj.label, obj.labelZh) }}</span>
      </div>
    </div>
  </ChallengeShell>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import type { OrderChallenge, ChallengeVerdict } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { playClickPop, resumeAudio } from '@/audio/sfx'
import { triggerSuccessFeedback, triggerErrorFeedback } from './feedback'

defineOptions({ name: 'OrderChallenge' })

const props = defineProps<{ config: OrderChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t, locale } = useI18n()

// ── Refs ──
const containerRef = ref<HTMLElement | null>(null)
const sequenceRef = ref<HTMLElement | null>(null)

// ── Interaction state ──
const sequence = reactive<(string | null)[]>(props.config.correctOrder.map(() => null))
const completed = ref(false)
const feedbackMessage = ref('')
const feedbackVerdict = ref<ChallengeVerdict | null>(null)
const attemptCount = ref(0)
const hoverIndex = ref<number | null>(null)

// ── Drag state (reorder within sequence) ──
interface DragState {
  fromIndex: number | null
  startX: number
  startY: number
  currentX: number
  currentY: number
}
const dragState = reactive<DragState>({ fromIndex: null, startX: 0, startY: 0, currentX: 0, currentY: 0 })

// ── Pool drag state (drag from pool to slot) ──
interface PoolDragState {
  objectId: string | null
  startX: number
  startY: number
  currentX: number
  currentY: number
}
const poolDragState = reactive<PoolDragState>({ objectId: null, startX: 0, startY: 0, currentX: 0, currentY: 0 })
const poolDragStyle = computed(() => {
  if (!poolDragState.objectId) return {}
  const dx = poolDragState.currentX - poolDragState.startX
  const dy = poolDragState.currentY - poolDragState.startY
  return { transform: `translate(${dx}px, ${dy}px) scale(1.08)`, zIndex: 100, position: 'relative' as const, touchAction: 'none' as const }
})

// ── Reorder drag ──
function startDrag(e: PointerEvent, idx: number) {
  if (completed.value || sequence[idx] === null) return
  resumeAudio()
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture?.(e.pointerId)
  dragState.fromIndex = idx
  dragState.startX = e.clientX
  dragState.startY = e.clientY
  dragState.currentX = e.clientX
  dragState.currentY = e.clientY
  playClickPop()
}

function startPoolDrag(e: PointerEvent, objId: string) {
  if (completed.value) return
  resumeAudio()
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture?.(e.pointerId)
  poolDragState.objectId = objId
  poolDragState.startX = e.clientX
  poolDragState.startY = e.clientY
  poolDragState.currentX = e.clientX
  poolDragState.currentY = e.clientY
  playClickPop()
}

function onPointerMove(e: PointerEvent) {
  if (dragState.fromIndex !== null) {
    dragState.currentX = e.clientX
    dragState.currentY = e.clientY
    // Detect which slot we're hovering
    const slots = sequenceRef.value?.querySelectorAll('.challenge-slot')
    if (slots) {
      hoverIndex.value = null
      slots.forEach((slot, i) => {
        const rect = slot.getBoundingClientRect()
        if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
          hoverIndex.value = i
        }
      })
    }
  }
  if (poolDragState.objectId) {
    poolDragState.currentX = e.clientX
    poolDragState.currentY = e.clientY
  }
}

function onPointerUp(e: PointerEvent) {
  // Handle reorder drop
  if (dragState.fromIndex !== null) {
    if (hoverIndex.value !== null && hoverIndex.value !== dragState.fromIndex && sequence[hoverIndex.value] === null) {
      // Move to empty slot
      sequence[hoverIndex.value] = sequence[dragState.fromIndex]
      sequence[dragState.fromIndex] = null
      playClickPop()
    } else if (hoverIndex.value !== null && hoverIndex.value !== dragState.fromIndex) {
      // Swap with occupied slot
      const temp = sequence[hoverIndex.value]
      sequence[hoverIndex.value] = sequence[dragState.fromIndex]
      sequence[dragState.fromIndex] = temp
      playClickPop()
    }
    dragState.fromIndex = null
    hoverIndex.value = null
  }
  // Handle pool drag drop
  if (poolDragState.objectId) {
    const slots = sequenceRef.value?.querySelectorAll('.challenge-slot')
    if (slots) {
      for (let i = 0; i < slots.length; i++) {
        const rect = slots[i].getBoundingClientRect()
        if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom && sequence[i] === null) {
          sequence[i] = poolDragState.objectId
          playClickPop()
          break
        }
      }
    }
    poolDragState.objectId = null
  }
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
interface PersistedState { sequence: (string | null)[]; attemptCount: number; completed: boolean; feedbackMessage: string; feedbackVerdict: ChallengeVerdict | null }
function restoreState() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw) as PersistedState
    const savedSeq = saved.sequence ?? []
    for (let i = 0; i < props.config.correctOrder.length; i++) {
      const objId = savedSeq[i] ?? null
      sequence[i] = objId && props.config.objects.some((o) => o.id === objId) ? objId : null
    }
    attemptCount.value = saved.attemptCount ?? 0
    completed.value = saved.completed ?? false
    feedbackMessage.value = saved.feedbackMessage ?? ''
    feedbackVerdict.value = saved.feedbackVerdict ?? null
  } catch { /* ignore */ }
}
function clearState() { try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ } }
restoreState()
watch([sequence, attemptCount, completed, feedbackMessage, feedbackVerdict], () => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ sequence: [...sequence], attemptCount: attemptCount.value, completed: completed.value, feedbackMessage: feedbackMessage.value, feedbackVerdict: feedbackVerdict.value }))
  } catch { /* ignore */ }
}, { deep: true })

// ── Computed ──
const isZh = computed(() => locale.value.startsWith('zh'))
const placedIds = computed(() => new Set(sequence.filter((id): id is string => id !== null)))
const remainingObjects = computed(() => props.config.objects.filter((o) => !placedIds.value.has(o.id)))
const hasAnyPlacement = computed(() => placedIds.value.size > 0)
const statusText = computed(() => t('learning.challenge.placedCount', { placed: placedIds.value.size, total: props.config.objects.length }))
const showTutorSuggestion = computed(() => attemptCount.value >= 2 && !completed.value)
const allowEarlyContinue = computed(() => attemptCount.value >= 2 && !completed.value)

// ── Methods ──
function localizedLabel(en: string, zh?: string): string { return isZh.value && zh ? zh : en }
function getObjectIcon(objId: string): string { return props.config.objects.find((o) => o.id === objId)?.icon ?? '●' }
function onContinue() { clearState(); emit('complete') }
function checkAnswer() {
  attemptCount.value++
  const result = evaluateOrder()
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
function evaluateOrder(): { isCorrect: boolean; hint: string } {
  if (!sequence.every((id) => id !== null)) return { isCorrect: false, hint: t('learning.challenge.hintOrderIncomplete') }
  for (let i = 0; i < props.config.correctOrder.length; i++) {
    if (sequence[i] !== props.config.correctOrder[i]) return { isCorrect: false, hint: t('learning.challenge.hintOrderWrong') }
  }
  return { isCorrect: true, hint: '' }
}
</script>

<style scoped>
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
  cursor: grab;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
  position: relative;
  touch-action: none;
  user-select: none;
}
.challenge-slot--filled { border-style: solid; border-color: var(--color-brand-mint); background: rgba(var(--color-brand-mint-rgb), 0.08); }
.challenge-slot--dragging { opacity: 0.4; }
.challenge-slot--drop-target { border-color: var(--color-brand-ochre); background: rgba(var(--color-brand-ochre-rgb), 0.08); transform: scale(1.05); }
.challenge-slot__icon { font-size: 28px; line-height: 1; }
.challenge-slot__placeholder { font-family: Inter, sans-serif; font-size: 14px; font-weight: 600; color: var(--color-muted); }
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
.challenge-object--dragging { border-color: var(--color-brand-ochre); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); cursor: grabbing; }
.challenge-object__icon { font-size: 24px; line-height: 1; }
.challenge-object__label { font-family: Inter, sans-serif; font-size: 11px; color: var(--color-body); text-align: center; max-width: 60px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (prefers-reduced-motion: reduce) {
  .challenge-slot, .challenge-object { transition: none; }
}
</style>
