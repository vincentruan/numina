import http from './index'

/** 可调度的技能标识符，与后端 ALLOWED_SCHEDULABLE_SKILLS 保持一致。 */
export type SchedulableSkillId = 'asset-report' | 'literacy-weekly-report'

export type ScheduledTaskStatus = 'idle' | 'running' | 'success' | 'failed'

export interface ScheduledTask {
  id: string
  family_id: string
  skill_id: string
  cron_expression: string
  is_enabled: boolean
  next_run_at: string
  last_run_at: string | null
  status: ScheduledTaskStatus
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface ScheduledTaskCreate {
  skill_id: SchedulableSkillId
  cron_expression: string
  is_enabled?: boolean
}

export interface ScheduledTaskUpdate {
  skill_id?: SchedulableSkillId
  cron_expression?: string
  is_enabled?: boolean
}

export const fetchScheduledTasks = () =>
  http.get<{ items: ScheduledTask[] }>('/ai/scheduled-tasks')

export const createScheduledTask = (payload: ScheduledTaskCreate) =>
  http.post<ScheduledTask>('/ai/scheduled-tasks', payload)

export const updateScheduledTask = (id: string, payload: ScheduledTaskUpdate) =>
  http.put<ScheduledTask>(`/ai/scheduled-tasks/${id}`, payload)

export const deleteScheduledTask = (id: string) =>
  http.delete(`/ai/scheduled-tasks/${id}`)
