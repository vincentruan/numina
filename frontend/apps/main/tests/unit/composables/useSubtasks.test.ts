/**
 * useSubtasks.ts unit tests — DeerFlow subagent task lifecycle parity
 *
 * 参考: frontend/src/core/tasks/context.tsx
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { useSubtasks, useSubtask, useUpdateSubtask } from '@/composables/ai-chat/useSubtasks'
import { EVENT_STATUS_MAP } from '@/types/ai-chat/subtask'

describe('EVENT_STATUS_MAP', () => {
  it('maps task_started to in_progress', () => {
    expect(EVENT_STATUS_MAP.task_started).toBe('in_progress')
  })

  it('maps task_completed to completed', () => {
    expect(EVENT_STATUS_MAP.task_completed).toBe('completed')
  })

  it('maps task_failed to failed', () => {
    expect(EVENT_STATUS_MAP.task_failed).toBe('failed')
  })

  it('maps task_timed_out to timed_out', () => {
    expect(EVENT_STATUS_MAP.task_timed_out).toBe('timed_out')
  })

  it('maps task_cancelled to cancelled', () => {
    expect(EVENT_STATUS_MAP.task_cancelled).toBe('cancelled')
  })

  it('maps task_running to in_progress', () => {
    expect(EVENT_STATUS_MAP.task_running).toBe('in_progress')
  })
})

describe('useSubtasks', () => {
  beforeEach(() => {
    // Clear global state
    const { clearSubtasks } = useUpdateSubtask()
    clearSubtasks()
  })

  describe('tasks and taskList', () => {
    it('returns empty dict initially', () => {
      const { tasks, taskList } = useSubtasks()

      expect(Object.keys(tasks.value)).toEqual([])
      expect(taskList.value).toEqual([])
    })

    it('taskList returns all subtasks as array', async () => {
      const { updateSubtask } = useUpdateSubtask()
      const { taskList } = useSubtasks()

      updateSubtask({ id: 'task-1', status: 'in_progress', description: 'Task 1' })
      updateSubtask({ id: 'task-2', status: 'completed', description: 'Task 2' })
      await nextTick()

      expect(taskList.value.length).toBe(2)
    })
  })

  describe('inProgressCount', () => {
    it('counts only in_progress tasks', async () => {
      const { updateSubtask } = useUpdateSubtask()
      const { inProgressCount } = useSubtasks()

      updateSubtask({ id: 'task-1', status: 'in_progress' })
      updateSubtask({ id: 'task-2', status: 'completed' })
      updateSubtask({ id: 'task-3', status: 'in_progress' })
      await nextTick()

      expect(inProgressCount.value).toBe(2)
    })
  })
})

describe('useSubtask', () => {
  beforeEach(() => {
    const { clearSubtasks } = useUpdateSubtask()
    clearSubtasks()
  })

  it('returns undefined for unknown taskId', () => {
    const task = useSubtask('unknown')
    expect(task.value).toBeUndefined()
  })

  it('returns subtask by taskId', async () => {
    const { updateSubtask } = useUpdateSubtask()

    updateSubtask({ id: 'task-1', status: 'in_progress', description: 'Task 1' })
    await nextTick()

    const task = useSubtask('task-1')
    expect(task.value?.description).toBe('Task 1')
  })
})

describe('useUpdateSubtask', () => {
  beforeEach(() => {
    const { clearSubtasks } = useUpdateSubtask()
    clearSubtasks()
  })

  describe('updateSubtask', () => {
    it('creates new subtask', async () => {
      const { updateSubtask } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      updateSubtask({
        id: 'task-1',
        status: 'in_progress',
        description: 'New task',
      })
      await nextTick()

      expect(tasks.value['task-1']).toEqual({
        id: 'task-1',
        status: 'in_progress',
        description: 'New task',
      })
    })

    it('updates existing subtask (merge)', async () => {
      const { updateSubtask } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      updateSubtask({ id: 'task-1', status: 'in_progress', description: 'Initial' })
      await nextTick()

      updateSubtask({ id: 'task-1', status: 'completed', result: 'Done' })
      await nextTick()

      expect(tasks.value['task-1']).toEqual({
        id: 'task-1',
        status: 'completed',
        description: 'Initial',
        result: 'Done',
      })
    })
  })

  describe('handleTaskEvent', () => {
    it('handles DeerFlow task_started event', async () => {
      const { handleTaskEvent } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleTaskEvent({
        type: 'task_started',
        task_id: 'task-1',
        description: 'Starting task',
        prompt: 'Do something',
      })
      await nextTick()

      expect(tasks.value['task-1'].status).toBe('in_progress')
      expect(tasks.value['task-1'].description).toBe('Starting task')
    })

    it('handles DeerFlow task_completed event', async () => {
      const { handleTaskEvent } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      // Start first
      handleTaskEvent({ type: 'task_started', task_id: 'task-1' })
      await nextTick()

      handleTaskEvent({
        type: 'task_completed',
        task_id: 'task-1',
        result: 'Task done',
        usage: { input_tokens: 100, output_tokens: 50, total_tokens: 150 },
      })
      await nextTick()

      expect(tasks.value['task-1'].status).toBe('completed')
      expect(tasks.value['task-1'].result).toBe('Task done')
      expect(tasks.value['task-1'].usage?.total_tokens).toBe(150)
    })

    it('handles task_failed event', async () => {
      const { handleTaskEvent } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleTaskEvent({
        type: 'task_failed',
        task_id: 'task-1',
        error: 'Something went wrong',
      })
      await nextTick()

      expect(tasks.value['task-1'].status).toBe('failed')
      expect(tasks.value['task-1'].error).toBe('Something went wrong')
    })

    it('handles taskId alias (Numina format)', async () => {
      const { handleTaskEvent } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleTaskEvent({
        type: 'task_started',
        taskId: 'task-alias', // Numina uses taskId
        description: 'Alias test',
      })
      await nextTick()

      expect(tasks.value['task-alias']).toBeDefined()
    })

    it('ignores event without task_id', async () => {
      const { handleTaskEvent } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleTaskEvent({ type: 'task_started' }) // no task_id
      await nextTick()

      expect(Object.keys(tasks.value)).toEqual([])
    })
  })

  describe('handleSubagentUpdate', () => {
    it('handles Numina subagent.update with running status', async () => {
      const { handleSubagentUpdate } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleSubagentUpdate({
        subagent: {
          taskId: 'task-1',
          status: 'running',
          title: 'Processing',
        },
      })
      await nextTick()

      expect(tasks.value['task-1'].status).toBe('in_progress')
      expect(tasks.value['task-1'].description).toBe('Processing')
    })

    it('handles Numina subagent.update with done status', async () => {
      const { handleSubagentUpdate } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleSubagentUpdate({
        subagent: {
          taskId: 'task-1',
          status: 'done',
          result: 'Completed',
        },
      })
      await nextTick()

      expect(tasks.value['task-1'].status).toBe('completed')
      expect(tasks.value['task-1'].result).toBe('Completed')
    })

    it('handles Numina subagent.update with failed status', async () => {
      const { handleSubagentUpdate } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleSubagentUpdate({
        subagent: {
          taskId: 'task-1',
          status: 'failed',
          error: 'Failed',
        },
      })
      await nextTick()

      expect(tasks.value['task-1'].status).toBe('failed')
      expect(tasks.value['task-1'].error).toBe('Failed')
    })

    it('uses description when title is missing', async () => {
      const { handleSubagentUpdate } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      handleSubagentUpdate({
        subagent: {
          taskId: 'task-1',
          status: 'running',
          description: 'Fallback description',
        },
      })
      await nextTick()

      expect(tasks.value['task-1'].description).toBe('Fallback description')
    })
  })

  describe('clearSubtasks', () => {
    it('clears all tasks', async () => {
      const { updateSubtask, clearSubtasks } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      updateSubtask({ id: 'task-1', status: 'in_progress' })
      updateSubtask({ id: 'task-2', status: 'completed' })
      await nextTick()

      clearSubtasks()
      await nextTick()

      expect(Object.keys(tasks.value)).toEqual([])
    })
  })

  describe('clearCompletedSubtasks', () => {
    it('removes only completed/failed tasks', async () => {
      const { updateSubtask, clearCompletedSubtasks } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      updateSubtask({ id: 'task-1', status: 'in_progress' })
      updateSubtask({ id: 'task-2', status: 'completed' })
      updateSubtask({ id: 'task-3', status: 'failed' })
      await nextTick()

      clearCompletedSubtasks()
      await nextTick()

      expect(Object.keys(tasks.value)).toEqual(['task-1'])
    })

    it('removes cancelled and timed_out tasks', async () => {
      const { updateSubtask, clearCompletedSubtasks } = useUpdateSubtask()
      const { tasks } = useSubtasks()

      updateSubtask({ id: 'task-1', status: 'cancelled' })
      updateSubtask({ id: 'task-2', status: 'timed_out' })
      updateSubtask({ id: 'task-3', status: 'in_progress' })
      await nextTick()

      clearCompletedSubtasks()
      await nextTick()

      expect(Object.keys(tasks.value)).toEqual(['task-3'])
    })
  })
})