import type { ThreadSession } from '@/types/ai-chat/session'
import http from '@/api/index'

export interface ThreadSearchParams {
  limit?: number
  offset?: number
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  filter?: Record<string, string>
}

export interface ThreadSearchResponse {
  items: ThreadSession[]
  total: number
}

export async function createThread(): Promise<ThreadSession> {
  const res = await http.request({ method: 'POST', url: '/api/threads', data: {} })
  return res.data
}

export async function searchThreads(params: ThreadSearchParams): Promise<ThreadSearchResponse> {
  const res = await http.request({ method: 'GET', url: '/api/threads/search', params })
  return res.data
}

export async function updateThread(id: string, data: Partial<ThreadSession>): Promise<ThreadSession> {
  const res = await http.request({ method: 'PUT', url: `/api/threads/${id}`, data })
  return res.data
}

export async function deleteThread(id: string): Promise<void> {
  await http.request({ method: 'DELETE', url: `/api/threads/${id}` })
}

export async function forkThread(id: string): Promise<ThreadSession> {
  const res = await http.request({ method: 'POST', url: `/api/threads/${id}/fork` })
  return res.data
}
