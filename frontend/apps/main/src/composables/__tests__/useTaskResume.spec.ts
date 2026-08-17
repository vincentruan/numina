import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
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
    started_at: '2026-08-16T00:00:00+00:00',
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
