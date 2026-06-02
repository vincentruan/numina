import http from './index'
import type { SessionsResponse, SystemDefaultSessionResponse } from '@/types/session'

export const getSessions = (limit = 20, offset = 0, capability?: string, agentId?: string) =>
  http.get<SessionsResponse>('/ai/sessions', {
    params: {
      limit,
      offset,
      ...(capability ? { capability } : {}),
      ...(agentId ? { agent_id: agentId } : {}),
    },
  })

export const getSystemDefaultSession = (maxAgeHours = 6) =>
  http.get<SystemDefaultSessionResponse>('/ai/sessions/system-default', {
    params: { max_age_hours: maxAgeHours },
  })

export const updateSession = (sessionId: string, data: { title?: string; is_pinned?: boolean }) =>
  http.patch(`/ai/sessions/${encodeURIComponent(sessionId)}`, data)

export const deleteSession = (sessionId: string) =>
  http.delete(`/ai/sessions/${encodeURIComponent(sessionId)}`)

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
