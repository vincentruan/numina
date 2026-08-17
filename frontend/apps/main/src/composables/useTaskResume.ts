/**
 * useTaskResume — v3 unified task resume composable.
 *
 * When user returns to a page, detects running tasks and attempts SSE
 * reconnection (subscribeTaskStream). Falls back to useTaskPolling on
 * gap/error/completion.
 *
 * Replaces the inline `resumeIfRunning()` pattern in individual components.
 *
 * Usage:
 *   const { resume, cleanup, status, taskId } = useTaskResume('narrative', {
 *     onStreamEvent: (event, data) => { ... },
 *     onComplete: (task) => { ... },
 *     onError: (task) => { ... },
 *   })
 *
 *   onActivated(async () => {
 *     const resumed = await resume()
 *     if (!resumed) await loadCached()
 *   })
 */
import { ref, type Ref } from 'vue'
import {
  getAITasks,
  subscribeTaskStream,
  type AITask,
  type TaskStreamHandle,
} from '@/api/ai-tasks'
import { useTaskPolling } from '@/composables/useTaskPolling'

export type TaskResumeStatus =
  | 'idle'
  | 'connecting'
  | 'streaming'
  | 'polling'
  | 'completed'
  | 'failed'

export interface UseTaskResumeOptions {
  /** Called for each SSE event during streaming. */
  onStreamEvent?: (event: string, data: unknown) => void
  /** Called when the task reaches 'completed' status. */
  onComplete?: (task: AITask) => void
  /** Called when the task reaches a terminal error state. */
  onError?: (task: AITask) => void
}

export interface UseTaskResumeReturn {
  /** Current task ID (set after resume detects a running task). */
  taskId: Ref<string | null>
  /** Resume lifecycle status. */
  status: Ref<TaskResumeStatus>
  /** Latest task data from API or polling. */
  task: Ref<AITask | null>
  /** Whether the composable is loading/checking. */
  loading: Ref<boolean>
  /** True when waitForTask exhausted all retries without finding a task. */
  triggerFailed: Ref<boolean>
  /** Attempt to resume — returns true if a running task was found. */
  resume: () => Promise<boolean>
  /** Progressive retry (500ms->1s->2s->4s) to find a just-triggered task. */
  waitForTask: () => Promise<AITask | null>
  /**
   * Retry after trigger failure. Re-checks for a running/completed task
   * (reuses it if found); returns false when no reusable task exists and
   * the caller must fire a fresh trigger.
   */
  retryTrigger: () => Promise<boolean>
  /** Cancel the current task (delegates to useTaskPolling.cancel). */
  cancel: () => Promise<void>
  /** Clean up SSE connection and polling. */
  cleanup: () => void
  /** Re-check task status (legacy compat). */
  check: () => Promise<void>
}

export function useTaskResume(
  capability: string,
  options: UseTaskResumeOptions = {},
): UseTaskResumeReturn {
  const taskId = ref<string | null>(null)
  const status = ref<TaskResumeStatus>('idle')
  const task = ref<AITask | null>(null)
  const triggerFailed = ref(false)
  const loading = ref(false)

  let streamHandle: TaskStreamHandle | null = null
  let disposed = false

  // Polling fallback — watches taskId ref
  const polling = useTaskPolling(taskId, {
    onComplete: (t) => {
      status.value = 'completed'
      task.value = t
      options.onComplete?.(t)
    },
    onError: (t) => {
      status.value = 'failed'
      task.value = t
      options.onError?.(t)
    },
  })

  function startSSE(tid: string): void {
    // P1-1 fix: abort previous SSE before starting a new one
    streamHandle?.abort()
    status.value = 'connecting'
    streamHandle = subscribeTaskStream(
      tid,
      {
        onEvent: (event, data) => {
          status.value = 'streaming'
          options.onStreamEvent?.(event, data)
        },
        onGap: () => {
          // Buffer overflow — fallback to polling
          status.value = 'polling'
          // taskId is already set → useTaskPolling takes over
        },
        onEnd: () => {
          // Stream ended — task likely completed.
          // useTaskPolling will detect the terminal state on next poll.
          // If polling isn't active yet, trigger a check.
          if (status.value !== 'completed' && status.value !== 'failed') {
            polling.pollNow()
          }
        },
        onError: (_msg) => {
          // SSE failed — fallback to polling
          status.value = 'polling'
        },
      },
    )
  }

  async function resume(): Promise<boolean> {
    loading.value = true
    try {
      const tasks = await getAITasks(capability)
      const latestTask = tasks[0]

      if (
        !latestTask?.id ||
        !['running', 'queued', 'post_processing'].includes(latestTask.status)
      ) {
        // No running task
        if (latestTask?.status === 'completed') {
          status.value = 'completed'
          task.value = latestTask
          options.onComplete?.(latestTask)
        } else if (
          latestTask?.status === 'failed' ||
          latestTask?.status === 'timeout'
        ) {
          status.value = 'failed'
          task.value = latestTask
          options.onError?.(latestTask)
        }
        return false
      }

      // Found a running task — try SSE reconnection
      taskId.value = latestTask.id
      task.value = latestTask
      startSSE(latestTask.id)
      return true
    } catch {
      status.value = 'idle'
      return false
    } finally {
      loading.value = false
    }
  }

  /**
   * T20 fix: progressive retry to locate the AITask created by a just-fired
   * trigger. Backend task creation races with agent startup; a single 500ms
   * check may miss it. Retries at 500ms -> 1s -> 2s -> 4s (4 attempts).
   * Returns the running task, or null if none appears.
   */
  async function waitForTask(): Promise<AITask | null> {
    const delays = [500, 1000, 2000, 4000]
    for (const delay of delays) {
      if (disposed) return null
      await new Promise((r) => setTimeout(r, delay))
      if (disposed) return null
      try {
        const tasks = await getAITasks(capability)
        const latestTask = tasks[0]
        if (
          latestTask?.id &&
          ['running', 'queued', 'post_processing'].includes(latestTask.status)
        ) {
          taskId.value = latestTask.id
          task.value = latestTask
          return latestTask
        }
      } catch {
        // best-effort; keep retrying
      }
    }
    if (!disposed) triggerFailed.value = true
    return null
  }

  /**
   * Retry after trigger failure. Re-checks for a running/completed task and
   * reuses it if found. Returns false when no reusable task exists (caller
   * must fire a fresh trigger).
   */
  async function retryTrigger(): Promise<boolean> {
    try {
      const tasks = await getAITasks(capability)
      const latestTask = tasks[0]
      if (
        latestTask?.id &&
        ['running', 'queued', 'post_processing'].includes(latestTask.status)
      ) {
        // Reuse the late-appearing running task
        triggerFailed.value = false
        taskId.value = latestTask.id
        task.value = latestTask
        startSSE(latestTask.id)
        return true
      }
      if (latestTask?.status === 'completed') {
        triggerFailed.value = false
        task.value = latestTask
        options.onComplete?.(latestTask)
        return true
      }
    } catch {
      // fall through to fresh trigger
    }
    return false
  }

  function cleanup(): void {
    disposed = true
    streamHandle?.abort()
    streamHandle = null
    polling.stop()
    taskId.value = null
    status.value = 'idle'
  }

  // Legacy compat — same as resume but returns void
  async function check(): Promise<void> {
    await resume()
  }

  return {
    taskId,
    status,
    task,
    loading,
    triggerFailed,
    resume,
    waitForTask,
    retryTrigger,
    cancel: polling.cancel,
    cleanup,
    check,
  }
}
