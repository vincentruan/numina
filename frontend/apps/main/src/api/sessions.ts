import http from './index'
import type { SessionsResponse, SystemDefaultSessionResponse, SessionSummary } from '@/types/session'

// Partial session for search results (backend /threads/search doesn't return all fields)
export interface PartialSessionSummary {
  session_id: string
  title: string | null
  is_pinned: boolean
  updated_at: string
  created_at: string
  status: 'active' | 'completed' | 'error'
}

export const getSessions = async (limit = 20, offset = 0, agentId?: string) => {
  const res = await http.post<unknown[]>('/threads/search', {
    limit,
    offset,
    metadata: agentId ? { agent_id: agentId } : {}
  })

  // Map ThreadResponse to PartialSessionSummary (subset of SessionSummary fields)
  const sessions: PartialSessionSummary[] = (res.data as Record<string, unknown>[]).map(t => ({
    session_id: (t.thread_id as string) || '',
    title: (t.metadata as Record<string, unknown>)?.title as string | null || '',
    is_pinned: (t.metadata as Record<string, unknown>)?.is_pinned as boolean || false,
    updated_at: (t.updated_at as string) || (t.created_at as string) || '',
    created_at: (t.created_at as string) || '',
    status: (t.status as 'active' | 'completed' | 'error') || 'active',
  }))

  return { data: { sessions, total: 100 } } // Mock total since /search doesn't return it
}

export const getSystemDefaultSession = (maxAgeHours = 6) =>
  http.get<SystemDefaultSessionResponse>('/ai/sessions/system-default', {
    params: { max_age_hours: maxAgeHours },
  })

export const updateSession = (sessionId: string, data: { title?: string; is_pinned?: boolean }) =>
  http.patch(`/threads/${encodeURIComponent(sessionId)}`, { metadata: data })

export const deleteSession = (sessionId: string) =>
  http.delete(`/threads/${encodeURIComponent(sessionId)}`)

