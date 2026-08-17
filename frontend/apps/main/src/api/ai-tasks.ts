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
  status?: string
): Promise<AITask[]> {
  const params: Record<string, string> = {}
  if (skillId) params.skill_id = skillId
  if (status) params.status = status

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
 * Returns ONLY exact session_id matches — returning another thread's task
 * (even if it's the most recent chat task) would show the wrong banner state
 * after the user switches threads.
 *
 * @param sessionId - Session ID to match against AITask.session_id exactly.
 */
export async function getChatTaskForSession(
  sessionId: string,
): Promise<AITask | null> {
  const tasks = await getAITasks('chat')
  return tasks.find((t) => t.session_id === sessionId) ?? null
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
