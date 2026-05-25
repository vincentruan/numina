import type { AgentEvent, NormalizedAiEvent, NormalizationState, ProcessStep } from '@/types/agent-stream'

export function createNormalizationState(): NormalizationState {
  return {
    phase: 'connecting',
    reasoningStartTime: null,
    answerContent: '',
    steps: [],
    artifacts: [],
    subagents: new Map(),
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

    case 'subagent.update':
      if (event.subagent?.taskId) {
        const prev = state.subagents.get(event.subagent.taskId)
        // Merge so partial updates (e.g. status-only) keep prior title/description
        const merged = { ...(prev ?? {}), ...event.subagent }
        state.subagents.set(event.subagent.taskId, merged)
        const stepIdx = state.steps.findIndex(
          (s) => s.type === 'subagent' && s.taskId === merged.taskId,
        )
        const subagentStep: Extract<ProcessStep, { type: 'subagent' }> = {
          type: 'subagent',
          id: `subagent-${merged.taskId}`,
          taskId: merged.taskId,
          title: merged.title,
          description: merged.description,
          status: merged.status,
          result: merged.result,
          error: merged.error,
        }
        if (stepIdx >= 0) {
          state.steps[stepIdx] = subagentStep
        } else {
          state.steps.push(subagentStep)
        }
        events.push({
          type: 'subagent_update',
          taskId: merged.taskId,
          status: merged.status,
          title: merged.title,
          description: merged.description,
          result: merged.result,
          error: merged.error,
        })
      }
      break

    case 'artifact.created':
      if (event.artifact?.id) {
        // Dedupe by id — re-emission of an artifact should update in place
        const existing = state.artifacts.findIndex((a) => a.id === event.artifact!.id)
        if (existing >= 0) {
          state.artifacts[existing] = event.artifact
        } else {
          state.artifacts.push(event.artifact)
        }
        const stepIdx = state.steps.findIndex(
          (s) => s.type === 'artifact' && s.id === event.artifact!.id,
        )
        const artifactStep: Extract<ProcessStep, { type: 'artifact' }> = {
          type: 'artifact',
          id: event.artifact.id,
          title: event.artifact.title,
          url: event.artifact.url,
          path: event.artifact.path,
          kind: event.artifact.kind,
        }
        if (stepIdx >= 0) {
          state.steps[stepIdx] = artifactStep
        } else {
          state.steps.push(artifactStep)
        }
        events.push({
          type: 'artifact',
          id: event.artifact.id,
          title: event.artifact.title,
          url: event.artifact.url,
          path: event.artifact.path,
          kind: event.artifact.kind,
        })
      }
      break

    case 'state.snapshot':
      if (event.artifacts) {
        state.artifacts = [...event.artifacts]
      }
      events.push({
        type: 'state_snapshot',
        messages: event.messages,
        artifacts: event.artifacts,
        title: event.title,
      })
      break
  }

  return events
}
