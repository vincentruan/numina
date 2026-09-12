/**
 * AI Task API - U6 task query endpoints for frontend task resume.
 *
 * Provides methods to query AI tasks from the backend's /api/v1/ai/tasks endpoint.
 * Used by useTaskResume composable to check for running tasks on page load.
 */
import api from '@/api'

export interface AITask {
  id: string
  family_id: string
  skill_id: string
  status:
    | 'running'
    | 'queued'
    | 'post_processing'
    | 'completed'
    | 'failed'
    | 'cancelled'
    | 'interrupted'
    | 'timeout'
  run_id?: string
  worker_id?: string
  started_at: string
  completed_at?: string
  error_message?: string
  // v2 fields (U10)
  progress?: Record<string, unknown> | null
  lease_expires_at?: string | null
  queue_position?: number | null
  session_id?: string | null
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
  status?: string,
  limit?: number,
): Promise<AITask[]> {
  const params: Record<string, string> = {}
  if (skillId) params.skill_id = skillId
  if (status) params.status = status
  if (limit != null) params.limit = String(limit)

  const response = await api.get('/ai/tasks', { params })
  return response.data
}

/**
 * Get all running tasks for the current family.
 *
 * @returns Array of running AITask objects
 */
export async function getRunningTasks(): Promise<AITask[]> {
  const response = await api.get('/ai/tasks/running')
  return response.data
}

/**
 * Get a specific task by ID.
 *
 * @param taskId - Task ID
 * @returns AITask object
 */
export async function getTaskById(taskId: string): Promise<AITask> {
  const response = await api.get(`/ai/tasks/detail/${taskId}`)
  return response.data
}

/**
 * Cancel a running task by ID (U21).
 *
 * Backend immediately marks the task as cancelled and notifies the agent
 * to stop execution (fire-and-forget). Idempotent: already-terminal tasks
 * return their current status without error.
 *
 * @param taskId - Task ID to cancel
 * @returns { ok, status, task_id }
 */
export async function cancelTaskById(
  taskId: string,
): Promise<{ ok: boolean; status: string; task_id: string }> {
  const response = await api.post(`/ai/tasks/detail/${taskId}/cancel`)
  return response.data
}

/**
 * Get the latest chat task for a session (U19).
 *
 * Used by the chat frontend recovery flow to check if a task is still
 * running after page reload / navigation. Returns the most recent chat
 * AITask for the given session, or null if none exists.
 *
 * Passes the thread_id (UUID) as a query parameter — the backend resolves
 * it to the internal session_id (snowflake PK) before filtering. The
 * previous client-side filter (`tasks.find(t => t.session_id === sessionId)`)
 * never matched because AITask.session_id is a snowflake int serialized as
 * string while the frontend only knows the UUID thread_id.
 *
 * @param threadId - Agent thread UUID (from store.activeThreadId).
 */
export async function getChatTaskForSession(
  threadId: string,
): Promise<AITask | null> {
  const params: Record<string, string> = { skill_id: 'chat', thread_id: threadId }
  const response = await api.get('/ai/tasks', { params })
  const tasks: AITask[] = response.data
  return tasks.length > 0 ? tasks[0] : null
}

// ---------------------------------------------------------------------------
// v3 SSE reconnection — subscribe-only stream
// ---------------------------------------------------------------------------

export interface TaskStreamCallbacks {
  onEvent: (event: string, data: unknown) => void
  onGap: () => void
  onEnd: () => void
  onError: (message: string) => void
}

export interface TaskStreamHandle {
  abort: () => void
}

/**
 * Subscribe to a task's SSE stream (subscribe-only, no trigger).
 *
 * Used for SSE reconnection when user navigates back to a page
 * while a task is still running. Supports Last-Event-ID for
 * gap-free replay from the bridge buffer.
 *
 * Uses bare fetch because axios lacks native SSE support —
 * same pattern as streamNarrative / useReportStream.
 */
export function subscribeTaskStream(
  taskId: string,
  callbacks: TaskStreamCallbacks,
  options?: { lastEventId?: string },
): TaskStreamHandle {
  const controller = new AbortController()
  void runTaskStream(controller, taskId, callbacks, options)
  return { abort: () => controller.abort() }
}

async function runTaskStream(
  controller: AbortController,
  taskId: string,
  callbacks: TaskStreamCallbacks,
  options?: { lastEventId?: string },
): Promise<void> {
  const url = `/api/v1/ai/tasks/detail/${taskId}/stream`
  const headers: Record<string, string> = { Accept: 'text/event-stream' }
  if (options?.lastEventId) {
    headers['Last-Event-ID'] = options.lastEventId
  }

  let res: Response
  try {
    res = await fetch(url, {
      method: 'GET',
      headers,
      credentials: 'include',
      signal: controller.signal,
    })
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      callbacks.onError('stream.request_failed')
    }
    return
  }

  if (!res.ok) {
    callbacks.onError(`stream.request_failed:${res.status}`)
    return
  }

  if (!res.body) {
    callbacks.onError('stream.unavailable')
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
          continue
        }
        if (!line.startsWith('data:')) continue
        const dataStr = line.slice(5).trim()

        const event = currentEvent || 'message'
        currentEvent = ''

        if (event === 'end') {
          callbacks.onEnd()
          return
        }
        if (event === 'gap') {
          callbacks.onGap()
          return
        }

        // Parse JSON data (best-effort)
        let parsed: unknown = dataStr
        try {
          parsed = JSON.parse(dataStr)
        } catch {
          // Non-JSON data — pass raw string
        }

        callbacks.onEvent(event, parsed)
      }
    }
    // Stream ended without explicit end event
    callbacks.onEnd()
  } catch (err) {
    if ((err as Error).name !== 'AbortError') {
      callbacks.onError('stream.read_failed')
    }
  }
}
