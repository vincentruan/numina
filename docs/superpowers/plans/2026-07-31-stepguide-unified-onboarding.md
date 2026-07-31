# StepGuide 统一引导系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified onboarding/guidance system with 3 modes (spotlight/tooltip/gesture-hint) for both main and child apps, replacing the broken legacy OnboardingOverlay.

**Architecture:** Core composable `useStepGuide` manages step state and localStorage persistence. `StepGuideOverlay.vue` renders spotlight/tooltip UI via Teleport. `useGestureHint` handles one-shot gesture animations. Storage helpers in `utils/storage.ts` manage key lifecycle.

**Tech Stack:** Vue 3 `<script setup>`, Vant 4, vitest, CSS variables, localStorage

## Global Constraints

- `<script setup lang="ts">` only — no Options API
- No `any` / `@ts-ignore`
- i18n required for all UI strings — `t('key')`, zh-CN + en-US lockstep
- Touch targets min 44×44px
- Dark mode via CSS variables (`[data-theme='dark']`)
- No new dependencies — use Vue 3 built-ins + existing CSS variables
- localStorage keys: `guide_*` (spotlight), `gesture_*` (animations), `tip_*` (tooltips)

---

### Task 1: Storage Helpers

**Files:**
- Modify: `frontend/apps/main/src/utils/storage.ts`
- Test: `frontend/apps/main/src/utils/__tests__/storage-guide.spec.ts`

**Interfaces:**
- Produces: `clearAllGuideKeys(): void`, `migrateOldOnboardingKey(): boolean`, `isGuideDone(key: string): boolean`, `markGuideDone(key: string): void`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/apps/main/src/utils/__tests__/storage-guide.spec.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { clearAllGuideKeys, migrateOldOnboardingKey, isGuideDone, markGuideDone } from '../storage'

