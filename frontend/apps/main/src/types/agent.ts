export interface Agent {
  id: string
  family_id: string
  agent_name: string
  display_name: string
  description: string | null
  icon: string | undefined
  color: string | null
  soul_md: string
  skills: string[] | null
  model: string | null
  subagent_enabled: boolean
  tool_groups: string[] | null
  agent_type: 'system' | 'custom'
  is_enabled: boolean
  is_published: boolean
  display_order: number
  created_by: string | null
  created_at: string
  updated_at: string
  can_edit: boolean
  can_delete: boolean
}

export interface AgentListResponse {
  system: Agent[]
  custom: Agent[]
}

export interface AgentListGroupedResponse {
  system: Agent[]
  builtin: Agent[]
  custom: Agent[]
  total: number
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
  is_published?: boolean
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
  is_published?: boolean
}
