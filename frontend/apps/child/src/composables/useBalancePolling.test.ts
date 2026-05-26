import { describe, it, expect, beforeEach, vi } from 'vitest'

vi.mock('@/api/coins', () => ({
  getCoinBalance: vi.fn(),
}))

import { useBalancePolling, __resetBalancePollingForTests } from './useBalancePolling'
import { getCoinBalance } from '@/api/coins'
import { effectScope } from 'vue'

describe('useBalancePolling lastChange', () => {
  beforeEach(() => {
    __resetBalancePollingForTests()
    vi.clearAllMocks()
  })

  it('does not fire lastChange on the initial fetch (0 → first value)', async () => {
    vi.mocked(getCoinBalance).mockResolvedValueOnce(100)
    const scope = effectScope()
    let lastChangeRef: ReturnType<typeof useBalancePolling>['lastChange'] | null = null
    scope.run(() => {
      const { lastChange, refresh } = useBalancePolling({ enabled: false })
      lastChangeRef = lastChange
      return refresh()
    })
    await Promise.resolve()
    await Promise.resolve()
    expect(lastChangeRef!.value).toBeNull()
    scope.stop()
  })

  it('fires lastChange with from/to when balance value changes between fetches', async () => {
    vi.mocked(getCoinBalance)
      .mockResolvedValueOnce(100)
      .mockResolvedValueOnce(150)

    const scope = effectScope()
    const handle = scope.run(() => {
      const api = useBalancePolling({ enabled: false })
      return api
    })!
    await handle.refresh()
    expect(handle.lastChange.value).toBeNull()
    await handle.refresh()
    expect(handle.lastChange.value).not.toBeNull()
    expect(handle.lastChange.value!.from).toBe(100)
    expect(handle.lastChange.value!.to).toBe(150)
    scope.stop()
  })

  it('does not fire when polled value is identical to previous', async () => {
    vi.mocked(getCoinBalance)
      .mockResolvedValueOnce(100)
      .mockResolvedValueOnce(100)
      .mockResolvedValueOnce(100)

    const scope = effectScope()
    const handle = scope.run(() => useBalancePolling({ enabled: false }))!
    await handle.refresh()
    await handle.refresh()
    await handle.refresh()
    expect(handle.lastChange.value).toBeNull()
    scope.stop()
  })
})

describe('useBalancePolling visibility listener cleanup', () => {
  beforeEach(() => {
    __resetBalancePollingForTests()
    vi.clearAllMocks()
  })

  it('removes visibilitychange listener when last consumer stops', async () => {
    vi.mocked(getCoinBalance).mockResolvedValue(100)

    const addSpy = vi.spyOn(document, 'addEventListener')
    const removeSpy = vi.spyOn(document, 'removeEventListener')

    const scope = effectScope()
    const handle = scope.run(() => useBalancePolling({ enabled: false }))!
    handle.start()
    handle.stop()

    const addedHandler = addSpy.mock.calls.find((c) => c[0] === 'visibilitychange')?.[1]
    const removedHandler = removeSpy.mock.calls.find((c) => c[0] === 'visibilitychange')?.[1]

    expect(addedHandler).toBeDefined()
    expect(removedHandler).toBe(addedHandler)

    scope.stop()
    addSpy.mockRestore()
    removeSpy.mockRestore()
  })
})
