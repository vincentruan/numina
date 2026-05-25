import type { AgentEvent, NormalizedAiEvent, NormalizationState, ProcessStep } from '@/types/agent-stream'

export function createNormalizationState(): NormalizationState {
  return {
    phase: 'connecting',
    reasoningStartTime: null,
    answerContent: '',
    steps: [],
  }
}

// Returns the last reasoning step if it is the most recent step in the array,
// otherwise null. New reasoning content after a tool call starts a fresh
// reasoning step so interleaved sequences render in arrival order.
function tailReasoningStep(steps: ProcessStep[]): Extract<ProcessStep, { type: 'reasoning' }> | null {
  const last = steps[steps.length - 1]
  return last && last.type === 'reasoning' ? last : null
}

let reasoningIdSeq = 0
function nextReasoningId(): string {
  reasoningIdSeq += 1
  return `reasoning-${Date.now()}-${reasoningIdSeq}`
}

export function normalizeAgentEvent(
  event: AgentEvent,
  state: NormalizationState,
): NormalizedAiEvent[] {
  const events: NormalizedAiEvent[] = []

  switch (event.type) {
    case 'phase.connecting':
      state.phase = 'connecting'
      events.push({ type: 'phase_change', phase: 'connecting' })
      break

    case 'phase.thinking':
      state.phase = 'thinking'
      if (!state.reasoningStartTime) state.reasoningStartTime = Date.now()
      events.push({ type: 'phase_change', phase: 'thinking' })
      break

    case 'phase.answering': {
      state.phase = 'answering'
      const tail = tailReasoningStep(state.steps)
      if (tail) {
        tail.status = 'done'
        if (state.reasoningStartTime) {
          const elapsedMs = Date.now() - state.reasoningStartTime
          tail.elapsedMs = elapsedMs
          events.push({ type: 'reasoning_done', elapsedMs })
        }
      }
      events.push({ type: 'phase_change', phase: 'answering' })
      break
    }

    case 'token.stream':
      if (event.is_thinking && event.token) {
        let tail = tailReasoningStep(state.steps)
        if (!tail) {
          tail = {
            type: 'reasoning',
            id: nextReasoningId(),
            content: '',
            status: 'streaming',
          }
          state.steps.push(tail)
        }
        tail.content += event.token
        events.push({ type: 'reasoning_delta', content: event.token })
      } else if (event.token) {
        if (state.phase === 'thinking' && import.meta.env.DEV) {
          console.warn(
            '[aiEventNormalizer] non-thinking token received during phase=thinking; routing to answer_delta',
            { token: event.token },
          )
        }
        state.answerContent += event.token
        events.push({ type: 'answer_delta', content: event.token })
      }
      break

    case 'tool.call':
      if (event.tool) {
        const toolStep: ProcessStep = {
          type: 'tool_call',
          id: event.tool.id,
          name: event.tool.name,
          displayName: event.tool.display_name || event.tool.name,
          icon: event.tool.icon || '⚙️',
          args: event.tool.arguments || {},
          status: 'running',
        }
        state.steps.push(toolStep)
        events.push({
          type: 'tool_call',
          toolCallId: event.tool.id,
          name: event.tool.name,
          displayName: event.tool.display_name || event.tool.name,
          icon: event.tool.icon || '⚙️',
          args: event.tool.arguments || {},
        })
        events.push({ type: 'tool_running', toolCallId: event.tool.id })
      }
      break

    case 'tool.result':
      if (event.tool_id) {
        const target = state.steps.find(
          (s): s is Extract<ProcessStep, { type: 'tool_call' }> =>
            s.type === 'tool_call' && s.id === event.tool_id,
        )
        if (target) {
          target.status = event.result?.success ? 'done' : 'error'
          target.resultSummary = event.result?.summary
          target.error = event.result?.error
          target.elapsedMs = event.result?.execution_time_ms
          events.push({
            type: 'tool_result',
            toolCallId: event.tool_id,
            success: event.result?.success ?? false,
            summary: event.result?.summary,
            error: event.result?.error,
            elapsedMs: event.result?.execution_time_ms,
          })
        }
      }
      break

    case 'capability.end':
      if (state.phase === 'answering') {
        events.push({ type: 'answer_done' })
      }
      state.phase = 'done'
      events.push({ type: 'phase_change', phase: 'done' })
      events.push({ type: 'session_end' })
      break

    case 'capability.error':
      events.push({
        type: 'error',
        message: event.error?.message || event.message || 'Unknown error',
        code: event.error?.code || event.code,
      })
      break
  }

  return events
}
