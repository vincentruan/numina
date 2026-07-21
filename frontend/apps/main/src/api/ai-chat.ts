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
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Family-Id': familyId,
  }
  // X-User-Id is required so the agent can persist user_id on session rows
  // (ai_chat_sessions). Without it, getSystemDefaultSession - which filters
  // by user_id - never matches, breaking the cache-hit path in handleNuminaConsult.
  const userId = authStore.user?.id
  if (userId) {
    headers['X-User-Id'] = String(userId)
  }
  return headers
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
    is_branch: (r.metadata?.is_branch as boolean) || false,
    parent_thread_id: (r.metadata?.parent_thread_id as string) || undefined,
    created_at: r.created_at,
    updated_at: r.updated_at,
  }
}

export async function createThread(source?: string): Promise<ThreadSession> {
  const res = await fetch(`${getAgentApiBase()}/api/threads`, {
    method: 'POST',
    headers: getAgentHeaders(),
    credentials: 'include',
    body: JSON.stringify(source ? { metadata: { source } } : {}),
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

/**
 * Minimal runtime shape check for a thread-state response.
 *
 * The agent returns a JSON object with ``channel_values`` under ``values``;
 * ``as ThreadState`` alone would pass ``null`` / arrays / strings through and
 * crash the consumer's ``state.values?.messages`` access. We avoid pulling in
 * Zod just for this one boundary - a structural guard is enough.
 */
function asThreadState(raw: unknown): ThreadState {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('Unexpected thread state response shape')
  }
  const obj = raw as Record<string, unknown>
  if (!obj.values || typeof obj.values !== 'object') {
    throw new Error('Thread state response missing values')
  }
  return raw as ThreadState
}

export async function getThreadState(id: string): Promise<ThreadState> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/${encodeURIComponent(id)}/state`, {
    headers: getAgentHeaders(),
    credentials: 'include',
  })
  if (!res.ok) throw new Error(`Failed to get thread state: ${res.status}`)
  return asThreadState(await res.json())
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

// ---------------------------------------------------------------------------
// Compact (D2 DeerFlow sync) — POST /api/threads/{id}/compact.
// Summarizes old history (RemoveMessage(ALL) + summary_text + preserved tail)
// via the backend's canonical compact_thread_context wrapper. Cookie auth +
// X-Family-Id, mirroring polishInputDraft / branchThreadFromTurn. Backend:
// routers/threads.py compact_thread_endpoint + services/compact_service.py.
// ---------------------------------------------------------------------------

export interface ThreadCompactResult {
  compacted: boolean
  reason: string | null
  removed_count: number
  preserved_count: number
  summary_updated: boolean
  checkpoint_id: string | null
  total_tokens: number
}

export async function compactThread(threadId: string): Promise<ThreadCompactResult> {
  const res = await fetch(`${getAgentApiBase()}/api/threads/${encodeURIComponent(threadId)}/compact`, {
    method: 'POST',
    headers: getAgentHeaders(),
    credentials: 'include',
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    let detail = `Failed to compact thread (${res.status})`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string' && body.detail) detail = body.detail
    } catch {
      // ignore parse failure, use fallback detail
    }
    throw new Error(detail)
  }
  return res.json() as Promise<ThreadCompactResult>
}

// ---------------------------------------------------------------------------
// Input polish (D3 DeerFlow sync) — frontend-direct, cookie auth + X-Family-Id.
// Stateless single LLM call; no thread run, no persistence. Mirrors
// runs_stream.py's verify_family_token path. Backend: routers/input_polish.py.
// ---------------------------------------------------------------------------

export interface InputPolishResult {
  rewritten_text: string
  changed: boolean
}

export async function polishInputDraft(text: string, signal?: AbortSignal): Promise<InputPolishResult> {
  const res = await fetch(`${getAgentApiBase()}/api/input-polish`, {
    method: 'POST',
    headers: getAgentHeaders(),
    credentials: 'include',
    body: JSON.stringify({ text }),
    signal,
  })
  if (!res.ok) throw new Error(`Input polish failed: ${res.status}`)
  return res.json()
}

// ---------------------------------------------------------------------------
// Branch API (DeerFlow threads/api.ts:71-97)
// ---------------------------------------------------------------------------

export interface ThreadBranchResponse {
  thread_id: string
  parent_thread_id: string
  parent_checkpoint_id: string
  branched_from_message_id: string
  /**
   * Sandbox artifact clone outcome (U1/U5). Mirrors the backend
   * `WorkspaceCloneMode` Literal (server/apps/agent/routers/threads.py) so a
   * typo on either side is a compile-time break, not a silent fall-through to
   * the no-warning branch. Keep in sync with `branchCloneWarnKey` in
   * AIChatBox.vue.
   */
  workspace_clone_mode?: WorkspaceCloneMode
}

/**
 * Sandbox artifact clone outcome — single source of truth for the values that
 * cross the backend->frontend boundary. Mirror of the backend
 * `WorkspaceCloneMode` Literal.
 */
export type WorkspaceCloneMode =
  | 'current_thread_best_effort'
  | 'skipped_historical_turn'
  | 'not_found'
  | 'failed'

export interface BranchThreadFromTurnInput {
  messageId: string
  messageIds?: string[]
  title?: string
}

export async function branchThreadFromTurn(
  threadId: string,
  input: BranchThreadFromTurnInput,
): Promise<ThreadBranchResponse> {
  const res = await fetch(
    `${getAgentApiBase()}/api/threads/${encodeURIComponent(threadId)}/branches`,
    {
      method: 'POST',
      headers: getAgentHeaders(),
      credentials: 'include',
      body: JSON.stringify({
        message_id: input.messageId,
        message_ids: input.messageIds ?? [input.messageId],
        ...(input.title ? { title: input.title } : {}),
      }),
    },
  )
  if (!res.ok) {
    let detail = `Failed to branch conversation (${res.status})`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string' && body.detail) detail = body.detail
    } catch {
      // ignore parse failure, use fallback detail
    }
    throw new Error(detail)
  }
  return res.json() as Promise<ThreadBranchResponse>
}
