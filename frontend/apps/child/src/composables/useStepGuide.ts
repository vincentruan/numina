// frontend/apps/child/src/composables/useStepGuide.ts
import { ref, computed, type Ref, type ComputedRef } from 'vue'

export interface StepGuideStep {
  selector: string
  mode: 'spotlight' | 'tooltip' | 'gesture-hint'
  title?: string
  desc?: string
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

  const steps = computed(() => {
    const raw = options.steps
    return 'value' in raw ? raw.value : raw
  })

  function start() {
    if (localStorage.getItem(key) === 'done') return
    currentStep.value = 0
    isActive.value = true
  }

  function skip() {
    isActive.value = false
    localStorage.setItem(key, 'done')
    onSkip?.()
  }

  function complete() {
    isActive.value = false
    localStorage.setItem(key, 'done')
    onComplete?.()
  }

  function next() {
    if (currentStep.value < steps.value.length - 1) {
      currentStep.value++
    }
  }

  return { isActive, currentStep, steps, start, skip, complete, next }
}
