/** Session returned from thread search API */
export interface ThreadSession {
  thread_id: string
  title: string
  /** Auto-generated title preserved on first manual rename (read-only). */
  original_title?: string
  status: 'idle' | 'interrupted' | 'error'
  is_pinned: boolean
  /** True when this session was branched from another thread (source=='branch'). */
  is_branch?: boolean
  /** Thread id this session was branched from; undefined for non-branch sessions. */
  parent_thread_id?: string
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
