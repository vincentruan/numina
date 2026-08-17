import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useTaskPolling } from '../useTaskPolling'
import type { AITask } from '@/api/ai-tasks'

// Create mock inside vi.hoisted() so it's available in the vi.mock factory
const { mockGetTaskById, mockCancelTaskById } = vi.hoisted(() => ({
  mockGetTaskById: vi.fn(),
  mockCancelTaskById: vi.fn(),
}))

vi.mock('@/api/ai-tasks', () => ({
  getTaskById: mockGetTaskById,
  cancelTaskById: mockCancelTaskById,
}))

function makeTask(overrides: Partial<AITask> = {}): AITask {
  return {
    id: '123',
    family_id: '1',
    skill_id: 'coach',
    status: 'running',
    started_at: '2026-08-16T00:00:00+00:00',
    ...overrides,
  }
}

describe('useTaskPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockGetTaskById.mockReset()
    mockCancelTaskById.mockReset()
    // Default: document visible
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('scenario 7: taskId null → no polling starts', () => {
    const taskId = ref<string | null>(null)
    const { status } = useTaskPolling(taskId)

    expect(status.value).toBe('idle')
    expect(mockGetTaskById).not.toHaveBeenCalled()
  })

  it('scenario 1: taskId set to non-null → starts polling (2s interval)', async () => {
    const taskId = ref<string | null>(null)
    mockGetTaskById.mockResolvedValue(makeTask({ status: 'running' }))

    useTaskPolling(taskId, { interval: 2000 })

    // Set taskId → immediate poll
    taskId.value = '123'
    await nextTick()
    // Flush microtasks for the immediate poll
    await vi.advanceTimersByTimeAsync(0)
    expect(mockGetTaskById).toHaveBeenCalledWith('123')

    // Advance 2s → second poll
    await vi.advanceTimersByTimeAsync(2000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(2)
  })

  it('scenario 2: status=completed → stops polling, calls onComplete', async () => {
    const taskId = ref<string | null>('123')
    const onComplete = vi.fn()
    const completedTask = makeTask({ status: 'completed' })
    mockGetTaskById.mockResolvedValue(completedTask)

    const { status } = useTaskPolling(taskId, { onComplete })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    expect(status.value).toBe('completed')
    expect(onComplete).toHaveBeenCalledWith(completedTask)

    // Advance time — no more polls after completion
    const callCount = mockGetTaskById.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(callCount)
  })

  it('scenario 3: status=failed → stops polling, calls onError', async () => {
    const taskId = ref<string | null>('123')
    const onError = vi.fn()
    const failedTask = makeTask({ status: 'failed', error_message: '服务异常' })
    mockGetTaskById.mockResolvedValue(failedTask)

    const { status, errorMessage } = useTaskPolling(taskId, { onError })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    expect(status.value).toBe('failed')
    expect(errorMessage.value).toBe('服务异常')
    expect(onError).toHaveBeenCalledWith(failedTask)

    // No more polls after failure
    const callCount = mockGetTaskById.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(callCount)
  })

  it('scenario 4: document.hidden → pauses polling', async () => {
    const taskId = ref<string | null>('123')
    mockGetTaskById.mockResolvedValue(makeTask({ status: 'running' }))

    const { paused } = useTaskPolling(taskId, { interval: 2000 })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    // Simulate document hidden
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await nextTick()

    expect(paused.value).toBe(true)

    // Advance — polls should not fire while hidden (interval fires but skips)
    const callCount = mockGetTaskById.mock.calls.length
    await vi.advanceTimersByTimeAsync(6000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(callCount)
  })

  it('scenario 5: document becomes visible again → resumes polling', async () => {
    const taskId = ref<string | null>('123')
    mockGetTaskById.mockResolvedValue(makeTask({ status: 'running' }))

    const { paused } = useTaskPolling(taskId, { interval: 2000 })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    // Hide
    Object.defineProperty(document, 'hidden', { value: true, configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await nextTick()
    expect(paused.value).toBe(true)

    // Show again
    Object.defineProperty(document, 'hidden', { value: false, configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await nextTick()

    expect(paused.value).toBe(false)
    // Immediate poll on resume
    await vi.advanceTimersByTimeAsync(0)
    const callCountAfterResume = mockGetTaskById.mock.calls.length
    expect(callCountAfterResume).toBeGreaterThan(1)
  })

  it('scenario 6: stop() → polling stops, no memory leak', async () => {
    const taskId = ref<string | null>('123')
    mockGetTaskById.mockResolvedValue(makeTask({ status: 'running' }))

    const { stop, status } = useTaskPolling(taskId, { interval: 2000 })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)
    expect(status.value).toBe('polling')

    stop()
    expect(status.value).toBe('idle')

    // Advance — no more polls
    const callCount = mockGetTaskById.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(callCount)
  })

  it('handles network error gracefully — continues polling', async () => {
    const taskId = ref<string | null>('123')
    // First poll fails
    mockGetTaskById.mockRejectedValueOnce(new Error('Network error'))

    const { status } = useTaskPolling(taskId, { interval: 2000 })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    // Status remains 'polling' after a network error
    expect(status.value).toBe('polling')

    // Next poll succeeds
    mockGetTaskById.mockResolvedValueOnce(makeTask({ status: 'running' }))
    await vi.advanceTimersByTimeAsync(2000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(2)
  })

  it('timeout/cancelled statuses are also terminal', async () => {
    const taskId = ref<string | null>('123')
    mockGetTaskById.mockResolvedValue(makeTask({ status: 'timeout' }))

    const { status } = useTaskPolling(taskId)

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    expect(status.value).toBe('failed')
  })

  it('T18: 404 -> stops polling silently with empty errorMessage', async () => {
    const taskId = ref<string | null>('123')
    const onError = vi.fn()
    // Axios-style error with response.status 404
    mockGetTaskById.mockRejectedValueOnce({ response: { status: 404 } })

    const { status, errorMessage } = useTaskPolling(taskId, { onError })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    expect(status.value).toBe('failed')
    // Silent: no error message (no toast), no onError callback
    expect(errorMessage.value).toBe('')
    expect(onError).not.toHaveBeenCalled()

    // No more polls after 404
    await vi.advanceTimersByTimeAsync(10000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(1)
  })

  it('T18: 500 error -> keeps polling (not silent-stopped)', async () => {
    const taskId = ref<string | null>('123')
    mockGetTaskById.mockRejectedValueOnce({ response: { status: 500 } })

    const { status } = useTaskPolling(taskId, { interval: 2000 })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)

    // Transient server error does not stop polling
    expect(status.value).toBe('polling')

    mockGetTaskById.mockResolvedValueOnce(makeTask({ status: 'running' }))
    await vi.advanceTimersByTimeAsync(2000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(2)
  })

  it('cancel() → calls cancelTaskById, stops polling, sets failed', async () => {
    const taskId = ref<string | null>('123')
    mockGetTaskById.mockResolvedValue(makeTask({ status: 'running' }))
    mockCancelTaskById.mockResolvedValue({ ok: true, status: 'cancelled', task_id: '123' })

    const { cancel, status, errorMessage } = useTaskPolling(taskId, { interval: 2000 })

    await nextTick()
    await vi.advanceTimersByTimeAsync(0)
    expect(status.value).toBe('polling')

    await cancel()

    expect(mockCancelTaskById).toHaveBeenCalledWith('123')
    expect(status.value).toBe('failed')
    // Aligns with i18n key `aiTask.cancelled` (任务已终止) — the original
    // hardcoded '任务已取消' was inconsistent with the canonical i18n value.
    expect(errorMessage.value).toBe('任务已终止')

    // No more polls after cancel
    const callCount = mockGetTaskById.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(mockGetTaskById).toHaveBeenCalledTimes(callCount)
  })
})
