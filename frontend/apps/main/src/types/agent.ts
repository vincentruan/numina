export interface Agent {
  id: string
  family_id: string
  agent_name: string
  display_name: string
  description: string | null
  icon: string | null
  color: string | null
  soul_md: string
  skills: string[] | null
  model: string | null
  subagent_enabled: boolean
  tool_groups: string[] | null
  is_builtin: boolean
  is_enabled: boolean
  display_order: number
  created_by: string | null
  created_at: string
  updated_at: string
  can_edit: boolean
  can_delete: boolean
}

export interface AgentListResponse {
  builtin: Agent[]
  custom: Agent[]
}

export interface AgentCreatePayload {
  agent_name: string
  display_name: string
  description?: string
  icon?: string
  color?: string
  soul_md: string
  skills?: string[]
  model?: string
  subagent_enabled?: boolean
  tool_groups?: string[]
}

export interface AgentUpdatePayload {
  display_name?: string
  description?: string
  icon?: string
  color?: string
  soul_md?: string
  skills?: string[]
  model?: string
  subagent_enabled?: boolean
  tool_groups?: string[]
  display_order?: number
}
