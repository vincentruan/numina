import { onScopeDispose, ref, watch, type Ref } from 'vue'

export interface UseStepCollapseOptions {
  defaultExpanded: boolean
  autoCollapseSignal: Ref<boolean>
  status: Ref<string>
}

export function useStepCollapse(options: UseStepCollapseOptions) {
  const { defaultExpanded, autoCollapseSignal, status } = options

  const isExpanded = ref(defaultExpanded)
  const hasAutoCollapsed = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  function clearTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function toggle() {
    clearTimer()
    hasAutoCollapsed.value = true
    isExpanded.value = !isExpanded.value
  }

  watch(
    autoCollapseSignal,
    (signal) => {
      if (signal && status.value === 'done' && !hasAutoCollapsed.value) {
        clearTimer()
        timer = setTimeout(() => {
          isExpanded.value = false
          hasAutoCollapsed.value = true
          timer = null
        }, 1000)
      }
    },
    { flush: 'sync' },
  )

  onScopeDispose(() => {
    clearTimer()
  })

  return { isExpanded, toggle, hasAutoCollapsed }
}
