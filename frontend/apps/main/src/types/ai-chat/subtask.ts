/**
 * DeerFlow Subtask Types
 *
 * 参考: frontend/src/core/tasks/types.ts
 */

export type SubtaskStatus = 'in_progress' | 'completed' | 'failed' | 'cancelled' | 'timed_out'

export interface Subtask {
  id: string // tool_call_id (task_id)
  status: SubtaskStatus
  subagent_type?: string // subagent 名称
  description?: string // 任务描述
  latestMessage?: unknown // 最新消息
  prompt?: string // 子任务 prompt
  result?: string // 最终结果
  error?: string // 错误信息
  usage?: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
}

/**
 * Numina subagent.update 事件状态映射
 */
export const EVENT_STATUS_MAP: Record<string, SubtaskStatus> = {
  task_started: 'in_progress',
  task_running: 'in_progress',
  task_completed: 'completed',
  task_failed: 'failed',
  task_timed_out: 'timed_out',
  task_cancelled: 'cancelled',
}