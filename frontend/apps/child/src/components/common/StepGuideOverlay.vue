<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="stepguide-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="currentTitle"
      @keydown="onKeydown"
    >
      <!-- SVG spotlight mask -->
      <svg
        class="stepguide-spotlight-svg"
        aria-hidden="true"
        :viewBox="`0 0 ${vpWidth} ${vpHeight}`"
        preserveAspectRatio="none"
      >
        <defs>
          <mask id="stepguide-spotlight-mask-child">
            <rect width="100%" height="100%" fill="white" />
            <rect
              v-if="spotlightRect"
              :x="spotlightRect.x - SPOTLIGHT_PAD"
              :y="spotlightRect.y - SPOTLIGHT_PAD"
              :width="spotlightRect.width + SPOTLIGHT_PAD * 2"
              :height="spotlightRect.height + SPOTLIGHT_PAD * 2"
              rx="16"
              fill="black"
            />
          </mask>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="rgba(0, 0, 0, 0.6)"
          mask="url(#stepguide-spotlight-mask-child)"
        />
      </svg>

      <!-- Tooltip card -->
      <div
        ref="tooltipRef"
        class="stepguide-tooltip"
        :style="tooltipStyle"
        role="region"
      >
        <!-- Step indicator dots -->
        <div class="stepguide-dots" aria-hidden="true">
          <span
            v-for="n in steps.length"
            :key="n"
            class="stepguide-dot"
            :class="{ 'stepguide-dot--active': n === currentStep + 1 }"
          />
        </div>

        <!-- Step content -->
        <div aria-live="polite" aria-atomic="true" class="stepguide-content">
          <h3 class="stepguide-title">{{ currentTitle }}</h3>
          <p class="stepguide-desc">{{ currentDesc }}</p>
        </div>

        <!-- Action buttons -->
        <div class="stepguide-actions">
          <button
            ref="skipBtnRef"
            class="stepguide-btn stepguide-btn--ghost"
            @click="$emit('skip')"
          >
            {{ t('childOnboarding.skip') }}
          </button>
          <button
            ref="nextBtnRef"
            class="stepguide-btn stepguide-btn--primary"
            @click="onPrimaryClick"
          >
            {{ isLastStep ? t('childOnboarding.done') : t('childOnboarding.next') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import type { StepGuideStep } from '@/composables/useStepGuide'

const props = defineProps<{
  visible: boolean
  steps: StepGuideStep[]
  currentStep: number
}>()

const emit = defineEmits<{
  skip: []
  next: []
  complete: []
}>()

const { t } = useI18n()

const SPOTLIGHT_PAD = 8
const TOOLTIP_MARGIN = 12

const spotlightRect = ref<DOMRect | null>(null)
const vpWidth = ref(window.innerWidth)
const vpHeight = ref(window.innerHeight)
const tooltipRef = ref<HTMLElement | null>(null)
const skipBtnRef = ref<HTMLElement | null>(null)
const nextBtnRef = ref<HTMLElement | null>(null)
const tooltipStyle = ref<Record<string, string>>({})

const isLastStep = computed(() => props.currentStep === props.steps.length - 1)
const currentStepData = computed(() => props.steps[props.currentStep])
const currentTitle = computed(() => currentStepData.value?.title ?? '')
const currentDesc = computed(() => currentStepData.value?.desc ?? '')

function getTargetElement(): Element | null {
  const selector = currentStepData.value?.selector
  if (!selector) return null
  for (const sel of selector.split(',')) {
    const el = document.querySelector(sel.trim())
    if (el) return el
  }
  return null
}

function updateSpotlight() {
  vpWidth.value = window.innerWidth
  vpHeight.value = window.innerHeight
  const el = getTargetElement()
  if (!el) {
    spotlightRect.value = null
    positionTooltipCenter()
    return
  }
  const rect = el.getBoundingClientRect()
  spotlightRect.value = rect
  nextTick(() => positionTooltip(rect))
}

function positionTooltip(targetRect: DOMRect) {
  if (!tooltipRef.value) return

  const tooltipEl = tooltipRef.value
  const tooltipH = tooltipEl.offsetHeight || 160
  const tooltipW = tooltipEl.offsetWidth || 300
  const vp = { w: vpWidth.value, h: vpHeight.value }

  const spotBottom = targetRect.y + targetRect.height + SPOTLIGHT_PAD
  const spotTop = targetRect.y - SPOTLIGHT_PAD

  let top: number

  if (spotBottom + tooltipH + TOOLTIP_MARGIN <= vp.h) {
    top = spotBottom + TOOLTIP_MARGIN
  } else if (spotTop - tooltipH - TOOLTIP_MARGIN >= 0) {
    top = spotTop - tooltipH - TOOLTIP_MARGIN
  } else {
    top = Math.max(TOOLTIP_MARGIN, (vp.h - tooltipH) / 2)
  }

  const spotCenterX = targetRect.x + targetRect.width / 2
  let left = spotCenterX - tooltipW / 2
  left = Math.max(TOOLTIP_MARGIN, Math.min(left, vp.w - tooltipW - TOOLTIP_MARGIN))

  tooltipStyle.value = {
    position: 'fixed',
    top: `${top}px`,
    left: `${left}px`,
    width: `${Math.min(tooltipW, vp.w - TOOLTIP_MARGIN * 2)}px`,
  }
}

function positionTooltipCenter() {
  const vp = { w: vpWidth.value, h: vpHeight.value }
  tooltipStyle.value = {
    position: 'fixed',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: `${Math.min(320, vp.w - TOOLTIP_MARGIN * 2)}px`,
  }
}

function onPrimaryClick() {
  if (isLastStep.value) {
    emit('complete')
  } else {
    emit('next')
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('skip')
    return
  }
  if (e.key === 'Tab') {
    e.preventDefault()
    const skip = skipBtnRef.value
    const next = nextBtnRef.value
    if (!skip || !next) return
    if (document.activeElement === skip) {
      next.focus()
    } else {
      skip.focus()
    }
  }
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      document.body.style.overflow = 'hidden'
      nextTick(() => {
        updateSpotlight()
        nextTick(() => nextBtnRef.value?.focus())
      })
    } else {
      document.body.style.overflow = ''
    }
  },
)

