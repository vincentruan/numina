import type { ThreadSession } from '@/types/ai-chat/session'
import { Client } from '@langchain/langgraph-sdk'
import http from '@/api/index'

/**
 * LangGraph SDK client pointing at the in-process /api base.
 * Reused across composables that stream runs via client.runs.stream().
 */
export function getClient(): Client {
  const apiUrl = typeof window !== 'undefined' ? `${window.location.origin}/api` : '/api'
  return new Client({ apiUrl })
}

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
