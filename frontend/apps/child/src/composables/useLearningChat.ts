// frontend/apps/child/src/composables/useLearningChat.ts
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { readSSEStream, type SSEStreamHandlers } from '@numina/shared'
import http from '@/api'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  toolCall?: { name: string; arguments: Record<string, unknown> }
  toolResult?: { name: string; output: unknown }
  timestamp: number
}

export function useLearningChat() {
  const { t } = useI18n()
  const messages = ref<ChatMessage[]>([])
  const status = ref<'idle' | 'connecting' | 'streaming' | 'completed' | 'error'>('idle')
  const lastEventId = ref<string | null>(null)
  const currentStreamText = ref('')
  const error = ref<string | null>(null)

  let abortController: AbortController | null = null
  let _activeSessionId = ''

  /**
   * Shared SSE event handlers — used by startAssessment, reconnect, and sendMessage.
   * Eliminates duplicated handler blocks across the three streaming methods.
   */
  function _createStreamHandlers(): SSEStreamHandlers {
    return {
      onMessage(event: string, data: unknown) {
        const payload = data as Record<string, unknown>
        if (payload?.content) {
          currentStreamText.value += payload.content as string
        }
      },
      onCustom(data: unknown) {
        const payload = data as Record<string, unknown>
        const type = payload?.type as string | undefined
        if (type === 'tool_call') {
          messages.value.push({
            id: `tool-${Date.now()}`,
            role: 'tool',
            content: '',
            toolCall: {
              name: payload.tool_name as string,
              arguments: payload.tool_args as Record<string, unknown>,
            },
            timestamp: Date.now(),
          })
        } else if (type === 'tool_result') {
          messages.value.push({
            id: `result-${Date.now()}`,
            role: 'tool',
            content: '',
            toolResult: {
              name: payload.tool_name as string,
              output: payload.result,
            },
            timestamp: Date.now(),
          })
        } else if (type === 'learning-tutor.result') {
          messages.value.push({
            id: `eval-${Date.now()}`,
            role: 'assistant',
            content: JSON.stringify(payload.data),
            timestamp: Date.now(),
          })
        }
      },
      onError(data: unknown) {
        error.value = String((data as Record<string, unknown>)?.message ?? t('learning.error.stream'))
        status.value = 'error'
      },
      onEnd() {
        // Flush any accumulated streaming text as a message
        if (currentStreamText.value) {
          messages.value.push({
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: currentStreamText.value,
            timestamp: Date.now(),
          })
          currentStreamText.value = ''
        }
        status.value = 'completed'
      },
      onMetadata(data: unknown) {
        const payload = data as Record<string, unknown>
        if (payload?.run_id) {
          lastEventId.value = (payload.last_event_id as string) ?? lastEventId.value
        }
      },
      onGap() {
        // Gap recovery: buffer overflow — show error instead of creating duplicate runs
        _handleGap()
      },
    }
  }

  /** Internal: handle stream gap (buffer overflow on Redis side).
   *
   * Re-subscribing via POST /assess/stream would create a duplicate AITask
   * and agent run.  Instead, show a user-visible error directing them to
   * refresh.  A dedicated resume endpoint (re-subscribe to existing run_id
   * via GET) is planned for a follow-up.
   */
  function _handleGap() {
    error.value = t('learning.error.gap_recovery')
    status.value = 'error'
  }

  async function startAssessment(sessionId: string) {
    _activeSessionId = sessionId
    status.value = 'connecting'
    error.value = null
    abortController = new AbortController()

    try {
      const response = await fetch(
        `/api/v1/child/learning/sessions/${sessionId}/assess/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            ...(lastEventId.value ? { 'Last-Event-ID': lastEventId.value } : {}),
          },
          signal: abortController.signal,
        },
      )

      if (!response.ok) {
        throw new Error(t('learning.error.assessment_stream', { status: response.status }))
      }

      status.value = 'streaming'
      currentStreamText.value = ''

      await readSSEStream(response, _createStreamHandlers())
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message
        status.value = 'error'
      }
    }
  }

  /**
   * Reconnect to an active or completed assessment.
   *
   * Pattern (from useTaskResume / useReportStream):
   * 1. GET /sessions/{id}/status to check run_status
   * 2a. running → resume SSE with Last-Event-ID
   * 2b. completed → load history from checkpointer via agent thread API
   * 2c. interrupted/error → show recovery UI
   * 2d. idle → no active run, do nothing
   */
  async function reconnect(sessionId: string) {
    _activeSessionId = sessionId
    status.value = 'connecting'
    error.value = null

    try {
      // 1. Check session status via Axios (non-SSE call uses wrapper)
      const { data: sessionStatus } = await http.get(
        `/child/learning/sessions/${sessionId}/status`,
      )

      if (sessionStatus.run_status === 'idle') {
        status.value = 'idle'
        return
      }

      if (sessionStatus.run_status === 'completed' || sessionStatus.run_status === 'failed') {
        // Load history from checkpointer via agent thread API
        if (sessionStatus.thread_id) {
          const { data: history } = await http.get(
            `/child/learning/sessions/${sessionId}/history`,
          )
          messages.value = (history.messages ?? []).map((m: Record<string, unknown>) => ({
            id: `hist-${m.id ?? Date.now()}`,
            role: (m.role as ChatMessage['role']) ?? 'assistant',
            content: (m.content as string) ?? '',
            timestamp: Date.now(),
          }))
        }
        status.value = 'completed'
        return
      }

      if (sessionStatus.run_status === 'running') {
        // Resume SSE with Last-Event-ID
        status.value = 'streaming'
        abortController = new AbortController()

        const response = await fetch(
          `/api/v1/child/learning/sessions/${sessionId}/assess/stream`,
          {
            method: 'POST',
            credentials: 'include',
            headers: {
              'Accept': 'text/event-stream',
              ...(lastEventId.value ? { 'Last-Event-ID': lastEventId.value } : {}),
            },
            signal: abortController.signal,
          },
        )

        if (!response.ok) throw new Error(t('learning.error.reconnect', { status: response.status }))
        await readSSEStream(response, _createStreamHandlers())
        return
      }

      // interrupted / timeout
      status.value = 'error'
      error.value = t('learning.error.session_interrupted', { status: sessionStatus.run_status })
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message
        status.value = 'error'
      }
    }
  }

  /**
   * Send a message during tutorial mode (multi-turn learning).
   *
   * Pattern (from useThreadChat.sendMessage):
   * 1. Cancel existing stream if still loading
   * 2. Add optimistic user message to messages list
   * 3. POST new assessment with user_message in body → backend builds new agent run
   * 4. Stream response
   */
  async function sendMessage(sessionId: string, content: string) {
    if (!content.trim()) return
    _activeSessionId = sessionId

    // 1. Cancel existing stream if active
    if (abortController) {
      abortController.abort()
      abortController = null
    }

    // 2. Add user message
    messages.value.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    })

    status.value = 'connecting'
    error.value = null
    abortController = new AbortController()

    try {
      const response = await fetch(
        `/api/v1/child/learning/sessions/${sessionId}/assess/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ user_message: content }),
          signal: abortController.signal,
        },
      )

      if (!response.ok) throw new Error(t('learning.error.send', { status: response.status }))

      status.value = 'streaming'
      currentStreamText.value = ''

      await readSSEStream(response, _createStreamHandlers())
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message
        status.value = 'error'
      }
    }
  }

  function disconnect() {
    abortController?.abort()
    abortController = null
  }

  const isStreaming = computed(() => status.value === 'streaming')
  const isCompleted = computed(() => status.value === 'completed')

  return {
    messages,
    status,
    currentStreamText,
    error,
    isStreaming,
    isCompleted,
    startAssessment,
    reconnect,
    sendMessage,
    disconnect,
  }
}
