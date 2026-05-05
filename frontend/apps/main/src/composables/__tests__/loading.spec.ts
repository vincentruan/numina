import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Isolate the module singleton between tests ────────────────────────────────
// Each test re-imports a fresh module instance via vi.isolateModules

async function freshComposable() {
  const mod = await import(
    /* @vite-ignore */ '../../../../../../packages/auth/src/composables/loading.ts'
  )
  return mod.useLoadingOverlay()
}

describe('useLoadingOverlay', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.resetModules()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.resetModules()
  })

  it('并发请求计数正确', async () => {
    const { increment, decrement, isLoading } = await freshComposable()

    // Start 5 concurrent requests
    for (let i = 0; i < 5; i++) increment()

    // Advance past debounce so loading becomes visible
    vi.advanceTimersByTime(250)
    expect(isLoading.value).toBe(true)

    // Complete 4 of 5 — still loading
    for (let i = 0; i < 4; i++) decrement()
    vi.advanceTimersByTime(500)
    expect(isLoading.value).toBe(true)

    // Complete last one — loading closes after min display time
    decrement()
    vi.advanceTimersByTime(500)
    expect(isLoading.value).toBe(false)
  })

  it('快速请求不闪烁 (< 200ms debounce)', async () => {
    const { increment, decrement, isLoading } = await freshComposable()

    increment()
    // Complete before debounce fires (200ms)
    vi.advanceTimersByTime(100)
    decrement()

    // Advance well past debounce — loading should never have shown
    vi.advanceTimersByTime(500)
    expect(isLoading.value).toBe(false)
  })

  it('异常请求正确关闭', async () => {
    const { increment, decrement, isLoading } = await freshComposable()

    increment()
    vi.advanceTimersByTime(250) // past debounce
    expect(isLoading.value).toBe(true)

    // Simulate rejected request — decrement must still be called
    decrement()
    vi.advanceTimersByTime(500)
    expect(isLoading.value).toBe(false)
  })

  it('最小展示时间 400ms', async () => {
    const { increment, decrement, isLoading } = await freshComposable()

    increment()
    vi.advanceTimersByTime(250) // past debounce → now visible
    expect(isLoading.value).toBe(true)

    // Request finishes after only 50ms of being visible
    vi.advanceTimersByTime(50)
    decrement()

    // Should still be visible — min display not elapsed
    vi.advanceTimersByTime(200)
    expect(isLoading.value).toBe(true)

    // After full 400ms min display, should close
    vi.advanceTimersByTime(300)
    expect(isLoading.value).toBe(false)
  })

  it('watchdog 30s 兜底强制关闭', async () => {
    const { increment, isLoading } = await freshComposable()

    // Simulate a stuck request — increment but never decrement
    increment()
    vi.advanceTimersByTime(250) // past debounce
    expect(isLoading.value).toBe(true)

    // Advance to just before watchdog
    vi.advanceTimersByTime(29_800)
    expect(isLoading.value).toBe(true)

    // Watchdog fires at 30s
    vi.advanceTimersByTime(300)
    expect(isLoading.value).toBe(false)
  })

  it('dismiss 动画触发：关闭时 isDismissing=true', async () => {
    const { increment, decrement, isLoading, isDismissing } = await freshComposable()

    increment()
    vi.advanceTimersByTime(250)
    expect(isLoading.value).toBe(true)

    decrement()

    // isDismissing should be true immediately after decrement
    expect(isDismissing.value).toBe(true)

    // After min display time, overlay closes and dismissing resets
    vi.advanceTimersByTime(500)
    expect(isLoading.value).toBe(false)
    expect(isDismissing.value).toBe(false)
  })
})
