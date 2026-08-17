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
  /** Attempt to resume — returns true if a running task was found. */
  resume: () => Promise<boolean>
  /** Progressive retry (500ms->1s->2s->4s) to find a just-triggered task. */
  waitForTask: () => Promise<AITask | null>
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
  const loading = ref(false)
  const lastEventId = ref<string | null>(null)

  let streamHandle: TaskStreamHandle | null = null

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
    status.value = 'connecting'
    streamHandle = subscribeTaskStream(
      tid,
      {
        onEvent: (event, data) => {
          status.value = 'streaming'
          // Track last event ID for potential reconnects
          // (SSE spec: events may carry an id field — for now
          // we track via the onEvent callback data)
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
      { lastEventId: lastEventId.value || undefined },
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
      await new Promise((r) => setTimeout(r, delay))
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
    return null
  }

  function cleanup(): void {
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
    resume,
    waitForTask,
    cancel: polling.cancel,
    cleanup,
    check,
  }
}
