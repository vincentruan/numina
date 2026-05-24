<template>
  <div
    class="wish-constellation-card"
    :class="[`tint-${tint}`, { 'is-pressed': isPressed, 'is-peek-affected': peekAfterProgress !== null }]"
    role="button"
    tabindex="0"
    :aria-label="ariaLabel"
    @click="onTap"
    @keydown.enter="onTap"
    @keydown.space.prevent="onTap"
    @touchstart="onTouchStart"
    @touchend="onTouchEnd"
    @touchcancel="onTouchEnd"
    @touchmove="onTouchMove"
    @mousedown="onMouseDown"
    @mouseup="onMouseUp"
    @mouseleave="onMouseUp"
    @contextmenu.prevent
  >
    <div class="ring-wrap">
      <svg class="ring-svg" viewBox="0 0 64 64" aria-hidden="true">
        <circle class="ring-track" cx="32" cy="32" r="28" fill="none" stroke-width="4" />
        <circle
          class="ring-progress"
          cx="32"
          cy="32"
          r="28"
          fill="none"
          stroke-width="4"
          stroke-linecap="round"
          :stroke-dasharray="ringCircumference"
          :stroke-dashoffset="visibleDashOffset"
          transform="rotate(-90 32 32)"
        />
      </svg>
      <span class="ring-emoji">{{ wish.emoji || '🌟' }}</span>
      <span v-if="statusIcon" class="status-icon" aria-hidden="true">{{ statusIcon }}</span>
      <span v-if="daysAdded > 0" class="days-added-label" aria-hidden="true">{{ t('wishes.peek.daysAdded', { n: daysAdded }) }}</span>
      <span v-if="isPressed" class="confirm-tag" aria-hidden="true">{{ t('wishes.peek.confirmTag') }}</span>
    </div>
    <p class="wish-name">{{ wish.name }}</p>
    <p class="days-line" :class="{ 'is-placeholder': daysEstimateValue === null }">
      {{ daysEstimateValue === null ? t('wishes.timeUnitPlaceholder') : t('wishes.timeUnitDays', { days: daysEstimateValue }) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ChildWish } from '@/api/childWishes'
import type { ReachabilityTint } from '@numina/math'

const props = defineProps<{
  wish: ChildWish
  tint: ReachabilityTint
  daysEstimateValue: number | null
  progress: number
  peekAfterProgress?: number | null
  daysAdded?: number
  isPressed?: boolean
}>()

const emit = defineEmits<{
  tap: [wishId: string]
  'peek-start': [wishId: string]
  'peek-end': [wishId: string]
}>()

const { t } = useI18n()

const LONG_PRESS_MS = 350
const RING_RADIUS = 28
const ringCircumference = 2 * Math.PI * RING_RADIUS

const daysAdded = computed(() => props.daysAdded ?? 0)

const visibleProgress = computed(() => {
  const p = props.peekAfterProgress ?? props.progress ?? 0
  return Math.max(0, Math.min(1, p))
})

const visibleDashOffset = computed(() => ringCircumference * (1 - visibleProgress.value))

const ariaLabel = computed(() => `${t(`wishes.tint.${props.tint}.aria`)}: ${props.wish.name}`)

const statusIcon = computed(() => {
  if (props.tint === 'green') return '✅'
  if (props.tint === 'yellow') return '⏳'
  return ''
})

let longPressTimer: ReturnType<typeof setTimeout> | null = null
const peekActive = ref(false)
const suppressTap = ref(false)

function startLongPress() {
  if (longPressTimer) clearTimeout(longPressTimer)
  longPressTimer = setTimeout(() => {
    longPressTimer = null
    peekActive.value = true
    suppressTap.value = true
    emit('peek-start', props.wish.id)
  }, LONG_PRESS_MS)
}

function cancelLongPress() {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
  if (peekActive.value) {
    peekActive.value = false
    emit('peek-end', props.wish.id)
  }
}

function onTouchStart() {
  startLongPress()
}
function onTouchEnd() {
  cancelLongPress()
}
function onTouchMove() {
  cancelLongPress()
}
function onMouseDown() {
  startLongPress()
}
function onMouseUp() {
  cancelLongPress()
}

function onTap() {
  if (suppressTap.value) {
    suppressTap.value = false
    return
  }
  emit('tap', props.wish.id)
}

onUnmounted(() => {
  if (longPressTimer) clearTimeout(longPressTimer)
})
</script>

<style scoped>
.wish-constellation-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-hairline);
  cursor: pointer;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.wish-constellation-card:active,
.wish-constellation-card.is-pressed {
  transform: scale(0.97);
}
.wish-constellation-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.ring-wrap {
  position: relative;
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ring-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.ring-track {
  stroke: var(--color-hairline);
  opacity: 0.5;
}

.ring-progress {
  transition: stroke-dashoffset 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.tint-green .ring-progress {
  stroke: var(--color-success);
}
.tint-yellow .ring-progress {
  stroke: var(--color-warning);
}
.tint-red .ring-progress {
  stroke: var(--color-error);
  opacity: 0.6;
}
.tint-gray .ring-progress {
  stroke: var(--color-muted-soft);
  stroke-dasharray: 4 4;
}

.ring-emoji {
  font-size: 28px;
  z-index: 1;
}

.status-icon {
  position: absolute;
  top: -2px;
  right: -2px;
  font-size: 18px;
  background: var(--color-surface-card);
  border-radius: var(--radius-pill);
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.days-added-label {
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-error);
  color: var(--color-on-dark, var(--color-on-primary));
  font-family: Inter, sans-serif;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  z-index: 3;
}

.confirm-tag {
  position: absolute;
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-success);
  color: var(--color-on-dark, var(--color-on-primary));
  font-family: Inter, sans-serif;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  z-index: 3;
}

.wish-name {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
}

.days-line {
  font-family: Inter, sans-serif;
  font-size: 11px;
  color: var(--color-muted);
  margin: 0;
  text-align: center;
  line-height: 1.3;
}
.days-line.is-placeholder {
  color: var(--color-muted-soft);
  font-size: 10px;
}
</style>
