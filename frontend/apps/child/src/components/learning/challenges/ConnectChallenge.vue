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
    <!-- Board with SVG connection lines -->
    <div ref="boardRef" class="connect-board">
      <!-- SVG overlay for connection lines -->
      <svg v-if="boardRef" class="connect-svg" :viewBox="svgViewBox">
        <line
          v-for="(line, idx) in connectionLines"
          :key="idx"
          :x1="line.x1" :y1="line.y1"
          :x2="line.x2" :y2="line.y2"
          :class="['connect-line', { 'connect-line--correct': line.correct, 'connect-line--wrong': line.wrong }]"
        />
        <!-- Active drag line -->
        <line
          v-if="dragState.active"
          :x1="dragState.startX" :y1="dragState.startY"
          :x2="dragState.currentX" :y2="dragState.currentY"
          class="connect-line connect-line--active"
        />
      </svg>

      <!-- Left column -->
      <div class="connect-column">
        <button
          v-for="item in config.leftItems"
          :key="item.id"
          ref="leftItemRefs"
          :data-id="item.id"
          class="connect-item"
          :class="{
            'connect-item--paired': pairs[item.id] !== undefined,
            'connect-item--dragging': dragState.leftId === item.id,
          }"
          :disabled="completed"
          @pointerdown.stop="startDrag($event, item.id, 'left')"
        >
          <span class="connect-item__label">{{ localizedLabel(item.label, item.labelZh) }}</span>
          <span v-if="pairs[item.id]" class="connect-item__partner">→ {{ pairLabel(pairs[item.id]!) }}</span>
        </button>
      </div>

      <!-- Right column -->
      <div class="connect-column">
        <button
          v-for="item in config.rightItems"
          :key="item.id"
          ref="rightItemRefs"
          :data-id="item.id"
          class="connect-item"
          :class="{
            'connect-item--paired': pairedRightIds.has(item.id),
            'connect-item--drop-target': dragState.active && dragHoverRightId === item.id,
          }"
          :disabled="completed"
        >
          <span class="connect-item__label">{{ localizedLabel(item.label, item.labelZh) }}</span>
          <span v-if="pairedRightIds.has(item.id)" class="connect-item__partner">↩ {{ leftLabelForRight(item.id) }}</span>
        </button>
      </div>
    </div>
  </ChallengeShell>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ChallengeJudgement, ConnectChallenge } from '@/types/learning-challenge'
import ChallengeShell from './ChallengeShell.vue'
import { useChallengeState } from './useChallengeState'
import { playClickPop, playSuccessChime, playErrorDescend, resumeAudio } from '@/audio/sfx'

defineOptions({ name: 'ConnectChallenge' })

const props = defineProps<{ config: ConnectChallenge }>()
const emit = defineEmits<{ complete: []; requestTutor: [] }>()
const { t, locale } = useI18n()

const { state, completed, feedbackMessage, feedbackVerdict, showTutorSuggestion, allowEarlyContinue, applyJudgement, clearState } =
  useChallengeState<{ pairs: Record<string, string> }>({
    id: props.config.id,
    initial: { pairs: {} },
  })

const pairs = computed(() => state.pairs)
const isZh = computed(() => locale.value.startsWith('zh'))
const pairedRightIds = computed(() => new Set(Object.values(state.pairs)))
const hasAnyPlacement = computed(() => Object.keys(state.pairs).length > 0)
const statusText = computed(() => t('learning.challenge.placedCount', { placed: Object.keys(state.pairs).length, total: props.config.leftItems.length }))

// ── Refs ──
const boardRef = ref<HTMLElement | null>(null)
const leftItemRefs = ref<HTMLElement[]>([])
const rightItemRefs = ref<HTMLElement[]>([])

// ── SVG viewBox ──
const svgViewBox = computed(() => {
  if (!boardRef.value) return '0 0 400 300'
  return `0 0 ${boardRef.value.offsetWidth} ${boardRef.value.offsetHeight}`
})

// ── Drag state ──
interface DragState {
  active: boolean
  leftId: string | null
  startX: number
  startY: number
  currentX: number
  currentY: number
}
const dragState = reactive<DragState>({ active: false, leftId: null, startX: 0, startY: 0, currentX: 0, currentY: 0 })
const dragHoverRightId = ref<string | null>(null)

// ── Connection line positions ──
interface ConnLine { x1: number; y1: number; x2: number; y2: number; correct?: boolean; wrong?: boolean }
const connectionLines = computed<ConnLine[]>(() => {
  const lines: ConnLine[] = []
  const boardRect = boardRef.value?.getBoundingClientRect()
  if (!boardRect) return lines
  for (const [leftId, rightId] of Object.entries(state.pairs)) {
    const leftEl = leftItemRefs.value.find((el) => el?.dataset.id === leftId)
    const rightEl = rightItemRefs.value.find((el) => el?.dataset.id === rightId)
    if (!leftEl || !rightEl) continue
    const lr = leftEl.getBoundingClientRect()
    const rr = rightEl.getBoundingClientRect()
    lines.push({
      x1: lr.right - boardRect.left,
      y1: lr.top + lr.height / 2 - boardRect.top,
      x2: rr.left - boardRect.left,
      y2: rr.top + rr.height / 2 - boardRect.top,
      correct: props.config.correctPairs[leftId] === rightId,
    })
  }
  return lines
})

