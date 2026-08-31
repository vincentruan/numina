import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useTaskResume } from '../useTaskResume'
import type { AITask } from '@/api/ai-tasks'

// Mock the api module with hoisted functions
const { mockGetAITasks, mockSubscribeTaskStream, mockGetTaskById, mockCancelTaskById } =
  vi.hoisted(() => ({
    mockGetAITasks: vi.fn(),
    mockSubscribeTaskStream: vi.fn(),
    mockGetTaskById: vi.fn(),
    mockCancelTaskById: vi.fn(),
  }))

vi.mock('@/api/ai-tasks', () => ({
  getAITasks: (...args: unknown[]) => mockGetAITasks(...args),
  subscribeTaskStream: (...args: unknown[]) => mockSubscribeTaskStream(...args),
  getTaskById: (...args: unknown[]) => mockGetTaskById(...args),
  cancelTaskById: (...args: unknown[]) => mockCancelTaskById(...args),
}))

function makeTask(overrides: Partial<AITask> = {}): AITask {
  return {
    id: '123',
    family_id: '1',
    skill_id: 'narrative',
    status: 'running',
    started_at: new Date().toISOString(), // default to "now" — fresh task, not stale
    ...overrides,
  }
}

describe('useTaskResume — retry flow (T20)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockGetAITasks.mockReset()
    mockSubscribeTaskStream.mockReset()
    mockGetTaskById.mockReset()
    mockCancelTaskById.mockReset()
    // Default: no task
    mockGetAITasks.mockResolvedValue([])
    // subscribeTaskStream returns an abort handle
    mockSubscribeTaskStream.mockReturnValue({ abort: vi.fn() })
    mockGetTaskById.mockResolvedValue(makeTask({ status: 'running' }))
    mockCancelTaskById.mockResolvedValue({ ok: true, status: 'cancelled', task_id: '123' })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('waitForTask finds a running task and clears triggerFailed', async () => {
    const resume = useTaskResume('narrative')
    // Task appears on the 2nd attempt
    mockGetAITasks
      .mockResolvedValueOnce([]) // attempt 1 (500ms)
      .mockResolvedValueOnce([makeTask({ id: 'task-1', status: 'running' })])

    const promise = resume.waitForTask()

    await vi.advanceTimersByTimeAsync(500)
    await vi.advanceTimersByTimeAsync(1000)

    const task = await promise
    expect(task?.id).toBe('task-1')
    expect(resume.taskId.value).toBe('task-1')
    expect(resume.triggerFailed.value).toBe(false)
  })

  it('waitForTask sets triggerFailed=true after exhausting all retries', async () => {
    const resume = useTaskResume('narrative')
    mockGetAITasks.mockResolvedValue([]) // never finds a task

    const promise = resume.waitForTask()

    await vi.advanceTimersByTimeAsync(500)
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(2000)
    await vi.advanceTimersByTimeAsync(4000)

    const task = await promise
    expect(task).toBeNull()
    expect(resume.triggerFailed.value).toBe(true)
    expect(resume.taskId.value).toBeNull()
  })

  it('retryTrigger reuses a late-appearing running task', async () => {
    const resume = useTaskResume('narrative')
    resume.triggerFailed.value = true

    mockGetAITasks.mockResolvedValueOnce([makeTask({ id: 'task-late', status: 'running' })])

    const reused = await resume.retryTrigger()

    expect(reused).toBe(true)
    expect(resume.triggerFailed.value).toBe(false)
    expect(resume.taskId.value).toBe('task-late')
    expect(mockSubscribeTaskStream).toHaveBeenCalled()
  })

  it('retryTrigger reuses a completed task without SSE', async () => {
    const resume = useTaskResume('narrative')
    resume.triggerFailed.value = true

    mockGetAITasks.mockResolvedValueOnce([makeTask({ id: 'task-done', status: 'completed' })])

    const reused = await resume.retryTrigger()

    expect(reused).toBe(true)
    expect(resume.triggerFailed.value).toBe(false)
    expect(mockSubscribeTaskStream).not.toHaveBeenCalled()
  })

  it('retryTrigger returns false when no reusable task (caller re-triggers)', async () => {
    const resume = useTaskResume('narrative')
    resume.triggerFailed.value = true

    mockGetAITasks.mockResolvedValueOnce([])

    const reused = await resume.retryTrigger()

    expect(reused).toBe(false)
    expect(resume.triggerFailed.value).toBe(true) // stays failed
    expect(mockSubscribeTaskStream).not.toHaveBeenCalled()
  })
})

