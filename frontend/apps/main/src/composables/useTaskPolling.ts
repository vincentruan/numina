/**
 * useTaskPolling — U16 generic task polling composable.
 *
 * Polls GET /api/v1/ai/tasks/detail/{taskId} at a configurable interval,
 * tracking status transitions and pausing when the document is hidden.
 *
 * Extracted from useReportStream's inline pollTaskUntilComplete() so all
 * non-Chat AI features (coach, literacy, narrative) share one implementation.
 */
import { ref, watch, onUnmounted, type Ref } from 'vue'
import { getTaskById, type AITask } from '@/api/ai-tasks'

export type TaskPollingStatus = 'idle' | 'polling' | 'completed' | 'failed'

export interface UseTaskPollingOptions {
  /** Polling interval in ms (default 2000). */
  interval?: number
  /** Called when task status becomes 'completed'. */
  onComplete?: (task: AITask) => void
  /** Called when task status becomes 'failed'/'cancelled'/'timeout'. */
  onError?: (task: AITask) => void
}

export interface UseTaskPollingReturn {
  /** Current polling lifecycle status. */
  status: Ref<TaskPollingStatus>
  /** Latest task data from the API. */
  task: Ref<AITask | null>
  /** Whether the polling timer is currently paused (document hidden). */
  paused: Ref<boolean>
  /** Last error message (if any). */
  errorMessage: Ref<string>
  /** Start polling a specific taskId. Pass null to stop. */
  setTaskId: (id: string | null) => void
  /** Force an immediate poll cycle. */
  pollNow: () => Promise<void>
  /** Cancel the current task (U21) and stop polling. */
  cancel: () => Promise<void>
  /** Stop polling and reset state. */
  stop: () => void
}

/**
 * Generic task polling composable.
 *
 * Watches `taskIdRef` — when it becomes non-null, starts polling every
 * `interval` ms. Pauses on `document.hidden`, resumes on visibility change.
 * Stops automatically on component unmount.
 */
export function useTaskPolling(
  taskIdRef: Ref<string | null>,
  options: UseTaskPollingOptions = {},
): UseTaskPollingReturn {
  const { interval = 2000, onComplete, onError } = options

  const status = ref<TaskPollingStatus>('idle')
  const task = ref<AITask | null>(null)
  const paused = ref(false)
  const errorMessage = ref('')

  let timer: ReturnType<typeof setInterval> | null = null
  let disposed = false
  // I1 fix: overlap guard — prevent concurrent pollOnce calls when API is slow.
  let pollInFlight = false

  function clearTimer(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  function handleTaskResult(t: AITask): void {
    task.value = t
    if (t.status === 'completed') {
      status.value = 'completed'
      clearTimer()
      onComplete?.(t)
    } else if (t.status === 'failed' || t.status === 'cancelled' || t.status === 'timeout') {
      status.value = 'failed'
      errorMessage.value = t.error_message || '任务失败'
      clearTimer()
      onError?.(t)
    }
    // 'running' / 'queued' → keep polling, progress is in task.value
  }

  async function pollOnce(): Promise<void> {
    const id = taskIdRef.value
    if (!id || disposed || pollInFlight) return

    pollInFlight = true
    try {
      const result = await getTaskById(id)
      if (disposed) return
      handleTaskResult(result)
    } catch (err) {
      if (disposed) return
      // Network error — don't stop polling, just log
      console.warn('[useTaskPolling] poll error:', err)
    } finally {
      pollInFlight = false
    }
  }

  function startTimer(): void {
    clearTimer()
    timer = setInterval(() => {
      if (!document.hidden) {
        pollOnce()
      }
    }, interval)
  }

  // Visibility change handler — pause/resume
  function onVisibilityChange(): void {
    if (disposed || status.value === 'completed' || status.value === 'failed') return
    paused.value = document.hidden
    if (!document.hidden && timer !== null) {
      // Resume: poll immediately then restart timer
      pollOnce()
      startTimer()
    }
  }

  // Watch taskIdRef — start/stop polling
  watch(
    taskIdRef,
    (newId) => {
      // I5 fix: always remove the previous listener before adding a new one
      // to avoid accumulating listeners when taskIdRef flips between non-null values.
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearTimer()
      if (newId) {
        status.value = 'polling'
        errorMessage.value = ''
        task.value = null
        // Poll immediately, then start interval
        pollOnce()
        startTimer()
        document.addEventListener('visibilitychange', onVisibilityChange)
      } else {
        status.value = 'idle'
      }
    },
    { immediate: true },
  )

  function setTaskId(id: string | null): void {
    taskIdRef.value = id
  }

  async function pollNow(): Promise<void> {
    await pollOnce()
  }

  async function cancel(): Promise<void> {
    const id = taskIdRef.value
    if (!id) return
    try {
      const { cancelTaskById } = await import('@/api/ai-tasks')
      await cancelTaskById(id)
      // Verify server state with one immediate poll (don't trust optimistic update)
      try {
        const result = await getTaskById(id)
        if (result.status === 'cancelled') {
          status.value = 'failed'
          errorMessage.value = '任务已取消'
        } else if (result.status === 'completed') {
          // Task completed before cancel took effect — show completed state
          handleTaskResult(result)
        } else {
          // Server hasn't processed cancel yet — set cancelled optimistically
          status.value = 'failed'
          errorMessage.value = '任务已取消'
        }
      } catch {
        // Verification failed — set optimistically
        status.value = 'failed'
        errorMessage.value = '任务已取消'
      }
      clearTimer()
    } catch (err) {
      console.warn('[useTaskPolling] cancel error:', err)
    }
  }

  function stop(): void {
    disposed = true
    clearTimer()
    document.removeEventListener('visibilitychange', onVisibilityChange)
    status.value = 'idle'
  }

  onUnmounted(() => {
    stop()
  })

  return {
    status,
    task,
    paused,
    errorMessage,
    setTaskId,
    pollNow,
    cancel,
    stop,
  }
}
