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
