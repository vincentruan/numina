/**
 * useTaskResume - U6 generic task resume hook for frontend SSE reconnection.
 *
 * Checks for existing running/completed tasks on page load and returns state
 * so the caller can reconnect SSE or load cached results.
 *
 * Usage:
 *   const { status, taskId, runId, task } = useTaskResume('report')
 *
 *   if (status.value === 'running') {
 *     // Reconnect SSE with taskId and runId
 *   } else if (status.value === 'completed') {
 *     // Load cached result from task
 *   } else {
 *     // No existing task, trigger new generation
 *   }
 */
import { ref, onMounted, type Ref } from 'vue'
import { getAITasks, type AITask } from '@/api/ai-tasks'

export type TaskResumeStatus = 'idle' | 'running' | 'completed' | 'failed' | 'interrupted'

export interface UseTaskResumeReturn {
  status: Ref<TaskResumeStatus>
  taskId: Ref<string | null>
  runId: Ref<string | null>
  task: Ref<AITask | null>
  loading: Ref<boolean>
  error: Ref<string | null>
  check: () => Promise<void>
}

/**
 * Generic task resume hook.
 *
 * On mount, queries GET /api/v1/ai/tasks?skill={skillId}&status=running,completed
 * and returns the most recent task state.
 *
 * @param skillId - Skill ID to check (e.g., 'report', 'import', 'coach')
 * @returns Task resume state and check function
 */
export function useTaskResume(skillId: string): UseTaskResumeReturn {
  const status = ref<TaskResumeStatus>('idle')
  const taskId = ref<string | null>(null)
  const runId = ref<string | null>(null)
  const task = ref<AITask | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function check(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      // Query for running and completed tasks
      const tasks = await getAITasks(skillId)

      if (tasks.length === 0) {
        status.value = 'idle'
        taskId.value = null
        runId.value = null
        task.value = null
        return
      }

      // Find the most recent task (sorted by started_at desc by backend)
      const latestTask = tasks[0]

      taskId.value = latestTask.id
      runId.value = latestTask.run_id || null
      task.value = latestTask

      // Map backend status to frontend status
      if (latestTask.status === 'running' || latestTask.status === 'queued') {
        status.value = 'running'
      } else if (latestTask.status === 'completed') {
        status.value = 'completed'
      } else if (latestTask.status === 'failed' || latestTask.status === 'timeout') {
        status.value = 'failed'
      } else if (latestTask.status === 'interrupted' || latestTask.status === 'cancelled') {
        status.value = 'interrupted'
      } else {
        status.value = 'idle'
      }
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to check task status'
      status.value = 'idle'
    } finally {
      loading.value = false
    }
  }

  // Check on mount
  onMounted(() => {
    check()
  })

  return {
    status,
    taskId,
    runId,
    task,
    loading,
    error,
    check,
  }
}
