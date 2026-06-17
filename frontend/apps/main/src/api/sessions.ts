import http from './index'
import type { SessionsResponse, SystemDefaultSessionResponse } from '@/types/session'

export const getSessions = async (limit = 20, offset = 0, agentId?: string) => {
  const res = await http.post<any[]>('/threads/search', {
    limit,
    offset,
    metadata: agentId ? { agent_id: agentId } : {}
  })
  
  // Map ThreadResponse to expected SessionsResponse
  const sessions = res.data.map(t => ({
    session_id: t.thread_id,
    title: t.metadata?.title || '',
    is_pinned: t.metadata?.is_pinned || false,
    updated_at: t.updated_at || t.created_at,
    created_at: t.created_at,
    status: t.status,
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

export function streamSessionEvents(
  sessionId: string,
  signal?: AbortSignal,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  return fetch(`/api/v1/ai/sessions/${encodeURIComponent(sessionId)}/events`, {
    credentials: 'include',
    signal,
  }).then((res) => {
    if (!res.ok) throw new Error(`${res.status}`)
    if (!res.body) throw new Error('streaming_not_supported')
    return res.body.getReader()
  })
}

export interface ForkSessionResponse {
  ok: boolean
  session_id: string
  message_count: number
}

export const forkSession = (sessionId: string, forkFromMessageId: string) =>
  http.post<ForkSessionResponse>(`/ai/sessions/${encodeURIComponent(sessionId)}/fork`, {
    fork_from_message_id: forkFromMessageId,
  })