watch(
  () => props.currentStep,
  () => {
    nextTick(() => updateSpotlight())
  },
)

onMounted(() => {
  window.addEventListener('resize', updateSpotlight, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('resize', updateSpotlight)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.stepguide-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: all;
}

.stepguide-spotlight-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* Tooltip card — child Clay styling */
.stepguide-tooltip {
  position: fixed;
  background: var(--color-surface-card, #f5f0e0);
  border-radius: var(--radius-lg, 16px);
  padding: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  border: 1px solid var(--color-hairline, #e5e5e5);
  min-width: 260px;
  max-width: 340px;
  z-index: 10000;
  transition: top 0.25s ease, left 0.25s ease;
}

[data-theme='dark'] .stepguide-tooltip {
  background: var(--color-surface-card, #152828);
  border-color: var(--color-hairline, #1e3030);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

/* Step dots */
.stepguide-dots {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

.stepguide-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-pill, 9999px);
  background: var(--color-hairline, #e5e5e5);
  transition: background 0.2s ease, width 0.2s ease;
}

.stepguide-dot--active {
  background: var(--color-brand-ochre, #e8b94a);
  width: 18px;
}

[data-theme='dark'] .stepguide-dot {
  background: var(--color-hairline, #1e3030);
}

[data-theme='dark'] .stepguide-dot--active {
  background: var(--color-brand-ochre, #d4a83a);
}

/* Content */
.stepguide-content {
  margin-bottom: 16px;
}

.stepguide-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink, #0a0a0a);
  margin: 0 0 8px;
  letter-spacing: -0.3px;
  line-height: 1.3;
}

.stepguide-desc {
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-body, #3a3a3a);
  margin: 0;
  line-height: 1.5;
}

/* Actions */
.stepguide-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.stepguide-btn {
  min-height: 44px;
  min-width: 72px;
  padding: 0 18px;
  border-radius: var(--radius-md, 12px);
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: opacity 0.15s ease, transform 0.1s ease;
}

.stepguide-btn:active {
  transform: scale(0.97);
  opacity: 0.85;
}

.stepguide-btn--ghost {
  background: transparent;
  color: var(--color-muted, #6a6a6a);
  border: 1px solid var(--color-hairline, #e5e5e5);
}

[data-theme='dark'] .stepguide-btn--ghost {
  color: var(--color-body, #c0bcb0);
  border-color: var(--color-hairline, #1e3030);
}

.stepguide-btn--primary {
  background: var(--color-brand-pink, #ff4d8b);
  color: var(--color-on-dark, #ffffff);
  flex: 1;
}

[data-theme='dark'] .stepguide-btn--primary {
  background: var(--color-brand-ochre, #d4a83a);
  color: var(--color-on-primary, #0a0a0a);
}

.stepguide-btn:focus-visible {
  outline: 2px solid var(--color-brand-ochre, #e8b94a);
  outline-offset: 2px;
}
</style>
