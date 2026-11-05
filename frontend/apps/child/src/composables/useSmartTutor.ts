import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { readSSEStream, type SSEStreamHandlers } from '@numina/shared'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TutorPhase =
  | 'diagnose'
  | 'focused_guidance'
  | 'prerequisite_retrace'
  | 'misconception_correction'
  | 'verify'
  | 'consolidate'
  | 'end'

export interface TutorMessage {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  phase?: TutorPhase
  toolCall?: { name: string; arguments: Record<string, unknown> }
  toolResult?: { name: string; output: unknown }
  timestamp: number
}

export interface TeacherPersona {
  subject: string
  age_group: string
  style: string
  style_en: string
  description: string
  tone: string
  max_sentence_length: number
  use_emoji: boolean
  strategies: string[]
}

export interface KnowledgeNode {
  topic_id: string
  name: string | null
  subject: string | null
  mastery_level: string
  depth: number
  is_current: boolean
}

export interface KnowledgeBridge {
  topic_id: string
  child_id: string
  prerequisite_chain: KnowledgeNode[]
  broken_link: KnowledgeNode | null
  total_depth: number
}

// ---------------------------------------------------------------------------
// Composable
// ---------------------------------------------------------------------------

export function useSmartTutor() {
  const { t } = useI18n()

  const messages = ref<TutorMessage[]>([])
  const status = ref<'idle' | 'connecting' | 'streaming' | 'completed' | 'error'>('idle')
  const currentPhase = ref<TutorPhase>('diagnose')
  const currentStreamText = ref('')
  const error = ref<string | null>(null)
  const activeSessionId = ref<string | null>(null)
  const activeQuestionId = ref<string | null>(null)
  const stepCount = ref(0)
  const persona = ref<TeacherPersona | null>(null)
  const knowledgeBridge = ref<KnowledgeBridge | null>(null)

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
          const result = payload.result as Record<string, unknown> | undefined
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

          // Extract phase transitions from record_tutoring_step results
          if (
            payload.tool_name === 'record_tutoring_step' &&
            result &&
            typeof result === 'object'
          ) {
            const nextPhase = result.next_phase as TutorPhase | undefined
            if (nextPhase) currentPhase.value = nextPhase
            stepCount.value = (result.total_steps as number) ?? stepCount.value + 1
          }

          // Extract knowledge bridge data
          if (payload.tool_name === 'get_knowledge_bridge' && result) {
            knowledgeBridge.value = result as unknown as KnowledgeBridge
          }

          // Extract persona data
          if (payload.tool_name === 'get_teacher_persona' && result) {
            persona.value = result as unknown as TeacherPersona
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

  /** Start a new smart-tutor session for a specific question. */
  async function startTutoring(sessionId: string, questionId: string) {
    activeSessionId.value = sessionId
    activeQuestionId.value = questionId
    status.value = 'connecting'
    error.value = null
    stepCount.value = 0
    currentPhase.value = 'diagnose'
    abortController = new AbortController()

    try {
      const response = await fetch(
        `/api/v1/child/learning/sessions/${sessionId}/smart-tutor/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ question_id: questionId }),
          signal: abortController.signal,
        },
      )

      if (!response.ok) {
        throw new Error(
          t('learning.error.smart_tutor_start', { status: response.status }),
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

  /** Submit the child's answer for the next Socratic turn. */
  async function submitAnswer(answer: string) {
    if (!answer.trim() || !activeSessionId.value) return
    if (!canSendAnswer.value) return

    // Add user message optimistically
    messages.value.push({
      id: `user-${Date.now()}`,
      role: 'user',
      content: answer,
      timestamp: Date.now(),
    })

    status.value = 'connecting'
    error.value = null
    abortController = new AbortController()

    try {
      const response = await fetch(
        `/api/v1/child/learning/sessions/${activeSessionId.value}/smart-tutor/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Accept': 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            child_answer: answer,
            question_id: activeQuestionId.value
              ? Number(activeQuestionId.value)
              : undefined,
          }),
          signal: abortController.signal,
        },
      )

      if (!response.ok) {
        throw new Error(
          t('learning.error.smart_tutor_answer', { status: response.status }),
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

  /** Request a hint from the teacher. */
  async function requestHint() {
    await submitAnswer(
      t('learning.smart_tutor.hint_request'),
    )
  }

  /** Signal that the child understands. */
  async function confirmUnderstanding() {
    await submitAnswer(
      t('learning.smart_tutor.understand_confirm'),
    )
  }

  function disconnect() {
    abortController?.abort()
    abortController = null
  }

  function reset() {
    disconnect()
    messages.value = []
    status.value = 'idle'
    currentPhase.value = 'diagnose'
    currentStreamText.value = ''
    error.value = null
    activeSessionId.value = null
    activeQuestionId.value = null
    stepCount.value = 0
    persona.value = null
    knowledgeBridge.value = null
  }

  return {
    messages,
    status,
    currentPhase,
    currentStreamText,
    error,
    persona,
    knowledgeBridge,
    stepCount,
    isStreaming,
    isCompleted,
    canSendAnswer,
    startTutoring,
    submitAnswer,
    requestHint,
    confirmUnderstanding,
    disconnect,
    reset,
  }
}
