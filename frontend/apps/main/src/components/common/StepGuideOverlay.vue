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
      <!-- SVG spotlight mask: punches a hole over the target element -->
      <svg
        class="stepguide-spotlight-svg"
        aria-hidden="true"
        :viewBox="`0 0 ${vpWidth} ${vpHeight}`"
        preserveAspectRatio="none"
      >
        <defs>
          <mask id="stepguide-spotlight-mask">
            <!-- White = visible (the dark overlay shows through) -->
            <rect width="100%" height="100%" fill="white" />
            <!-- Black = cut-out (transparent hole = spotlight) -->
            <rect
              v-if="spotlightRect"
              :x="spotlightRect.x - SPOTLIGHT_PAD"
              :y="spotlightRect.y - SPOTLIGHT_PAD"
              :width="spotlightRect.width + SPOTLIGHT_PAD * 2"
              :height="spotlightRect.height + SPOTLIGHT_PAD * 2"
              rx="8"
              fill="black"
            />
          </mask>
        </defs>
        <!-- Dark overlay with hole cut out -->
        <rect
          width="100%"
          height="100%"
          fill="rgba(1,1,32,0.72)"
          mask="url(#stepguide-spotlight-mask)"
        />
      </svg>

      <!-- Tooltip card positioned near the spotlight -->
      <div
        ref="tooltipRef"
        class="stepguide-tooltip"
        :style="tooltipStyle"
        role="region"
      >
        <!-- Step indicator dots -->
        <div class="stepguide-dots" aria-hidden="true">
          <span
            v-for="n in resolvedSteps.length"
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
            {{ t('onboarding.skip') }}
          </button>
          <button
            ref="nextBtnRef"
            class="stepguide-btn stepguide-btn--primary"
            @click="onPrimaryClick"
          >
            {{ isLastStep ? t('onboarding.done') : t('onboarding.next') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { StepGuideStep } from '@/composables/useStepGuide'

const props = defineProps<{
  visible: boolean
  steps: StepGuideStep[] | Ref<StepGuideStep[]>
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

const isLastStep = computed(() => {
  return props.currentStep === resolvedSteps.value.length - 1
})
const resolvedSteps = computed(() => {
  const s = props.steps
  return 'value' in s ? s.value : s
})
const currentStepData = computed(() => resolvedSteps.value[props.currentStep])
const currentTitle = computed(() => currentStepData.value?.title ?? '')
const currentDesc = computed(() => currentStepData.value?.desc ?? '')

function getTargetElement(): Element | null {
  const selector = currentStepData.value?.selector
  if (!selector) return null
  // Try each comma-separated selector in order
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
  const tooltipH = tooltipEl.offsetHeight || 140
  const tooltipW = tooltipEl.offsetWidth || 280
  const vp = { w: vpWidth.value, h: vpHeight.value }

  const spotBottom = targetRect.y + targetRect.height + SPOTLIGHT_PAD
  const spotTop = targetRect.y - SPOTLIGHT_PAD

  let top: number

  // Prefer placing tooltip below the spotlight
  if (spotBottom + tooltipH + TOOLTIP_MARGIN <= vp.h) {
    top = spotBottom + TOOLTIP_MARGIN
  } else if (spotTop - tooltipH - TOOLTIP_MARGIN >= 0) {
    // Place above
    top = spotTop - tooltipH - TOOLTIP_MARGIN
  } else {
    // Fallback: center vertically
    top = Math.max(TOOLTIP_MARGIN, (vp.h - tooltipH) / 2)
  }

  // Horizontally: center on spotlight, clamp to viewport
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
    width: `${Math.min(300, vp.w - TOOLTIP_MARGIN * 2)}px`,
  }
}

function onPrimaryClick() {
  if (isLastStep.value) {
    emit('complete')
  } else {
    emit('next')
  }
}

// Focus trap: Tab cycles between skip and next buttons only
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

// Save body scroll position when overlay opens so we can restore it on close.
// Exposed so parent can zero it before skip() during navigation, preventing
// the overlay from restoring a stale scroll position of the old page.
const savedBodyScrollTop = ref(0)
defineExpose({ savedBodyScrollTop })

watch(
  () => props.visible,
  (val) => {
    if (val) {
      savedBodyScrollTop.value = window.scrollY
      document.body.style.overflow = 'hidden'
      // Prevent any residual body scroll from leaking through
      document.body.scrollTop = 0
      document.documentElement.scrollTop = 0
      nextTick(() => {
        updateSpotlight()
        // Focus the next/primary button on open (preventScroll avoids
        // mobile browsers jumping to the fixed-position button)
        nextTick(() => nextBtnRef.value?.focus({ preventScroll: true }))
      })
    } else {
      document.body.style.overflow = ''
      // Reset body scroll — overflow:hidden期间可能积累偏移
      document.body.scrollTop = 0
      document.documentElement.scrollTop = 0
      // Restore the scroll position the page had before the guide opened
      window.scrollTo(0, savedBodyScrollTop.value)
      savedBodyScrollTop.value = 0
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
  // Defensive cleanup: ensure overflow and scroll are reset even if
  // the visible watcher didn't fire (e.g. parent destroyed without toggling visible)
  document.body.style.overflow = ''
  document.body.scrollTop = 0
  document.documentElement.scrollTop = 0
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

/* Tooltip card */
.stepguide-tooltip {
  position: fixed;
  background: var(--card-bg, #ffffff);
  border-radius: var(--radius-sm, 8px);
  padding: 16px;
  box-shadow: 0 8px 32px rgba(1, 1, 32, 0.18);
  border: 1px solid var(--color-card-border, rgba(1, 1, 32, 0.08));
  min-width: 240px;
  max-width: 320px;
  z-index: 10000;
  /* Smooth repositioning between steps */
  transition: top 0.25s ease, left 0.25s ease;
}

[data-theme='dark'] .stepguide-tooltip {
  background: #1a1a3a;
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

/* Step dots */
.stepguide-dots {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.stepguide-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: var(--color-hairline, rgba(1, 1, 32, 0.12));
  transition: background 0.2s ease, width 0.2s ease;
}

.stepguide-dot--active {
  background: var(--van-primary-color, #010120);
  width: 16px;
}

[data-theme='dark'] .stepguide-dot {
  background: rgba(255, 255, 255, 0.15);
}

[data-theme='dark'] .stepguide-dot--active {
  background: var(--color-lavender, #bdbbff);
}

/* Content */
.stepguide-content {
  margin-bottom: 14px;
}

.stepguide-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  margin: 0 0 6px;
  letter-spacing: -0.3px;
  line-height: 1.3;
}

.stepguide-desc {
  font-size: 14px;
  color: var(--text-secondary, #616161);
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
  padding: 0 16px;
  border-radius: var(--radius-xs, 4px);
  font-size: 14px;
  font-weight: 500;
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
  color: var(--text-secondary, #616161);
  border: 1px solid var(--color-card-border, rgba(1, 1, 32, 0.12));
}

[data-theme='dark'] .stepguide-btn--ghost {
  color: var(--text-secondary, #c8c8d0);
  border-color: rgba(255, 255, 255, 0.12);
}

.stepguide-btn--primary {
  background: var(--van-primary-color, #010120);
  color: var(--color-on-primary, #ffffff);
  flex: 1;
}

[data-theme='dark'] .stepguide-btn--primary {
  background: var(--color-lavender, #bdbbff);
  color: #010120;
}

.stepguide-btn:focus-visible {
  outline: 2px solid var(--van-primary-color, #010120);
  outline-offset: 2px;
}

[data-theme='dark'] .stepguide-btn:focus-visible {
  outline-color: var(--color-lavender, #bdbbff);
}
</style>
