// frontend/apps/child/src/composables/useStepGuide.ts
import { ref, type Ref } from 'vue'

export interface StepGuideStep {
  selector: string
  mode: 'spotlight' | 'tooltip' | 'gesture-hint'
  title?: string
  desc?: string
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
    if (currentStep.value < steps.length - 1) {
      currentStep.value++
    }
  }

  return { isActive, currentStep, steps, start, skip, complete, next }
}
