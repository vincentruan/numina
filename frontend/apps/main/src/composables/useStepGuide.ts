// frontend/apps/main/src/composables/useStepGuide.ts
import { ref, computed, type Ref, type ComputedRef } from 'vue'
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
  steps: StepGuideStep[] | Ref<StepGuideStep[]> | ComputedRef<StepGuideStep[]>
  onComplete?: () => void
  onSkip?: () => void
}

export interface UseStepGuideReturn {
  isActive: Ref<boolean>
  currentStep: Ref<number>
  steps: ComputedRef<StepGuideStep[]>
  start: () => void
  skip: () => void
  complete: () => void
  next: () => void
}

export function useStepGuide(options: UseStepGuideOptions): UseStepGuideReturn {
  const { key, onComplete, onSkip } = options
  const isActive = ref(false)
  const currentStep = ref(0)

  // Accept plain array, Ref, or ComputedRef — normalize to ComputedRef
  const steps = computed(() => {
    const raw = options.steps
    return 'value' in raw ? raw.value : raw
  })

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
    if (currentStep.value < steps.value.length - 1) {
      currentStep.value++
    }
  }

  return { isActive, currentStep, steps, start, skip, complete, next }
}