describe('guide storage helpers', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('isGuideDone / markGuideDone', () => {
    it('returns false when key not set', () => {
      expect(isGuideDone('guide_test')).toBe(false)
    })

    it('returns true after markGuideDone', () => {
      markGuideDone('guide_test')
      expect(isGuideDone('guide_test')).toBe(true)
    })
  })

  describe('migrateOldOnboardingKey', () => {
    it('returns false when no old key exists', () => {
      expect(migrateOldOnboardingKey()).toBe(false)
    })

    it('migrates old key to new key and returns true', () => {
      localStorage.setItem('onboarding_completed', 'true')
      const migrated = migrateOldOnboardingKey()
      expect(migrated).toBe(true)
      expect(localStorage.getItem('guide_main-onboarding-v2')).toBe('done')
    })

    it('does not set new key if old key is not "true"', () => {
      localStorage.setItem('onboarding_completed', 'false')
      migrateOldOnboardingKey()
      expect(localStorage.getItem('guide_main-onboarding-v2')).toBeNull()
    })
  })

  describe('clearAllGuideKeys', () => {
    it('removes all guide_/gesture_/tip_ prefixed keys', () => {
      localStorage.setItem('guide_test', 'done')
      localStorage.setItem('gesture_test', 'done')
      localStorage.setItem('tip_test', 'done')
      localStorage.setItem('other_key', 'keep')
      clearAllGuideKeys()
      expect(localStorage.getItem('guide_test')).toBeNull()
      expect(localStorage.getItem('gesture_test')).toBeNull()
      expect(localStorage.getItem('tip_test')).toBeNull()
      expect(localStorage.getItem('other_key')).toBe('keep')
    })

    it('removes legacy onboarding_completed key', () => {
      localStorage.setItem('onboarding_completed', 'true')
      clearAllGuideKeys()
      expect(localStorage.getItem('onboarding_completed')).toBeNull()
    })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/apps/main && pnpm vitest run src/utils/__tests__/storage-guide.spec.ts`
Expected: FAIL — functions not exported from `../storage`

- [ ] **Step 3: Implement storage helpers**

Add to `frontend/apps/main/src/utils/storage.ts`:

```ts
// --- Guide/Onboarding storage helpers ---

const GUIDE_PREFIXES = ['guide_', 'gesture_', 'tip_'] as const
const OLD_ONBOARDING_KEY = 'onboarding_completed'
const NEW_ONBOARDING_KEY = 'guide_main-onboarding-v2'

export function isGuideDone(key: string): boolean {
  return localStorage.getItem(key) === 'done'
}

export function markGuideDone(key: string): void {
  localStorage.setItem(key, 'done')
}

export function migrateOldOnboardingKey(): boolean {
  if (localStorage.getItem(OLD_ONBOARDING_KEY) === 'true') {
    localStorage.setItem(NEW_ONBOARDING_KEY, 'done')
    return true
  }
  return false
}

export function clearAllGuideKeys(): void {
  const keysToRemove = Object.keys(localStorage).filter(k =>
    GUIDE_PREFIXES.some(prefix => k.startsWith(prefix))
  )
  keysToRemove.forEach(k => localStorage.removeItem(k))
  localStorage.removeItem(OLD_ONBOARDING_KEY)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend/apps/main && pnpm vitest run src/utils/__tests__/storage-guide.spec.ts`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/utils/storage.ts frontend/apps/main/src/utils/__tests__/storage-guide.spec.ts
git commit -m "feat(stepguide): add storage helpers for guide key lifecycle

clearAllGuideKeys(), migrateOldOnboardingKey(), isGuideDone(), markGuideDone()
Handles guide_/gesture_/tip_ prefixes + legacy onboarding_completed migration"
```

---

### Task 2: `useStepGuide` Composable

**Files:**
- Create: `frontend/apps/main/src/composables/useStepGuide.ts`
- Test: `frontend/apps/main/src/composables/__tests__/useStepGuide.spec.ts`

**Interfaces:**
- Consumes: `isGuideDone`, `markGuideDone` from `@/utils/storage`
- Produces: `useStepGuide(options: UseStepGuideOptions): UseStepGuideReturn`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/apps/main/src/composables/__tests__/useStepGuide.spec.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useStepGuide } from '../useStepGuide'

describe('useStepGuide', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('initializes with isActive=false', () => {
    const { isActive, currentStep } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    expect(isActive.value).toBe(false)
    expect(currentStep.value).toBe(0)
  })

  it('start() activates when key not done', () => {
    const { isActive, start } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    expect(isActive.value).toBe(true)
  })

  it('start() does NOT activate when key is done', () => {
    localStorage.setItem('guide_test', 'done')
    const { isActive, start } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    expect(isActive.value).toBe(false)
  })

  it('next() advances step', () => {
    const { currentStep, start, next } = useStepGuide({
      key: 'guide_test',
      steps: [
        { selector: '.a', mode: 'spotlight', title: 't1', desc: 'd1' },
        { selector: '.b', mode: 'spotlight', title: 't2', desc: 'd2' },
      ],
    })
    start()
    expect(currentStep.value).toBe(0)
    next()
    expect(currentStep.value).toBe(1)
  })

  it('skip() deactivates and marks done', () => {
    const { isActive, start, skip } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    skip()
    expect(isActive.value).toBe(false)
    expect(localStorage.getItem('guide_test')).toBe('done')
  })

  it('complete() deactivates and marks done', () => {
    const { isActive, start, complete } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    complete()
    expect(isActive.value).toBe(false)
    expect(localStorage.getItem('guide_test')).toBe('done')
  })

  it('calls onComplete callback when completed', () => {
    const onComplete = vi.fn()
    const { start, complete } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
      onComplete,
    })
    start()
    complete()
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('calls onSkip callback when skipped', () => {
    const onSkip = vi.fn()
    const { start, skip } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
      onSkip,
    })
    start()
    skip()
    expect(onSkip).toHaveBeenCalledOnce()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/apps/main && pnpm vitest run src/composables/__tests__/useStepGuide.spec.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `useStepGuide`**

```ts
// frontend/apps/main/src/composables/useStepGuide.ts
import { ref, type Ref } from 'vue'
import { isGuideDone, markGuideDone } from '@/utils/storage'

export interface StepGuideStep {
  selector: string
  mode: 'spotlight' | 'tooltip' | 'gesture-hint'
  title?: string
  desc?: string
  gestureType?: 'swipe-left' | 'long-press-pulse'
  duration?: number
}

export interface UseStepGuideOptions {
  key: string
  steps: StepGuideStep[]
  onComplete?: () => void
  onSkip?: () => void
}

export interface UseStepGuideReturn {
  isActive: Ref<boolean>
  currentStep: Ref<number>
  steps: StepGuideStep[]
  start: () => void
  skip: () => void
  complete: () => void
  next: () => void
}

export function useStepGuide(options: UseStepGuideOptions): UseStepGuideReturn {
  const { key, steps, onComplete, onSkip } = options
  const isActive = ref(false)
  const currentStep = ref(0)

  function start() {
    if (isGuideDone(key)) return
    currentStep.value = 0
    isActive.value = true
  }

  function skip() {
    isActive.value = false
    markGuideDone(key)
    onSkip?.()
  }

  function complete() {
    isActive.value = false
    markGuideDone(key)
    onComplete?.()
  }

  function next() {
    if (currentStep.value < steps.length - 1) {
      currentStep.value++
    }
  }

  return { isActive, currentStep, steps, start, skip, complete, next }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend/apps/main && pnpm vitest run src/composables/__tests__/useStepGuide.spec.ts`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/composables/useStepGuide.ts frontend/apps/main/src/composables/__tests__/useStepGuide.spec.ts
git commit -m "feat(stepguide): add useStepGuide composable

Manages multi-step guide state: start/skip/complete/next, localStorage persistence, callbacks"
```

---

### Task 3: `useGestureHint` Composable

**Files:**
- Create: `frontend/apps/main/src/composables/useGestureHint.ts`
- Test: `frontend/apps/main/src/composables/__tests__/useGestureHint.spec.ts`

**Interfaces:**
- Consumes: `isGuideDone`, `markGuideDone` from `@/utils/storage`
- Produces: `useGestureHint(key: string, options: UseGestureHintOptions): { played: Ref<boolean>, trigger: () => void }`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/apps/main/src/composables/__tests__/useGestureHint.spec.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { useGestureHint } from '../useGestureHint'

describe('useGestureHint', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns played=false initially', () => {
    const { played } = useGestureHint('test-gesture', {
      target: '.test',
      type: 'swipe-left',
    })
    expect(played.value).toBe(false)
  })

  it('trigger() sets played=true and marks done when not already done', () => {
    const { played, trigger } = useGestureHint('test-gesture', {
      target: '.test',
      type: 'swipe-left',
    })
    trigger()
    expect(played.value).toBe(true)
    expect(localStorage.getItem('gesture_test-gesture')).toBe('done')
  })

  it('trigger() does NOT play when already done', () => {
    localStorage.setItem('gesture_test-gesture', 'done')
    const { played, trigger } = useGestureHint('test-gesture', {
      target: '.test',
      type: 'swipe-left',
    })
    trigger()
    expect(played.value).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/apps/main && pnpm vitest run src/composables/__tests__/useGestureHint.spec.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `useGestureHint`**

```ts
// frontend/apps/main/src/composables/useGestureHint.ts
import { ref, type Ref } from 'vue'
import { isGuideDone, markGuideDone } from '@/utils/storage'

export interface UseGestureHintOptions {
  target: string
  type: 'swipe-left' | 'long-press-pulse'
  autoPlay?: number
}

export function useGestureHint(key: string, options: UseGestureHintOptions): {
  played: Ref<boolean>
  trigger: () => void
} {
  const storageKey = `gesture_${key}`
  const played = ref(false)

  function trigger() {
    if (isGuideDone(storageKey)) return
    played.value = true
    markGuideDone(storageKey)
  }

  return { played, trigger }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend/apps/main && pnpm vitest run src/composables/__tests__/useGestureHint.spec.ts`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/composables/useGestureHint.ts frontend/apps/main/src/composables/__tests__/useGestureHint.spec.ts
git commit -m "feat(stepguide): add useGestureHint composable

One-shot gesture animation trigger with localStorage persistence"
```

---

### Task 4: `StepGuideOverlay` Component

**Files:**
- Create: `frontend/apps/main/src/components/common/StepGuideOverlay.vue`
- Test: `frontend/apps/main/src/components/common/__tests__/StepGuideOverlay.spec.ts`

**Interfaces:**
- Consumes: `StepGuideStep` from `@/composables/useStepGuide`
- Props: `visible: boolean`, `steps: StepGuideStep[]`, `currentStep: number`
- Emits: `skip`, `next`, `complete`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/apps/main/src/components/common/__tests__/StepGuideOverlay.spec.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import StepGuideOverlay from '../StepGuideOverlay.vue'

const mockSteps = [
  { selector: '.target-1', mode: 'spotlight' as const, title: 'Step 1', desc: 'First step' },
  { selector: '.target-2', mode: 'spotlight' as const, title: 'Step 2', desc: 'Second step' },
]

describe('StepGuideOverlay', () => {
  it('does not render when visible=false', () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: false, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.find('.stepguide-overlay').exists()).toBe(false)
  })

  it('renders overlay when visible=true', () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.find('.stepguide-overlay').exists()).toBe(true)
  })

  it('emits skip when skip button clicked', async () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    await wrapper.find('.stepguide-btn--ghost').trigger('click')
    expect(wrapper.emitted('skip')).toBeTruthy()
  })

  it('emits next when next button clicked on non-last step', async () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    await wrapper.find('.stepguide-btn--primary').trigger('click')
    expect(wrapper.emitted('next')).toBeTruthy()
  })

  it('emits complete when done button clicked on last step', async () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 1 },
      global: { stubs: { teleport: true } },
    })
    await wrapper.find('.stepguide-btn--primary').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('renders aria-live region for screen readers', () => {
    const wrapper = mount(StepGuideOverlay, {
      props: { visible: true, steps: mockSteps, currentStep: 0 },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.find('[aria-live="polite"]').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend/apps/main && pnpm vitest run src/components/common/__tests__/StepGuideOverlay.spec.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `StepGuideOverlay.vue`**

Based on existing `OnboardingOverlay.vue` but generalized:

```vue
<!-- frontend/apps/main/src/components/common/StepGuideOverlay.vue -->
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
          <mask id="stepguide-spotlight-mask">
            <rect width="100%" height="100%" fill="white" />
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
        <rect
          width="100%"
          height="100%"
          fill="rgba(1,1,32,0.72)"
          mask="url(#stepguide-spotlight-mask)"
        />
      </svg>

      <!-- Tooltip card -->
      <div
        ref="tooltipRef"
        class="stepguide-tooltip"
        :style="tooltipStyle"
        role="region"
      >
        <!-- Step dots -->
        <div class="stepguide-dots" aria-hidden="true">
          <span
            v-for="n in steps.length"
            :key="n"
            class="stepguide-dot"
            :class="{ 'stepguide-dot--active': n === currentStep + 1 }"
          />
        </div>

        <!-- Content -->
        <div aria-live="polite" aria-atomic="true" class="stepguide-content">
          <h3 class="stepguide-title">{{ currentTitle }}</h3>
          <p class="stepguide-desc">{{ currentDesc }}</p>
        </div>

        <!-- Actions -->
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
  spotlightRect.value = el.getBoundingClientRect()
  nextTick(() => positionTooltip(spotlightRect.value!))
}

function positionTooltip(targetRect: DOMRect) {
  if (!tooltipRef.value) return
  const tooltipEl = tooltipRef.value
  const tooltipH = tooltipEl.offsetHeight || 140
  const tooltipW = tooltipEl.offsetWidth || 280
  const vp = { w: vpWidth.value, h: vpHeight.value }
  const spotBottom = targetRect.y + targetRect.height + SPOTLIGHT_PAD

  let top: number
  if (spotBottom + tooltipH + TOOLTIP_MARGIN <= vp.h) {
    top = spotBottom + TOOLTIP_MARGIN
  } else if (targetRect.y - tooltipH - TOOLTIP_MARGIN >= 0) {
    top = targetRect.y - SPOTLIGHT_PAD - tooltipH - TOOLTIP_MARGIN
  } else {
    top = Math.max(TOOLTIP_MARGIN, (vp.h - tooltipH) / 2)
  }

  const spotCenterX = (targetRect.x + targetRect.width / 2)
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
  if (isLastStep.value) emit('complete')
  else emit('next')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') { emit('skip'); return }
  if (e.key === 'Tab') {
    e.preventDefault()
    const skip = skipBtnRef.value
    const next = nextBtnRef.value
    if (!skip || !next) return
    if (document.activeElement === skip) next.focus()
    else skip.focus()
  }
}

watch(() => props.visible, (val) => {
  if (val) {
    document.body.style.overflow = 'hidden'
    nextTick(() => { updateSpotlight(); nextTick(() => nextBtnRef.value?.focus()) })
  } else {
    document.body.style.overflow = ''
  }
})

watch(() => props.currentStep, () => {
  nextTick(() => updateSpotlight())
})

onMounted(() => { window.addEventListener('resize', updateSpotlight, { passive: true }) })
onUnmounted(() => {
  window.removeEventListener('resize', updateSpotlight)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.stepguide-overlay {
  position: fixed; inset: 0; z-index: 9999; pointer-events: all;
}
.stepguide-spotlight-svg {
  position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;
}
.stepguide-tooltip {
  position: fixed;
  background: var(--card-bg, #fff);
  border-radius: var(--radius-sm, 8px);
  padding: 16px;
  box-shadow: 0 8px 32px rgba(1,1,32,0.18);
  border: 1px solid var(--color-card-border, rgba(1,1,32,0.08));
  min-width: 240px; max-width: 320px; z-index: 10000;
  transition: top 0.25s ease, left 0.25s ease;
}
[data-theme='dark'] .stepguide-tooltip {
  background: #1a1a3a; border-color: rgba(255,255,255,0.1);
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.stepguide-dots { display: flex; gap: 6px; margin-bottom: 10px; }
.stepguide-dot {
  width: 6px; height: 6px; border-radius: 9999px;
  background: var(--color-hairline, rgba(1,1,32,0.12));
  transition: background 0.2s ease, width 0.2s ease;
}
.stepguide-dot--active { background: var(--van-primary-color, #010120); width: 16px; }
[data-theme='dark'] .stepguide-dot { background: rgba(255,255,255,0.15); }
[data-theme='dark'] .stepguide-dot--active { background: var(--color-lavender, #bdbbff); }
.stepguide-content { margin-bottom: 14px; }
.stepguide-title { font-size: 16px; font-weight: 600; color: var(--text-primary, #0a0a0a); margin: 0 0 6px; }
.stepguide-desc { font-size: 14px; color: var(--text-secondary, #616161); margin: 0; line-height: 1.5; }
.stepguide-actions { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.stepguide-btn {
  min-height: 44px; min-width: 72px; padding: 0 16px;
  border-radius: var(--radius-xs, 4px); font-size: 14px; font-weight: 500;
  cursor: pointer; border: none; transition: opacity 0.15s ease;
}
.stepguide-btn--ghost { background: transparent; color: var(--text-secondary); border: 1px solid var(--color-card-border); }
.stepguide-btn--primary { background: var(--van-primary-color, #010120); color: var(--color-on-primary, #fff); flex: 1; }
[data-theme='dark'] .stepguide-btn--primary { background: var(--color-lavender, #bdbbff); color: #010120; }
.stepguide-btn:focus-visible { outline: 2px solid var(--van-primary-color); outline-offset: 2px; }
</style>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend/apps/main && pnpm vitest run src/components/common/__tests__/StepGuideOverlay.spec.ts`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/components/common/StepGuideOverlay.vue frontend/apps/main/src/components/common/__tests__/StepGuideOverlay.spec.ts
git commit -m "feat(stepguide): add StepGuideOverlay component

Spotlight overlay with SVG mask, tooltip positioning, step dots, a11y (focus trap, aria-live, Escape skip)"
```

---

### Task 5: i18n Keys + AppTabBar `data-tab`

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`
- Modify: `frontend/apps/main/src/components/common/AppTabBar.vue`

**Interfaces:**
- Produces: i18n namespace `onboarding.*`, `childOnboarding.*`, `featureHints.*`, `settings.replayOnboarding`
- Produces: `data-tab` attributes on AppTabBar items

- [ ] **Step 1: Add i18n keys to zh-CN.ts**

Find the existing `onboarding:` block (around line 2419) and replace it:

```ts
// Replace existing onboarding block with:
onboarding: {
  step1: {
    empty: { title: '欢迎来到 Numina', desc: '这里是你的家庭资产全貌' },
    data: { title: '家庭资产全貌', desc: '这里展示您家庭的净资产、总资产和总负债' },
  },
  step2: { title: '管理资产与负债', desc: '点击这里管理您的资产、负债和心愿' },
  step3: { title: '邀请家人一起', desc: '在设置中创建或加入家庭，邀请家人共同管理' },
  skip: '跳过',
  next: '下一步',
  done: '完成',
},
childOnboarding: {
  step1: {
    empty: { title: '你的家务任务', desc: '这里会显示你的家务任务，完成后就能获得奖励' },
    data: { title: '你的任务列表', desc: '完成家务就能获得奖励' },
  },
  step2: { title: '我的奖励', desc: '积攒奖励，兑换心愿' },
},
featureHints: {
  assetLongPress: '长按资产可快捷操作（编辑/出售/标记闲置）',
  liabilitySwipe: '左滑负债卡片可删除',
  aiFirst: 'AI 教练随时为您解答财务问题',
  settingsInvite: '邀请家人加入，一起管理家庭资产',
},
```

Add to the `settings:` section:
```ts
replayOnboarding: '重新播放新手引导',
```

- [ ] **Step 2: Add matching i18n keys to en-US.ts**

```ts
onboarding: {
  step1: {
    empty: { title: 'Welcome to Numina', desc: 'This shows your complete family financial picture' },
    data: { title: 'Financial Overview', desc: 'See your net worth, total assets, and liabilities' },
  },
  step2: { title: 'Assets & Liabilities', desc: 'Manage your assets, liabilities, and wishes here' },
  step3: { title: 'Invite Family', desc: 'Create or join a family in Settings to manage together' },
  skip: 'Skip',
  next: 'Next',
  done: 'Done',
},
childOnboarding: {
  step1: {
    empty: { title: 'Your Chores', desc: 'Your chores will appear here — complete them to earn rewards' },
    data: { title: 'Your Task List', desc: 'Complete chores to earn rewards' },
  },
  step2: { title: 'My Rewards', desc: 'Earn rewards and redeem wishes' },
},
featureHints: {
  assetLongPress: 'Long press an asset for quick actions',
  liabilitySwipe: 'Swipe left on a liability to delete',
  aiFirst: 'AI Coach is here to answer your finance questions',
  settingsInvite: 'Invite family members to manage assets together',
},
```

Add to settings:
```ts
replayOnboarding: 'Replay onboarding',
```

- [ ] **Step 3: Add `data-tab` attributes to AppTabBar**

Modify `frontend/apps/main/src/components/common/AppTabBar.vue`:

```vue
<template>
  <van-tabbar :model-value="activeTab" class="app-tabbar" :z-index="1000" @change="onTabChange">
    <van-tabbar-item name="dashboard" data-tab="dashboard" icon="chart-trending-o">{{ t('nav.dashboard') }}</van-tabbar-item>
    <van-tabbar-item name="finance" data-tab="finance" icon="balance-o">{{ t('nav.finance') }}</van-tabbar-item>
    <van-tabbar-item name="ai" data-tab="ai" :aria-label="t('settings.aiAssistant')">
      <template #icon="{ active: isActive }">
        <AIBrainIcon :active="isActive" />
      </template>
      {{ t('nav.ai') }}
    </van-tabbar-item>
    <van-tabbar-item v-if="isOwner" name="baby" data-tab="baby" icon="friends-o">{{ t('nav.baby') }}</van-tabbar-item>
    <van-tabbar-item name="settings" data-tab="settings" icon="setting-o">{{ t('nav.settings') }}</van-tabbar-item>
  </van-tabbar>
</template>
```

- [ ] **Step 4: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts frontend/apps/main/src/components/common/AppTabBar.vue
git commit -m "feat(stepguide): add i18n keys and AppTabBar data-tab attributes

onboarding.step1.empty/data adaptive copy, childOnboarding, featureHints, settings.replayOnboarding
data-tab attributes on all 5 tabs for spotlight selector targeting"
```

---

### Task 6: Dashboard Onboarding Integration

**Files:**
- Modify: `frontend/apps/main/src/pages/DashboardPage.vue`
- Delete: `frontend/apps/main/src/components/common/OnboardingOverlay.vue`

**Interfaces:**
- Consumes: `useStepGuide` from `@/composables/useStepGuide`
- Consumes: `StepGuideOverlay` from `@/components/common/StepGuideOverlay.vue`
- Consumes: `migrateOldOnboardingKey`, `isGuideDone` from `@/utils/storage`

- [ ] **Step 1: Replace onboarding logic in DashboardPage.vue**

Replace the existing onboarding imports and logic:

```vue
<!-- In <template>, replace <OnboardingOverlay> with: -->
<StepGuideOverlay
  :visible="guide.isActive.value"
  :steps="guideSteps"
  :current-step="guide.currentStep.value"
  @skip="guide.skip"
  @next="guide.next"
  @complete="guide.complete"
/>
```

```ts
// In <script setup>, replace onboarding imports/logic with:
import { useStepGuide, type StepGuideStep } from '@/composables/useStepGuide'
import StepGuideOverlay from '@/components/common/StepGuideOverlay.vue'
import { migrateOldOnboardingKey } from '@/utils/storage'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Adaptive step 1 copy based on dashboard state
const guideSteps = computed<StepGuideStep[]>(() => {
  const isEmpty = (overview.value?.asset_count ?? 0) === 0
  return [
    {
      selector: '.empty-dashboard, .hero-section',
      mode: 'spotlight',
      title: isEmpty ? t('onboarding.step1.empty.title') : t('onboarding.step1.data.title'),
      desc: isEmpty ? t('onboarding.step1.empty.desc') : t('onboarding.step1.data.desc'),
    },
    {
      selector: '[data-tab="finance"]',
      mode: 'spotlight',
      title: t('onboarding.step2.title'),
      desc: t('onboarding.step2.desc'),
    },
    {
      selector: '[data-tab="settings"]',
      mode: 'spotlight',
      title: t('onboarding.step3.title'),
      desc: t('onboarding.step3.desc'),
    },
  ]
})

const guide = useStepGuide({
  key: 'guide_main-onboarding-v2',
  steps: guideSteps.value,
})

function maybeShowOnboarding() {
  // Migrate old key first
  migrateOldOnboardingKey()
  // Only show on Dashboard
  if (router.currentRoute.value.path !== '/') return
  guide.start()
}
```

Call `maybeShowOnboarding()` in `onMounted` / `onActivated`.

- [ ] **Step 2: Delete old OnboardingOverlay.vue**

```bash
rm frontend/apps/main/src/components/common/OnboardingOverlay.vue
```

- [ ] **Step 3: Run typecheck + tests**

Run: `cd frontend/apps/main && pnpm typecheck && pnpm vitest run`
Expected: 0 typecheck errors, all tests pass

- [ ] **Step 4: Commit**

```bash
git add -A frontend/apps/main/src/pages/DashboardPage.vue frontend/apps/main/src/components/common/OnboardingOverlay.vue
git commit -m "feat(stepguide): integrate StepGuide into Dashboard, remove legacy OnboardingOverlay

Adaptive Step 1 selector (.empty-dashboard/.hero-section), old key migration, 3-step spotlight tour"
```

---

### Task 7: FinanceHub Gesture Hints + Tooltip Integration

**Files:**
- Modify: `frontend/apps/main/src/pages/FinanceHubPage.vue`
- Modify: `frontend/apps/main/src/pages/AIHubPage.vue`
- Modify: `frontend/apps/main/src/pages/SettingsPage.vue`

**Interfaces:**
- Consumes: `useGestureHint` from `@/composables/useGestureHint`

- [ ] **Step 1: Add gesture hints to FinanceHub**

In `FinanceHubPage.vue`, add to the assets tab section:

```ts
import { useGestureHint } from '@/composables/useGestureHint'

const assetGesture = useGestureHint('asset-longpress', {
  target: '.asset-list-item:first-child',
  type: 'long-press-pulse',
})

const liabilityGesture = useGestureHint('liability-swipe', {
  target: '.liability-card:first-child',
  type: 'swipe-left',
})

// Trigger on tab change (in the tab change handler)
function onTabChange(tab: string) {
  if (tab === 'assets') assetGesture.trigger()
  if (tab === 'liabilities') liabilityGesture.trigger()
}
```

Add gesture animation CSS classes to the first list item when `played` is true (use a CSS class `.gesture-hint--pulse` / `.gesture-hint--swipe`).

- [ ] **Step 2: Add tooltip to AI Hub**

In `AIHubPage.vue`:

```ts
import { isGuideDone, markGuideDone } from '@/utils/storage'

const showAiTip = ref(false)

onMounted(() => {
  if (!isGuideDone('tip_ai-first')) {
    showAiTip.value = true
    setTimeout(() => {
      showAiTip.value = false
      markGuideDone('tip_ai-first')
    }, 3000)
  }
})

function dismissTip() {
  showAiTip.value = false
  markGuideDone('tip_ai-first')
}
```

Add tooltip template (use Vant `van-popover` or a simple positioned div with `pointer-events: none`).

- [ ] **Step 3: Add tooltip to Settings**

In `SettingsPage.vue`:

```ts
const showInviteTip = ref(false)

onMounted(async () => {
  if (isGuideDone('tip_settings-invite')) return
  // Check owner + no family members
  if (authStore.user?.role !== 'owner') return
  const members = await familyApi.getMembers()
  if (members.data.length > 1) return

  showInviteTip.value = true
  setTimeout(() => {
    showInviteTip.value = false
    markGuideDone('tip_settings-invite')
  }, 3000)
})
```

- [ ] **Step 4: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/FinanceHubPage.vue frontend/apps/main/src/pages/AIHubPage.vue frontend/apps/main/src/pages/SettingsPage.vue
git commit -m "feat(stepguide): add gesture hints to FinanceHub and tooltips to AI/Settings

long-press pulse on first asset, swipe-left hint on first liability, AI Hub first-visit tip, Settings invite tip"
```

---

### Task 8: Settings "Replay Onboarding" Entry

**Files:**
- Modify: `frontend/apps/main/src/pages/SettingsPage.vue`

**Interfaces:**
- Consumes: `clearAllGuideKeys` from `@/utils/storage`

- [ ] **Step 1: Add replay cell to Settings**

```vue
<!-- Add before the "about" section -->
<van-cell
  :title="t('settings.replayOnboarding')"
  is-link
  @click="onReplayOnboarding"
/>
```

```ts
import { clearAllGuideKeys } from '@/utils/storage'
import { useRouter } from 'vue-router'

const router = useRouter()

function onReplayOnboarding() {
  clearAllGuideKeys()
  router.push('/')
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/pages/SettingsPage.vue
git commit -m "feat(stepguide): add 'Replay onboarding' entry to Settings

Clears all guide/gesture/tip keys and navigates to Dashboard to re-trigger onboarding"
```

---

### Task 9: Child App Onboarding

**Files:**
- Create: `frontend/apps/child/src/composables/useStepGuide.ts`
- Create: `frontend/apps/child/src/components/common/StepGuideOverlay.vue`
- Modify: `frontend/apps/child/src/pages/ChildTasksPage.vue`
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts` (or child i18n file)
- Test: `frontend/apps/child/src/composables/__tests__/useStepGuide.spec.ts`

- [ ] **Step 1: Create child `useStepGuide.ts`**

Copy logic from main app's `useStepGuide.ts`. Child uses the same composable interface but may have different CSS variables (clay.css).

- [ ] **Step 2: Create child `StepGuideOverlay.vue`**

Based on main app's `StepGuideOverlay.vue` but with child styling:
- Larger border-radius (16px)
- Child primary colors
- Larger font for readability
- Mask color: `rgba(0, 0, 0, 0.6)`

- [ ] **Step 3: Integrate into ChildTasksPage**

```ts
import { useStepGuide } from '@/composables/useStepGuide'
import StepGuideOverlay from '@/components/common/StepGuideOverlay.vue'

const choreSteps = computed(() => {
  const hasChores = chores.value.length > 0
  return [
    {
      selector: '.chore-list, .empty-state',
      mode: 'spotlight' as const,
      title: hasChores ? t('childOnboarding.step1.data.title') : t('childOnboarding.step1.empty.title'),
      desc: hasChores ? t('childOnboarding.step1.data.desc') : t('childOnboarding.step1.empty.desc'),
    },
    {
      selector: '.balance-hero, .empty-state',
      mode: 'spotlight' as const,
      title: t('childOnboarding.step2.title'),
      desc: t('childOnboarding.step2.desc'),
    },
  ]
})

const guide = useStepGuide({
  key: 'guide_child-onboarding-v1',
  steps: choreSteps.value,
})

function maybeShowChildOnboarding() {
  guide.start()
}
```

- [ ] **Step 4: Add child i18n keys**

Add `childOnboarding` namespace to child app's i18n files (zh-CN + en-US).

- [ ] **Step 5: Run typecheck + tests for child app**

Run: `cd frontend/apps/child && pnpm typecheck && pnpm vitest run`
Expected: 0 errors, all tests pass

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/child/src/composables/useStepGuide.ts frontend/apps/child/src/composables/__tests__/useStepGuide.spec.ts frontend/apps/child/src/components/common/StepGuideOverlay.vue frontend/apps/child/src/pages/ChildTasksPage.vue frontend/apps/child/src/i18n/
git commit -m "feat(stepguide): add child app onboarding

2-step spotlight in ChildTasksPage (task list + rewards), clay.css styling, single-page constraint"
```

---

### Task 10: Final Verification + Cleanup

- [ ] **Step 1: Run full test suite**

```bash
cd frontend/apps/main && pnpm typecheck && pnpm vitest run
cd frontend/apps/child && pnpm typecheck && pnpm vitest run
```

Expected: 0 typecheck errors, all tests pass

- [ ] **Step 2: Run lint**

```bash
cd frontend && pnpm -r lint
```

Expected: 0 new errors

- [ ] **Step 3: Verify no dead code remains**

```bash
grep -rn "OnboardingOverlay" frontend/apps/main/src/ 2>/dev/null
grep -rn "onboarding_completed" frontend/apps/main/src/ 2>/dev/null | grep -v storage.ts
```

Expected: No references to old component or old key (except migration logic in storage.ts)

- [ ] **Step 4: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore(stepguide): final cleanup and verification"
```

---

## File Summary

| File | Action | Responsibility |
|------|--------|---------------|
| `main/src/utils/storage.ts` | Modify | Guide key lifecycle (clear/migrate/isDone/markDone) |
| `main/src/utils/__tests__/storage-guide.spec.ts` | Create | Storage helper tests |
| `main/src/composables/useStepGuide.ts` | Create | Core step guide composable |
| `main/src/composables/__tests__/useStepGuide.spec.ts` | Create | Composable tests |
| `main/src/composables/useGestureHint.ts` | Create | One-shot gesture trigger |
| `main/src/composables/__tests__/useGestureHint.spec.ts` | Create | Gesture hint tests |
| `main/src/components/common/StepGuideOverlay.vue` | Create | Spotlight/tooltip overlay UI |
| `main/src/components/common/__tests__/StepGuideOverlay.spec.ts` | Create | Overlay tests |
| `main/src/components/common/OnboardingOverlay.vue` | Delete | Legacy (replaced) |
| `main/src/components/common/AppTabBar.vue` | Modify | Add data-tab attributes |
| `main/src/i18n/locales/zh-CN.ts` | Modify | New i18n keys |
| `main/src/i18n/locales/en-US.ts` | Modify | New i18n keys |
| `main/src/pages/DashboardPage.vue` | Modify | Onboarding integration |
| `main/src/pages/FinanceHubPage.vue` | Modify | Gesture hints |
| `main/src/pages/AIHubPage.vue` | Modify | Tooltip |
| `main/src/pages/SettingsPage.vue` | Modify | Tooltip + replay entry |
| `child/src/composables/useStepGuide.ts` | Create | Child composable |
| `child/src/composables/__tests__/useStepGuide.spec.ts` | Create | Child tests |
| `child/src/components/common/StepGuideOverlay.vue` | Create | Child overlay (clay.css) |
| `child/src/pages/ChildTasksPage.vue` | Modify | Child onboarding integration |
| `child/src/i18n/locales/zh-CN.ts` | Modify | Child i18n keys |