describe('useTaskResume — resume() SSE path', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockGetAITasks.mockReset()
    mockSubscribeTaskStream.mockReset()
    mockGetTaskById.mockReset()
    mockCancelTaskById.mockReset()
    mockSubscribeTaskStream.mockReturnValue({ abort: vi.fn() })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('resume() finds a running task and starts SSE', async () => {
    const onComplete = vi.fn()
    const resume = useTaskResume('narrative', { onComplete })

    mockGetAITasks.mockResolvedValueOnce([makeTask({ id: 'task-running', status: 'running' })])

    const resumed = await resume.resume()

    expect(resumed).toBe(true)
    expect(resume.taskId.value).toBe('task-running')
    expect(resume.status.value).toBe('connecting')
    expect(mockSubscribeTaskStream).toHaveBeenCalledWith(
      'task-running',
      expect.objectContaining({ onEvent: expect.any(Function) }),
    )
  })

  it('resume() finds a completed task and calls onComplete', async () => {
    const onComplete = vi.fn()
    const resume = useTaskResume('narrative', { onComplete })

    mockGetAITasks.mockResolvedValueOnce([makeTask({ id: 'task-done', status: 'completed' })])

    const resumed = await resume.resume()

    expect(resumed).toBe(false)
    expect(resume.status.value).toBe('completed')
    expect(onComplete).toHaveBeenCalledWith(expect.objectContaining({ id: 'task-done' }))
    expect(mockSubscribeTaskStream).not.toHaveBeenCalled()
  })

  it('resume() returns false when no running task', async () => {
    const resume = useTaskResume('narrative')

    mockGetAITasks.mockResolvedValueOnce([])

    const resumed = await resume.resume()

    expect(resumed).toBe(false)
    expect(resume.taskId.value).toBeNull()
    expect(mockSubscribeTaskStream).not.toHaveBeenCalled()
  })

  it('disconnect() aborts SSE stream and stops polling but preserves state', async () => {
    const resume = useTaskResume('narrative')
    const mockAbort = vi.fn()

    mockGetAITasks.mockResolvedValueOnce([makeTask({ id: 'task-1', status: 'running' })])
    mockSubscribeTaskStream.mockReturnValue({ abort: mockAbort })

    await resume.resume()
    expect(mockSubscribeTaskStream).toHaveBeenCalled()

    resume.disconnect()

    expect(mockAbort).toHaveBeenCalled()
    // v3 fix: disconnect() preserves taskId and status for resume on re-entry
    expect(resume.taskId.value).toBe('task-1')
    expect(resume.status.value).toBe('connecting')
  })

  it('cleanup() aborts SSE stream, stops polling, AND resets state', async () => {
    const resume = useTaskResume('narrative')
    const mockAbort = vi.fn()

    mockGetAITasks.mockResolvedValueOnce([makeTask({ id: 'task-1', status: 'running' })])
    mockSubscribeTaskStream.mockReturnValue({ abort: mockAbort })

    await resume.resume()
    expect(mockSubscribeTaskStream).toHaveBeenCalled()

    resume.cleanup()

    expect(mockAbort).toHaveBeenCalled()
    expect(resume.taskId.value).toBeNull()
    expect(resume.status.value).toBe('idle')
  })
})