// ── Drag handlers ──
function getElementCenter(el: HTMLElement, boardRect: DOMRect) {
  const r = el.getBoundingClientRect()
  return { x: r.left + r.width / 2 - boardRect.left, y: r.top + r.height / 2 - boardRect.top }
}

function startDrag(e: PointerEvent, leftId: string, _side: 'left') {
  if (completed.value) return
  resumeAudio()
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture?.(e.pointerId)
  const boardRect = boardRef.value!.getBoundingClientRect()
  const elCenter = getElementCenter(e.currentTarget as HTMLElement, boardRect)
  dragState.active = true
  dragState.leftId = leftId
  dragState.startX = elCenter.x
  dragState.startY = elCenter.y
  dragState.currentX = e.clientX - boardRect.left
  dragState.currentY = e.clientY - boardRect.top
  playClickPop()
}

function onPointerMove(e: PointerEvent) {
  if (!dragState.active || !boardRef.value) return
  const boardRect = boardRef.value.getBoundingClientRect()
  dragState.currentX = e.clientX - boardRect.left
  dragState.currentY = e.clientY - boardRect.top
  // Detect hover over right items
  dragHoverRightId.value = null
  for (const el of rightItemRefs.value) {
    if (!el) continue
    const r = el.getBoundingClientRect()
    if (e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom) {
      dragHoverRightId.value = el.dataset.id ?? null
      break
    }
  }
}

function onPointerUp(e: PointerEvent) {
  if (!dragState.active) return
  if (dragHoverRightId.value && dragState.leftId) {
    const rightId = dragHoverRightId.value
    const leftId = dragState.leftId
    // Remove existing pair for this right item
    const existing = Object.entries(state.pairs).find(([, rid]) => rid === rightId)
    if (existing) delete state.pairs[existing[0]]
    // Create new pair
    state.pairs[leftId] = rightId
    // Check if correct
    const isCorrect = props.config.correctPairs[leftId] === rightId
    if (isCorrect) {
      playSuccessChime()
    } else {
      playErrorDescend()
    }
  }
  dragState.active = false
  dragState.leftId = null
  dragHoverRightId.value = null
}

onMounted(() => {
  window.addEventListener('pointermove', onPointerMove)
  window.addEventListener('pointerup', onPointerUp)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerup', onPointerUp)
})

// ── Helpers ──
function localizedLabel(en: string, zh?: string): string { return isZh.value && zh ? zh : en }
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

function judgeConnect(current: Record<string, string>, config: ConnectChallenge): ChallengeJudgement {
  const allPaired = config.leftItems.every((l) => current[l.id] !== undefined)
  if (!allPaired) return { verdict: 'wrong', hint: t('learning.challenge.connect.hintIncomplete') }
  const wrongPairs = config.leftItems.filter((l) => current[l.id] !== config.correctPairs[l.id]).length
  if (wrongPairs === 0) return { verdict: 'correct', hint: '' }
  const isClose = wrongPairs === 1
  return { verdict: isClose ? 'close' : 'wrong', hint: isClose ? t('learning.challenge.connect.hintClose') : t('learning.challenge.connect.hintWrong') }
}

function checkAnswer() {
  const judgement = judgeConnect(state.pairs, props.config)
  const success = isZh.value ? props.config.discoveryMessageZh : props.config.discoveryMessage
  applyJudgement(judgement, success)
  if (judgement.verdict === 'correct') playSuccessChime()
  else playErrorDescend()
}

function onContinue() { clearState(); emit('complete') }
</script>

<style scoped>
.connect-board { position: relative; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.connect-svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; }
.connect-column { display: flex; flex-direction: column; gap: 8px; position: relative; z-index: 2; }
.connect-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-height: 56px;
  padding: 10px 12px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  cursor: grab;
  text-align: left;
  transition: border-color 0.15s, background 0.15s, transform 0.15s, box-shadow 0.15s;
  touch-action: none;
  user-select: none;
}
.connect-item--paired { border-color: var(--color-brand-mint); background: rgba(var(--color-brand-mint-rgb), 0.08); }
.connect-item--dragging { border-color: var(--color-brand-ochre); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }
.connect-item--drop-target { border-color: var(--color-brand-ochre); background: rgba(var(--color-brand-ochre-rgb), 0.08); transform: scale(1.03); }
.connect-item__label { font-family: Inter, sans-serif; font-size: 14px; font-weight: 500; color: var(--color-ink); }
.connect-item__partner { font-family: Inter, sans-serif; font-size: 11px; color: var(--color-muted); }
.connect-line { stroke-width: 3; stroke-linecap: round; }
.connect-line--active { stroke: var(--color-brand-ochre); stroke-dasharray: 6 4; opacity: 0.7; }
.connect-line--correct { stroke: var(--color-brand-mint); }
.connect-line--wrong { stroke: var(--color-brand-coral); }
@media (prefers-reduced-motion: reduce) {
  .connect-item { transition: none; }
}
</style>
