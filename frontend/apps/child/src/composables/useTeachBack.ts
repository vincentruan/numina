import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { readSSEStream, type SSEStreamHandlers } from '@numina/shared'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TeachBackPhase =
  | 'present_confusion'
  | 'evaluate_explanation'
  | 'resolve'
  | 'end'

export interface TeachBackConfusion {
  id: string
  sequence: number
  text: string
  text_zh: string | null
}

export interface TeachBackTurn {
  confusion_id: string
  child_explanation: string
  verdict: 'hit' | 'miss'
  extracted_expression: string | null
  expression_verdict: 'true' | 'false' | 'null'
  reasoning_summary: string
  phase: TeachBackPhase
  next_phase: TeachBackPhase
}

export interface TeachBackMessage {
  id: string
  role: 'user' | 'assistant' | 'tool'
  content: string
  phase?: TeachBackPhase
  toolResult?: { name: string; output: unknown }
  timestamp: number
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useTeachBack() {
  const { t } = useI18n()

  const messages = ref<TeachBackMessage[]>([])
  const status = ref<'idle' | 'connecting' | 'streaming' | 'completed' | 'error'>('idle')
  const currentPhase = ref<TeachBackPhase>('present_confusion')
  const currentStreamText = ref('')
  const error = ref<string | null>(null)
  const activeSessionId = ref<string | null>(null)
  const activeTopicId = ref<string | null>(null)
  const turns = ref<TeachBackTurn[]>([])
  const allConfusionsHit = ref(false)
  const teachBackSuccess = ref(false)

  let abortController: AbortController | null = null

  const isStreaming = computed(() => status.value === 'streaming')
  const isCompleted = computed(() => status.value === 'completed')
  const canSendAnswer = computed(
    () => status.value === 'completed' || status.value === 'idle',
  )

  // ---------------------------------------------------------------------------
  // SSE handlers
  // ---------------------------------------------------------------------------

  function _createHandlers(): SSEStreamHandlers {
    return {
      onMessage(_event: string, data: unknown) {
        const payload = data as Record<string, unknown>
        if (payload?.content) {
          currentStreamText.value += payload.content as string
        }
      },
      onCustom(data: unknown) {
        const payload = data as Record<string, unknown>
        const type = payload?.type as string | undefined
        // Capture session_id from the prepended session_created event (#4)
        if (type === 'session_created' && typeof payload.session_id === 'string') {
          activeSessionId.value = payload.session_id
          return
        }
        if (type === 'tool_result') {
          // Backend publishes the tool payload under `content` (see run_pipeline.py
          // tool_result synthesis), not `result`. Parse it when it is a JSON string.
          let result: Record<string, unknown> | undefined
          if (typeof payload.content === 'string') {
            try {
              result = JSON.parse(payload.content) as Record<string, unknown>
            } catch {
              result = undefined
            }
          } else if (payload.content && typeof payload.content === 'object') {
            result = payload.content as Record<string, unknown>
          }
          if (payload.tool_name === 'record_teach_back_turn' && result) {
            // Fallback: also capture session_id from tool result
            if (typeof result.session_id === 'string' && !activeSessionId.value) {
              activeSessionId.value = result.session_id
            }
            // Extract teach-back turn + verdict from the tool result
            if (typeof result.child_explanation === 'string') {
              const turn: TeachBackTurn = {
                confusion_id: String(result.confusion_id),
                child_explanation: result.child_explanation as string,
                verdict: result.verdict as 'hit' | 'miss',
                extracted_expression:
                  (result.extracted_expression as string | null) ?? null,
                expression_verdict:
                  (result.expression_verdict as 'true' | 'false' | 'null') ?? 'null',
                reasoning_summary:
                  (result.reasoning_summary as string | undefined) ?? '',
                phase: result.phase as TeachBackPhase,
                next_phase: result.next_phase as TeachBackPhase,
              }
              turns.value.push(turn)
              if (result.next_phase) {
                currentPhase.value = result.next_phase as TeachBackPhase
              }
              if (result.all_confusions_hit) allConfusionsHit.value = true
              if (result.teach_back_success) teachBackSuccess.value = true
            }
          }
        }
      },
      onError(data: unknown) {
        error.value = String(
          (data as Record<string, unknown>)?.message ?? t('learning.error.stream'),
        )
        status.value = 'error'
      },
      onEnd() {
        if (currentStreamText.value) {
          messages.value.push({
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: currentStreamText.value,
            phase: currentPhase.value,
            timestamp: Date.now(),
          })
          currentStreamText.value = ''
        }
        status.value = 'completed'
      },
      onMetadata(_data: unknown) {
        // track run metadata if needed
      },
      onGap() {
        error.value = t('learning.error.gap_recovery')
        status.value = 'error'
      },
    }
  }

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  /** Start a new teach-back session for a mastered topic. */
  async function startTeachBack(topicId: string) {
    activeTopicId.value = topicId
    status.value = 'connecting'
    error.value = null
    turns.value = []
    allConfusionsHit.value = false
    teachBackSuccess.value = false
    currentPhase.value = 'present_confusion'
    abortController = new AbortController()

    try {
      const response = await fetch(
        '/api/v1/child/learning/teach-back/stream',
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ topic_id: topicId }),
          signal: abortController.signal,
        },
      )

      if (!response.ok) {
        throw new Error(
          t('learning.teach_back.error.start', { status: response.status }),
        )
      }

      status.value = 'streaming'
      currentStreamText.value = ''
      await readSSEStream(response, _createHandlers())
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        error.value = (e as Error).message
        status.value = 'error'
      }
    }
  }

  /** Submit the child's explanation for the current confusion. */
  async function submitExplanation(explanation: string) {
    if (!explanation.trim() || !activeTopicId.value || !activeSessionId.value) return
    if (!canSendAnswer.value) return

    messages.value.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content: explanation,
      timestamp: Date.now(),
    })

    status.value = 'connecting'
    error.value = null
    abortController = new AbortController()

    try {
      const response = await fetch(
        '/api/v1/child/learning/teach-back/stream',
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_id: activeSessionId.value,
            child_answer: explanation,
          }),
          signal: abortController.signal,
        },
      )

      if (!response.ok) {
        throw new Error(
          t('learning.teach_back.error.answer', { status: response.status }),
        )
      }

      status.value = 'streaming'
      currentStreamText.value = ''
      await readSSEStream(response, _createHandlers())
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

  function reset() {
    disconnect()
    messages.value = []
    status.value = 'idle'
    currentPhase.value = 'present_confusion'
    currentStreamText.value = ''
    error.value = null
    activeSessionId.value = null
    activeTopicId.value = null
    turns.value = []
    allConfusionsHit.value = false
    teachBackSuccess.value = false
  }

  return {
    messages,
    status,
    currentPhase,
    currentStreamText,
    error,
    turns,
    allConfusionsHit,
    teachBackSuccess,
    isStreaming,
    isCompleted,
    canSendAnswer,
    startTeachBack,
    submitExplanation,
    disconnect,
    reset,
  }
}
