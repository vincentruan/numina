/**
 * AI Task API - U6 task query endpoints for frontend task resume.
 *
 * Provides methods to query AI tasks from the backend's /api/v1/ai/tasks endpoint.
 * Used by useTaskResume composable to check for running tasks on page load.
 */
import axios from 'axios'

export interface AITask {
  id: string
  family_id: string
  skill_id: string
  status: 'running' | 'queued' | 'completed' | 'failed' | 'cancelled' | 'interrupted' | 'timeout'
  run_id?: string
  worker_id?: string
  started_at: string
  completed_at?: string
  error_message?: string
}

/**
 * Get AI tasks for the current family, optionally filtered by skill_id and status.
 *
 * @param skillId - Optional skill_id filter (e.g., 'report', 'import', 'coach')
 * @param status - Optional status filter (e.g., 'running', 'completed')
 * @returns Array of AITask objects
 */
export async function getAITasks(
  skillId?: string,
  status?: string
): Promise<AITask[]> {
  const params: Record<string, string> = {}
  if (skillId) params.skill_id = skillId
  if (status) params.status = status

  const response = await axios.get('/api/v1/ai/tasks', { params })
  return response.data
}

/**
 * Get all running tasks for the current family.
 *
 * @returns Array of running AITask objects
 */
export async function getRunningTasks(): Promise<AITask[]> {
  const response = await axios.get('/api/v1/ai/tasks/running')
  return response.data
}

/**
 * Get a specific task by ID.
 *
 * @param taskId - Task ID
 * @returns AITask object
 */
export async function getTaskById(taskId: string): Promise<AITask> {
  const response = await axios.get(`/api/v1/ai/tasks/${taskId}`)
  return response.data
}
