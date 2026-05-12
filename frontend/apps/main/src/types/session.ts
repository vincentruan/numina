export interface SessionSummary {
  session_id: string
  family_id: string
  user_id: string | null
  capability: string
  title: string | null
  status: 'active' | 'completed' | 'error'
  last_message_summary: string | null
  last_model: string | null
  has_attachments: boolean
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export interface SessionsResponse {
  sessions: SessionSummary[]
  total: number
}
