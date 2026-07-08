import type { ThreadSession } from '@/types/ai-chat/session'
import { Client } from '@langchain/langgraph-sdk'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'

/**
 * LangGraph SDK client pointing at the in-process /api base.
 * Reused across composables that stream runs via client.runs.stream().
 */
export function getClient(): Client {
  const apiUrl = typeof window !== 'undefined' ? `${window.location.origin}/api` : '/api'
  const authStore = useAuthStore()
  const familyStore = useFamilyStore()
  // Prefer familyStore.family.id (full family object), fallback to authStore.user.family_id
  const familyId = familyStore.family?.id || authStore.user?.family_id
  if (!familyId) {
    throw new Error('Family not loaded - cannot make agent API calls')
  }
  // The @langchain/langgraph-sdk Client builds fetch requests without setting
  // `credentials`, so the browser does not attach the `access_token` cookie
  // that `verify_family_token` (runs_stream.py) reads. Every direct fetch() in
  // this module uses `credentials: 'include'` for the same reason; the SDK
  // client must match, or `client.runs.stream()` 401s before the run starts
  // and the thread is left empty (no AI output, no checkpoint messages).
  return new Client({
    apiUrl,
    defaultHeaders: { 'X-Family-Id': familyId },
    onRequest: (_url, init) => ({ ...init, credentials: 'include' }),
  })
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

/** Get the base URL for agent service API calls */
function getAgentApiBase(): string {
  return typeof window !== 'undefined' ? window.location.origin : ''
}

/** Get required headers for agent service calls */
function getAgentHeaders(): Record<string, string> {
  const authStore = useAuthStore()
  const familyStore = useFamilyStore()
  const familyId = familyStore.family?.id || authStore.user?.family_id
  if (!familyId) {
    throw new Error('Family not loaded - cannot make agent API calls')
  }
  return {
    'Content-Type': 'application/json',
    'X-Family-Id': familyId,
  }
}

/** Raw ThreadResponse from the agent threads API */
interface ThreadApiResponse {
  thread_id: string
  status: string
  created_at: string
  updated_at: string
  metadata: Record<string, unknown>
  values: Record<string, unknown>
}

/** Map agent ThreadResponse → frontend ThreadSession */
function mapThreadResponse(r: ThreadApiResponse): ThreadSession {
  const metadataTitle = (r.metadata?.title as string) || ''
  const valuesTitle = (r.values?.title as string) || ''
  // values.title is the raw [SKILL:chat] prompt wrapper on the sync stream
  // path (sync after_model fallback) - never display it as a title.
  const title = metadataTitle
    || (valuesTitle && !valuesTitle.startsWith('[SKILL:') ? valuesTitle : '')
  return {
    thread_id: r.thread_id,
    title,
    original_title: (r.metadata?.original_title as string) || undefined,
    status: (r.status as ThreadSession['status']) || 'idle',
    is_pinned: (r.metadata?.is_pinned as boolean) || false,
    created_at: r.created_at,
    updated_at: r.updated_at,
  }
}

export async function createThread(): Promise<ThreadSession> {
  const res = await fetch(`${getAgentApiBase()}/api/threads`, {
    method: 'POST',
    headers: getAgentHeaders(),
    credentials: 'include',
    body: JSON.stringify({}),
  })
  if (!res.ok) throw new Error(`Failed to create thread: ${res.status}`)
  return mapThreadResponse(await res.json() as ThreadApiResponse)
}

export async function getThread(id: string): Promise<ThreadSession> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/${encodeURIComponent(id)}`, {
    headers: getAgentHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Failed to get thread: ${res.status}`)
  return mapThreadResponse(await res.json() as ThreadApiResponse)
}

/** Thread state (including channel_values.messages) — used for export. */
export interface ThreadState {
  values: { title?: string; messages?: unknown[]; [k: string]: unknown }
  [k: string]: unknown
}

export async function getThreadState(id: string): Promise<ThreadState> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/${encodeURIComponent(id)}/state`, {
    headers: getAgentHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Failed to get thread state: ${res.status}`)
  return (await res.json()) as ThreadState
}

export async function searchThreads(params: ThreadSearchParams): Promise<ThreadSearchResponse> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/search`, {
    method: 'POST',
    headers: getAgentHeaders(),
    credentials: 'include',
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error(`Failed to search threads: ${res.status}`)
  const list = await res.json() as ThreadApiResponse[]
  const items = list.map(mapThreadResponse)
  return { items, total: items.length }
}

export async function updateThread(id: string, data: Partial<ThreadSession>): Promise<ThreadSession> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/${id}`, {
    method: 'PATCH',
    headers: getAgentHeaders(),
    credentials: 'include',
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to update thread: ${res.status}`)
  return mapThreadResponse(await res.json() as ThreadApiResponse)
}

export async function deleteThread(id: string): Promise<void> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/${id}`, {
    method: 'DELETE',
    headers: getAgentHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Failed to delete thread: ${res.status}`)
}

export interface TokenUsageData {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export async function getTokenUsage(threadId: string): Promise<TokenUsageData> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/${encodeURIComponent(threadId)}/token-usage`, {
    headers: getAgentHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Failed to fetch token usage: ${res.status}`)
  return res.json()
}
