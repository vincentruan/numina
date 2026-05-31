<template>
  <!-- Full-screen onboarding overlay with spotlight effect -->
  <Teleport to="body">
    <div
      v-if="visible"
      class="onboarding-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="t('onboarding.step' + currentStep + '.title')"
      @keydown="onKeydown"
    >
      <!-- SVG spotlight mask: punches a hole over the target element -->
      <svg
        class="onboarding-spotlight-svg"
        aria-hidden="true"
        :viewBox="`0 0 ${vpWidth} ${vpHeight}`"
        preserveAspectRatio="none"
      >
        <defs>
          <mask id="onboarding-spotlight-mask">
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
          mask="url(#onboarding-spotlight-mask)"
        />
      </svg>

      <!-- Tooltip card positioned near the spotlight -->
      <div
        ref="tooltipRef"
        class="onboarding-tooltip"
        :style="tooltipStyle"
        role="region"
      >
        <!-- Step indicator dots -->
        <div class="onboarding-dots" aria-hidden="true">
          <span
            v-for="n in TOTAL_STEPS"
            :key="n"
            class="onboarding-dot"
            :class="{ 'onboarding-dot--active': n === currentStep }"
          />
        </div>

        <!-- Step content -->
        <div
          aria-live="polite"
          aria-atomic="true"
          class="onboarding-content"
        >
          <h3 class="onboarding-title">{{ stepTitle }}</h3>
          <p class="onboarding-desc">{{ stepDesc }}</p>
        </div>

        <!-- Action buttons -->
        <div class="onboarding-actions">
          <button
            ref="skipBtnRef"
            class="onboarding-btn onboarding-btn--ghost"
            @click="onSkip"
          >
            {{ t('onboarding.skip') }}
          </button>
          <button
            ref="nextBtnRef"
            class="onboarding-btn onboarding-btn--primary"
            @click="onNext"
          >
            {{ isLastStep ? t('onboarding.done') : t('onboarding.next') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  complete: []
}>()

const { t } = useI18n()

const TOTAL_STEPS = 3
const SPOTLIGHT_PAD = 8
const TOOLTIP_MARGIN = 12

// Step selectors — graceful degradation if element not found
const STEP_SELECTORS: Record<number, string> = {
  1: '.net-worth-card, .hero-section',
  2: '.fab',
  3: '[data-tabbar-settings], .van-tabbar-item:last-child',
}

const currentStep = ref(1)
const spotlightRect = ref<DOMRect | null>(null)
const vpWidth = ref(window.innerWidth)
const vpHeight = ref(window.innerHeight)
const tooltipRef = ref<HTMLElement | null>(null)
const skipBtnRef = ref<HTMLElement | null>(null)
const nextBtnRef = ref<HTMLElement | null>(null)
const tooltipStyle = ref<Record<string, string>>({})

const isLastStep = computed(() => currentStep.value === TOTAL_STEPS)

const stepTitle = computed(() => t(`onboarding.step${currentStep.value}.title`))
const stepDesc = computed(() => t(`onboarding.step${currentStep.value}.desc`))

function getTargetElement(step: number): Element | null {
  const selector = STEP_SELECTORS[step]
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

  const el = getTargetElement(currentStep.value)
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

  const spotTop = targetRect.y - SPOTLIGHT_PAD
  const spotBottom = targetRect.y + targetRect.height + SPOTLIGHT_PAD
  const spotLeft = targetRect.x - SPOTLIGHT_PAD
  const spotRight = targetRect.x + targetRect.width + SPOTLIGHT_PAD

  let top: number
  let left: number

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
  const spotCenterX = (spotLeft + spotRight) / 2
  left = spotCenterX - tooltipW / 2
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

function lockBodyScroll() {
  document.body.style.overflow = 'hidden'
}

function unlockBodyScroll() {
  document.body.style.overflow = ''
}

function onSkip() {
  complete()
}

function onNext() {
  if (isLastStep.value) {
    complete()
  } else {
    currentStep.value++
    nextTick(() => updateSpotlight())
  }
}

function complete() {
  unlockBodyScroll()
  emit('complete')
}

// Focus trap: Tab cycles between skip and next buttons only
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    onSkip()
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

function onResize() {
  updateSpotlight()
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      currentStep.value = 1
      lockBodyScroll()
      nextTick(() => {
        updateSpotlight()
        // Focus the next/primary button on open
        nextTick(() => nextBtnRef.value?.focus())
      })
    } else {
      unlockBodyScroll()
    }
  },
)

onMounted(() => {
  window.addEventListener('resize', onResize, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  unlockBodyScroll()
})
</script>

<style scoped>
.onboarding-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  /* Pointer events pass through to the SVG overlay only */
  pointer-events: all;
}

.onboarding-spotlight-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

/* Tooltip card */
.onboarding-tooltip {
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

[data-theme='dark'] .onboarding-tooltip {
  background: #1a1a3a;
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

/* Step dots */
.onboarding-dots {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}

.onboarding-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full, 9999px);
  background: var(--color-hairline, rgba(1, 1, 32, 0.12));
  transition: background 0.2s ease, width 0.2s ease;
}

.onboarding-dot--active {
  background: var(--van-primary-color, #010120);
  width: 16px;
}

[data-theme='dark'] .onboarding-dot {
  background: rgba(255, 255, 255, 0.15);
}

[data-theme='dark'] .onboarding-dot--active {
  background: var(--color-lavender, #bdbbff);
}

/* Content */
.onboarding-content {
  margin-bottom: 14px;
}

.onboarding-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  margin: 0 0 6px;
  letter-spacing: -0.3px;
  line-height: 1.3;
}

.onboarding-desc {
  font-size: 14px;
  color: var(--text-secondary, #616161);
  margin: 0;
  line-height: 1.5;
}

/* Actions */
.onboarding-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.onboarding-btn {
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

.onboarding-btn:active {
  transform: scale(0.97);
  opacity: 0.85;
}

.onboarding-btn--ghost {
  background: transparent;
  color: var(--text-secondary, #616161);
  border: 1px solid var(--color-card-border, rgba(1, 1, 32, 0.12));
}

[data-theme='dark'] .onboarding-btn--ghost {
  color: var(--text-secondary, #c8c8d0);
  border-color: rgba(255, 255, 255, 0.12);
}

.onboarding-btn--primary {
  background: var(--van-primary-color, #010120);
  color: var(--color-on-primary, #ffffff);
  flex: 1;
}

[data-theme='dark'] .onboarding-btn--primary {
  background: var(--color-lavender, #bdbbff);
  color: #010120;
}

.onboarding-btn:focus-visible {
  outline: 2px solid var(--van-primary-color, #010120);
  outline-offset: 2px;
}

[data-theme='dark'] .onboarding-btn:focus-visible {
  outline-color: var(--color-lavender, #bdbbff);
}
</style>
