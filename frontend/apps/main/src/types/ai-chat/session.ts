/** Session returned from thread search API */
export interface ThreadSession {
  thread_id: string
  title: string
  status: 'idle' | 'interrupted' | 'error'
  is_pinned: boolean
  created_at: string
  updated_at: string
}

/** Token usage from LangGraph streaming metadata */
export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

/** Date grouping label for sidebar sections */
export type DateGroupLabel = 'pinned' | 'today' | 'yesterday' | 'earlier'

/** A date-grouped section in the session sidebar */
export interface DateGroup {
  label: DateGroupLabel
  displayName: string
  sessions: ThreadSession[]
}
