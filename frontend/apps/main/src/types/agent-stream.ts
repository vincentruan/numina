export type AgentEventType =
  | 'session.start'
  | 'phase.connecting'
  | 'phase.thinking'
  | 'phase.answering'
  | 'tool.call'
  | 'tool.result'
  | 'token.stream'
  | 'capability.end'
  | 'capability.error'
  | 'subagent.update'
  | 'artifact.created'
  | 'state.snapshot'
  | 'plan.update'
  | 'tool.progress'

export interface Artifact {
  id: string
  title: string
  url?: string
  path?: string
  kind?: 'report' | 'file' | 'image' | 'link' | 'other'
}

export interface Subagent {
  taskId: string
  status: 'running' | 'done' | 'failed'
  title?: string
  description?: string
  result?: string
  error?: string
}

export interface AgentEvent {
  id?: string
  type: AgentEventType
  timestamp?: number
  session_id?: string
  capability_id?: string
  task_id?: string
  phase?: 'connecting' | 'thinking' | 'answering'
  metadata?: Record<string, unknown>
  token?: string
  is_thinking?: boolean
  tool?: {
    id: string
    name: string
    tool_type?: string
    display_name: string
    icon: string
    arguments: Record<string, unknown>
  }
  tool_id?: string
  result?: {
    success?: boolean
    data?: unknown
    error?: string
    execution_time_ms?: number
    summary?: string
    tokens_used?: number
    tools_used?: string[]
  }
  error?: {
    message: string
    code: string
  }
  // capability.error may also be sent as a flat object: { type, code, message }
  code?: string
  message?: string
  // subagent.update payload (spec §4.1)
  subagent?: Subagent
  // artifact.created payload (spec §4.1)
  artifact?: Artifact
  // state.snapshot payload (spec §4.1) — replays full state on history load
  messages?: unknown[]
  artifacts?: Artifact[]
  title?: string
  // plan.update payload
  todos?: Array<{ id: string; content: string; status: string }>
  // tool.progress payload
  progress_message?: string
}

// Plan step — represents a single step in an AI-generated plan (spec §4.2)
export interface PlanStep {
  id: string
  label: string
  status: 'pending' | 'active' | 'done' | 'error'
}

// Normalized event types for UI consumption (spec §4.1)
export type NormalizedAiEvent =
  | { type: 'phase_change'; phase: 'connecting' | 'thinking' | 'answering' | 'done' }
  | { type: 'reasoning_delta'; content: string }
  | { type: 'reasoning_done'; elapsedMs: number }
  | { type: 'tool_call'; toolCallId: string; name: string; displayName: string; icon: string; toolType?: string; args: Record<string, unknown> }
  | { type: 'tool_running'; toolCallId: string }
  | { type: 'tool_result'; toolCallId: string; success: boolean; summary?: string; error?: string; elapsedMs?: number }
  | { type: 'answer_delta'; content: string }
  | { type: 'answer_done' }
  | { type: 'subagent_update'; taskId: string; status: 'running' | 'done' | 'failed'; title?: string; description?: string; result?: string; error?: string }
  | { type: 'artifact'; id: string; title: string; url?: string; path?: string; kind?: 'report' | 'file' | 'image' | 'link' | 'other' }
  | { type: 'state_snapshot'; messages?: unknown[]; artifacts?: Artifact[]; title?: string }
  | { type: 'error'; message: string; code?: string }
  | { type: 'session_end' }
  | { type: 'plan_update'; steps: PlanStep[] }
  | { type: 'tool_progress'; toolCallId: string; progressMessage: string }

// Unified process step union — preserves event arrival order across reasoning, tool calls,
// subagents, artifacts, and progress events. Spec §3.3 requires a single steps[] array
// (not split props) so interleaved sequences render in the order they arrived.
// AiProcessBlock dispatches by `type`.
export type ProcessStep =
  | {
      type: 'reasoning'
      id: string
      content: string
      status: 'streaming' | 'done'
      elapsedMs?: number
    }
  | {
      type: 'tool_call'
      id: string
      name: string
      displayName: string
      icon: string
      toolType?: string
      args: Record<string, unknown>
      status: 'pending' | 'running' | 'done' | 'error'
      resultSummary?: string
      error?: string
      elapsedMs?: number
      progressMessage?: string
    }
  | {
      type: 'subagent'
      id: string
      taskId: string
      title?: string
      description?: string
      status: 'running' | 'done' | 'failed'
      result?: string
      error?: string
    }
  | {
      type: 'artifact'
      id: string
      title: string
      url?: string
      path?: string
      kind?: 'report' | 'file' | 'image' | 'link' | 'other'
    }
  | {
      type: 'progress'
      id: string
      title: string
      description?: string
      status: 'running' | 'done' | 'error'
    }

export interface NormalizationState {
  phase: 'connecting' | 'thinking' | 'answering' | 'done'
  reasoningStartTime: number | null
  answerContent: string
  steps: ProcessStep[]
  artifacts: Artifact[]
  subagents: Map<string, Subagent>
  planSteps: PlanStep[]
  lastPlanHash: string
  planSource: 'explicit' | 'inferred' | null
  inferredSteps: PlanStep[]
  planWaitTimer: ReturnType<typeof setTimeout> | null
}
