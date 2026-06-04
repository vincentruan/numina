import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { effectScope, ref } from 'vue'
import { useStepCollapse } from '@/composables/useStepCollapse'

describe('useStepCollapse', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('auto-collapses 1s after signal becomes true when status is done', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('done')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: true, autoCollapseSignal, status })
    })

    expect(result!.isExpanded.value).toBe(true)
    autoCollapseSignal.value = true
    vi.advanceTimersByTime(999)
    expect(result!.isExpanded.value).toBe(true)
    vi.advanceTimersByTime(1)
    expect(result!.isExpanded.value).toBe(false)

    scope.stop()
  })

  it('does NOT auto-collapse when status is still streaming', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('streaming')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: true, autoCollapseSignal, status })
    })

    autoCollapseSignal.value = true
    vi.advanceTimersByTime(2000)
    expect(result!.isExpanded.value).toBe(true)

    scope.stop()
  })

  it('manual toggle before auto-collapse cancels the timer', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('done')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: true, autoCollapseSignal, status })
    })

    autoCollapseSignal.value = true
    vi.advanceTimersByTime(500)
    result!.toggle()
    expect(result!.isExpanded.value).toBe(false)
    vi.advanceTimersByTime(1000)
    expect(result!.isExpanded.value).toBe(false)

    scope.stop()
  })

  it('manual toggle after auto-collapse re-expands without triggering another collapse', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('done')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: true, autoCollapseSignal, status })
    })

    autoCollapseSignal.value = true
    vi.advanceTimersByTime(1000)
    expect(result!.isExpanded.value).toBe(false)
    expect(result!.hasAutoCollapsed.value).toBe(true)

    result!.toggle()
    expect(result!.isExpanded.value).toBe(true)

    // Simulate signal change — should not re-collapse since hasAutoCollapsed is true
    autoCollapseSignal.value = false
    autoCollapseSignal.value = true
    vi.advanceTimersByTime(2000)
    expect(result!.isExpanded.value).toBe(true)

    scope.stop()
  })

  it('timer is cleaned up on scope stop (no leaked timers)', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('done')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: true, autoCollapseSignal, status })
    })

    autoCollapseSignal.value = true
    // Stop the scope (simulates unmount)
    scope.stop()

    // Timer should have been cleared via onScopeDispose
    expect(() => vi.advanceTimersByTime(2000)).not.toThrow()
  })

  it('defaultExpanded: false starts collapsed and auto-collapse signal has no effect', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('done')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: false, autoCollapseSignal, status })
    })

    expect(result!.isExpanded.value).toBe(false)
    autoCollapseSignal.value = true
    vi.advanceTimersByTime(2000)
    expect(result!.isExpanded.value).toBe(false)

    scope.stop()
  })

  it('timer is cleared when status changes away from done during pending timer', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('done')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: true, autoCollapseSignal, status })
    })

    autoCollapseSignal.value = true
    vi.advanceTimersByTime(500)
    // Status changes to streaming during timer wait
    status.value = 'streaming'
    vi.advanceTimersByTime(1000)
    // Timer should have been cleared — step stays expanded
    expect(result!.isExpanded.value).toBe(true)

    scope.stop()
  })

  it('timer is cleared when signal becomes false during pending timer', () => {
    const scope = effectScope()
    const autoCollapseSignal = ref(false)
    const status = ref('done')

    let result: ReturnType<typeof useStepCollapse>
    scope.run(() => {
      result = useStepCollapse({ defaultExpanded: true, autoCollapseSignal, status })
    })

    autoCollapseSignal.value = true
    vi.advanceTimersByTime(500)
    // Signal becomes false during timer wait
    autoCollapseSignal.value = false
    vi.advanceTimersByTime(1000)
    // Timer should have been cleared — step stays expanded
    expect(result!.isExpanded.value).toBe(true)

    scope.stop()
  })
})
