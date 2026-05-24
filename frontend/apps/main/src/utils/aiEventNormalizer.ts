import type { AgentEvent, NormalizedAiEvent, NormalizationState } from '@/types/agent-stream'

export function createNormalizationState(): NormalizationState {
  return {
    phase: 'connecting',
    reasoningContent: '',
    reasoningStartTime: null,
    answerContent: '',
    toolCalls: new Map(),
  }
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

    case 'phase.answering':
      state.phase = 'answering'
      if (state.reasoningStartTime && state.reasoningContent) {
        const elapsedMs = Date.now() - state.reasoningStartTime
        events.push({ type: 'reasoning_done', elapsedMs })
      }
      events.push({ type: 'phase_change', phase: 'answering' })
      break

    case 'token.stream':
      if (event.is_thinking && event.token) {
        state.reasoningContent += event.token
        events.push({ type: 'reasoning_delta', content: event.token })
      } else if (state.phase === 'answering' && event.token) {
        state.answerContent += event.token
        events.push({ type: 'answer_delta', content: event.token })
      }
      break

    case 'tool.call':
      if (event.tool) {
        state.toolCalls.set(event.tool.id, {
          name: event.tool.name,
          displayName: event.tool.display_name || event.tool.name,
          icon: event.tool.icon || '⚙️',
          args: event.tool.arguments || {},
          status: 'running',
        })
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
      if (event.tool_id && state.toolCalls.has(event.tool_id)) {
        const tool = state.toolCalls.get(event.tool_id)!
        tool.status = event.result?.success ? 'done' : 'error'
        tool.resultSummary = event.result?.summary
        tool.error = event.result?.error
        tool.elapsedMs = event.result?.execution_time_ms
        events.push({
          type: 'tool_result',
          toolCallId: event.tool_id,
          success: event.result?.success ?? false,
          summary: event.result?.summary,
          error: event.result?.error,
          elapsedMs: event.result?.execution_time_ms,
        })
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
