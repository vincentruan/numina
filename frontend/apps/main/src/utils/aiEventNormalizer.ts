import type { AgentEvent, NormalizedAiEvent, NormalizationState, ProcessStep } from '@/types/agent-stream'
import { hashTodos, mapTodosToPlanSteps } from '@/utils/planDiff'

export function createNormalizationState(): NormalizationState {
  return {
    phase: 'connecting',
    reasoningStartTime: null,
    answerContent: '',
    steps: [],
    artifacts: [],
    subagents: new Map(),
    planSteps: [],
    lastPlanHash: '',
    planSource: null,
    inferredSteps: [],
    planWaitTimer: null,
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
    case 'session.start':
      // Start 3s inference fallback timer. If no explicit plan.update arrives
      // within 3 seconds, tool.call events will activate inference mode.
      if (state.planWaitTimer !== null) clearTimeout(state.planWaitTimer)
      state.planWaitTimer = setTimeout(() => {
        state.planWaitTimer = null
        // Timer has expired; planSource remains null until a tool.call fires
        // the inference activation branch below.
      }, 3000)
      break

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
    case 'tool.call_started': // 兼容旧格式
      if (event.tool || event.toolName) {
        // 统一处理：提取 tool 信息，映射旧格式字段
        const toolInfo = event.tool || {
          id: event.toolId ?? event.tool_id,
          name: event.toolName ?? event.tool_name,
          display_name: event.toolName ?? event.tool_name,
          icon: event.icon ?? 'tool',
          arguments: event.arguments ?? event.args ?? {},
        }

        // If no explicit plan arrived and the 3s timer has already expired
        // (planWaitTimer === null means it fired or was never started), activate
        // inference mode so the UI can show inferred plan steps.
        if (state.planSource === null && state.planWaitTimer === null) {
          state.planSource = 'inferred'
        }
        const toolStep: ProcessStep = {
          type: 'tool_call',
          id: toolInfo.id,
          name: toolInfo.name,
          displayName: toolInfo.display_name || toolInfo.name,
          icon: toolInfo.icon || '⚙️',
          toolType: toolInfo.tool_type,
          args: toolInfo.arguments || {},
          status: 'running',
        }
        state.steps.push(toolStep)
        events.push({
          type: 'tool_call',
          toolCallId: toolInfo.id,
          name: toolInfo.name,
          displayName: toolInfo.display_name || toolInfo.name,
          icon: toolInfo.icon || '⚙️',
          toolType: toolInfo.tool_type,
          args: toolInfo.arguments || {},
        })
        events.push({ type: 'tool_running', toolCallId: toolInfo.id })
      }
      break

    case 'tool.result':
    case 'tool.call_completed': // 兼容旧格式
      const toolId = event.tool_id ?? event.toolId
      if (toolId) {
        const target = state.steps.find(
          (s): s is Extract<ProcessStep, { type: 'tool_call' }> =>
            s.type === 'tool_call' && s.id === toolId,
        )
        if (target) {
          // Handle both nested (streaming) and flat (journal) formats
          target.status = (event.result?.success ?? event.success ?? false) ? 'done' : 'error'
          target.resultSummary = event.result?.summary ?? event.summary
          target.data = event.result?.data ?? event.data
          target.error = event.result?.error ?? event.error
          target.elapsedMs = event.result?.execution_time_ms ?? event.executionTimeMs
          events.push({
            type: 'tool_result',
            toolCallId: toolId,
            success: event.result?.success ?? false,
            summary: event.result?.summary,
            error: event.result?.error,
            elapsedMs: event.result?.execution_time_ms,
          })
        }
      }
      break

    case 'tool.progress':
      if (event.tool_id && event.progress_message) {
        const target = state.steps.find(
          (s): s is Extract<ProcessStep, { type: 'tool_call' }> =>
            s.type === 'tool_call' && s.id === event.tool_id,
        )
        if (target) {
          target.progressMessage = event.progress_message
        }
        events.push({
          type: 'tool_progress',
          toolCallId: event.tool_id,
          progressMessage: event.progress_message,
        })
      }
      break

    case 'plan.update': {
      // Clear the inference timer and set explicit source
      if (state.planWaitTimer !== null) {
        clearTimeout(state.planWaitTimer)
        state.planWaitTimer = null
      }
      const prevSource = state.planSource
      state.planSource = 'explicit'

      if (event.todos && event.todos.length > 0) {
        const newHash = hashTodos(event.todos)
        if (newHash !== state.lastPlanHash) {
          state.lastPlanHash = newHash
          const newPlanSteps = mapTodosToPlanSteps(event.todos)

          // Source switching: if inference was active, clear inferred steps
          if (prevSource === 'inferred') {
            state.inferredSteps = []
          }

          state.planSteps = newPlanSteps

          // Insert/update progress-type ProcessStep entries in steps[] so they
          // appear inline in the activity stream.
          for (const planStep of newPlanSteps) {
            const existingIdx = state.steps.findIndex(
              (s): s is Extract<ProcessStep, { type: 'progress' }> =>
                s.type === 'progress' && s.id === planStep.id,
            )
            const progressStep: Extract<ProcessStep, { type: 'progress' }> = {
              type: 'progress',
              id: planStep.id,
              title: planStep.label,
              status: planStep.status === 'pending' || planStep.status === 'active' ? 'running' : planStep.status,
            }
            if (existingIdx >= 0) {
              state.steps[existingIdx] = progressStep
            } else {
              state.steps.push(progressStep)
            }
          }

          events.push({ type: 'plan_update', steps: newPlanSteps })
        }
        // If hash unchanged, skip emission (no duplicate event)
      }
      break
    }

    case 'capability.end':
      // Clear the plan inference timer to prevent dangling callbacks after stream ends
      if (state.planWaitTimer !== null) {
        clearTimeout(state.planWaitTimer)
        state.planWaitTimer = null
      }
      if (state.phase === 'answering') {
        events.push({ type: 'answer_done' })
      }
      state.phase = 'done'
      events.push({ type: 'phase_change', phase: 'done' })
      events.push({ type: 'session_end' })
      break

    case 'capability.error':
      // Clear the plan inference timer to prevent dangling callbacks after error
      if (state.planWaitTimer !== null) {
        clearTimeout(state.planWaitTimer)
        state.planWaitTimer = null
      }
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
          kind: event.artifact.kind === 'data' ? 'other' : event.artifact.kind,
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
          kind: event.artifact.kind === 'data' ? 'other' : event.artifact.kind,
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

/**
 * Extracts an artifact from a completed tool call step.
 * Returns null for non-artifact steps (reasoning, subagent, etc.) or incomplete tool calls.
 */
export function extractArtifactFromStep(step: ProcessStep): import('@/types/agent-stream').Artifact | null {
  // Only tool_call steps can produce artifacts
  if (step.type !== 'tool_call') {
    return null
  }

  // Only completed tool calls produce artifacts
  if (step.status !== 'done') {
    return null
  }

  // Exclude internal tools that don't produce user-facing artifacts
  if (step.name === 'write_todos') {
    return null
  }

  // Must have resultSummary to extract from
  if (!step.resultSummary) {
    return null
  }

  // URL extraction patterns
  const urlPattern = /(https?:\/\/[^\s]+)/g
  const imageExtensions = /\.(png|jpe?g|gif|svg)(\?.*)?$/i

  // Check for image URLs
  const urls = step.resultSummary.match(urlPattern)
  if (urls && urls.length > 0) {
    const url = urls[0]
    const isImage = imageExtensions.test(url)
    return {
      id: `artifact-${step.id}`,
      title: step.displayName || step.name,
      url,
      kind: isImage ? 'image' : 'link',
      sourceStepId: step.id,
      generatedAt: new Date().toISOString(),
    }
  }

  // File path extraction pattern - match paths with file extensions
  // Supports absolute paths (/path/to/file.ext) and relative paths (path/to/file.ext)
  const fileExtensions = 'txt|csv|json|md|pdf|xlsx|docx?|png|jpe?g|gif|svg'
  const pathPattern = new RegExp(`((?:/|[a-zA-Z]:)[^\\s]+\\.(?:${fileExtensions})(\\?.*)?)`, 'gi')

  const pathMatches = step.resultSummary.match(pathPattern)
  if (pathMatches && pathMatches.length > 0) {
    const path = pathMatches[0]
    return {
      id: `artifact-${step.id}`,
      title: step.displayName || step.name,
      path,
      kind: 'file',
      sourceStepId: step.id,
      generatedAt: new Date().toISOString(),
    }
  }

  // Check for structured data in step.data
  if (step.data && typeof step.data === 'object') {
    return {
      id: `artifact-${step.id}`,
      title: step.displayName || step.name,
      kind: 'data',
      sourceStepId: step.id,
      generatedAt: new Date().toISOString(),
    }
  }

  return null
}
