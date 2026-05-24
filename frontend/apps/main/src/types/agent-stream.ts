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
}

// Normalized event types for UI consumption
export type NormalizedAiEvent =
  | { type: 'phase_change'; phase: 'connecting' | 'thinking' | 'answering' | 'done' }
  | { type: 'reasoning_delta'; content: string }
  | { type: 'reasoning_done'; elapsedMs: number }
  | { type: 'tool_call'; toolCallId: string; name: string; displayName: string; icon: string; args: Record<string, unknown> }
  | { type: 'tool_running'; toolCallId: string }
  | { type: 'tool_result'; toolCallId: string; success: boolean; summary?: string; error?: string; elapsedMs?: number }
  | { type: 'answer_delta'; content: string }
  | { type: 'answer_done' }
  | { type: 'error'; message: string; code?: string }
  | { type: 'session_end' }

export interface NormalizationState {
  phase: 'connecting' | 'thinking' | 'answering' | 'done'
  reasoningContent: string
  reasoningStartTime: number | null
  answerContent: string
  toolCalls: Map<string, { name: string; displayName: string; icon: string; args: Record<string, unknown>; status: 'pending' | 'running' | 'done' | 'error'; resultSummary?: string; error?: string; elapsedMs?: number }>
}
