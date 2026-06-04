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

  // Clear timer when conditions no longer permit auto-collapse
  function checkAndClearTimer() {
    if (!autoCollapseSignal.value || status.value !== 'done' || hasAutoCollapsed.value) {
      clearTimer()
    }
  }

  // Watch signal changes
  watch(
    autoCollapseSignal,
    (signal) => {
      if (signal && status.value === 'done' && !hasAutoCollapsed.value) {
        clearTimer()
        timer = setTimeout(() => {
          // Re-check conditions before collapsing (status/signal may have changed)
          if (autoCollapseSignal.value && status.value === 'done' && !hasAutoCollapsed.value) {
            isExpanded.value = false
            hasAutoCollapsed.value = true
          }
          timer = null
        }, 1000)
      } else {
        // Signal became false or other condition changed — clear pending timer
        checkAndClearTimer()
      }
    },
    { flush: 'sync' },
  )

  // Watch status changes to clear timer when status moves away from 'done'
  watch(
    status,
    () => {
      checkAndClearTimer()
    },
    { flush: 'sync' },
  )

  onScopeDispose(() => {
    clearTimer()
  })

  return { isExpanded, toggle, hasAutoCollapsed }
}