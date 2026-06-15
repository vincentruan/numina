/**
 * DeerFlow Subtasks Composable
 *
 * 参考: frontend/src/core/tasks/context.tsx
 *
 * 职责:
 * - 管理 Subtask 状态字典 (Record<string, Subtask>)
 * - 处理 subagent.update 事件
 * - 提供 useSubtask(taskId) 单任务查询
 */

import { ref, computed, readonly } from 'vue'
import type { Subtask, SubtaskStatus } from '@/types/ai-chat/subtask'
import { EVENT_STATUS_MAP } from '@/types/ai-chat/subtask'

// 全局状态
const tasks = ref<Record<string, Subtask>>({})

/**
 * 获取所有子任务
 */
export function useSubtasks() {
  return {
    tasks: readonly(tasks),
    taskList: computed(() => Object.values(tasks.value)),
    inProgressCount: computed(() =>
      Object.values(tasks.value).filter((t) => t.status === 'in_progress').length,
    ),
  }
}

/**
 * 获取单个子任务
 */
export function useSubtask(taskId: string) {
  return computed(() => tasks.value[taskId])
}

/**
 * 清除所有子任务（session 结束时调用）
 */
export function clearSubtasks() {
  tasks.value = {}
}

/**
 * 清除已完成的子任务
 */
export function clearCompletedSubtasks() {
  for (const [id, task] of Object.entries(tasks.value)) {
    if (task.status !== 'in_progress') {
      delete tasks.value[id]
    }
  }
}

/**
 * 更新子任务状态
 */
export function useUpdateSubtask() {
  /**
   * 创建或更新子任务
   */
  function updateSubtask(task: Partial<Subtask> & { id: string }) {
    tasks.value[task.id] = {
      ...tasks.value[task.id],
      ...task,
    } as Subtask
  }

  /**
   * 处理 DeerFlow task 事件
   */
  function handleTaskEvent(event: {
    type: string
    task_id?: string
    taskId?: string
    description?: string
    prompt?: string
    latestMessage?: unknown
    result?: string
    error?: string
    usage?: Subtask['usage']
  }) {
    const taskId = event.task_id || event.taskId
    if (!taskId) return

    const status = EVENT_STATUS_MAP[event.type] || 'in_progress'

    updateSubtask({
      id: taskId,
      status,
      description: event.description,
      prompt: event.prompt,
      latestMessage: event.latestMessage,
      result: event.result,
      error: event.error,
      usage: event.usage,
    })
  }

  /**
   * 处理 Numina subagent.update 事件
   *
   * Numina 后端发送的格式:
   * {
   *   type: 'subagent.update',
   *   subagent: {
   *     taskId: string,
   *     status: 'running' | 'done' | 'failed',
   *     title?: string,
   *     description?: string,
   *     result?: string,
   *     error?: string,
   *   }
   * }
   */
  function handleSubagentUpdate(event: {
    subagent: {
      taskId: string
      status: 'running' | 'done' | 'failed'
      title?: string
      description?: string
      result?: string
      error?: string
    }
  }) {
    const { taskId, status, title, description, result, error } = event.subagent

    // Numina status 映射
    const mappedStatus: SubtaskStatus =
      status === 'running' ? 'in_progress' : status === 'done' ? 'completed' : status === 'failed' ? 'failed' : 'in_progress'

    updateSubtask({
      id: taskId,
      status: mappedStatus,
      description: title || description,
      result,
      error,
    })
  }

  return {
    updateSubtask,
    handleTaskEvent,
    handleSubagentUpdate,
    clearSubtasks,
    clearCompletedSubtasks,
  }
}