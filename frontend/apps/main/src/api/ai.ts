import http, { refreshTokenIfNeeded } from './index'
import type { AIReport, FinanceCoachResponse, FinanceSuggestion } from '@/types'

// ── Multi-provider config types ───────────────────────────────────────────────

export interface ProviderTestResult {
  id: string
  test_type: string
  success: boolean | null
  message: string | null
  latency_ms: number | null
  tested_at: string
}

export interface ProviderConfig {
  id: string
  name: string
  provider: string
  ai_api_key_masked: string | null
  base_url: string | null
  model_id: string | null
  vision_model_id: string | null
  timeout_seconds: number
  is_active: boolean
  max_tokens: number | null
  provider_name: string
  display_order: number
  model_2_id: string | null
  model_3_id: string | null
  model_1_capabilities: string[]
  model_2_capabilities: string[]
  model_3_capabilities: string[]
  // Circuit breaker fields (three-state model)
  circuit_state: 'closed' | 'open' | 'half_open'
  circuit_reason: string | null  // transient | permanent_auth | permanent_account
  recovery_schedule: string | null  // comma-separated time patterns like ":01,:31"
  last_failure_type: string | null
  half_open_window_start: string | null
  // Legacy circuit breaker fields (retained for backward compatibility)
  circuit_open: boolean
  circuit_open_until: string | null
  failure_count: number
  test_results: ProviderTestResult[]
}

export interface ProviderConfigCreate {
  name: string
  provider: string
  ai_api_key?: string | null
  base_url?: string | null
  model_id?: string | null
  vision_model_id?: string | null
  timeout_seconds?: number | null
  is_active?: boolean
  max_tokens?: number | null
  provider_name?: string | null
  display_order?: number | null
  model_2_id?: string | null
  model_3_id?: string | null
  model_1_capabilities?: string[] | null
  model_2_capabilities?: string[] | null
  model_3_capabilities?: string[] | null
  recovery_schedule?: string | null  // e.g., ":01,:31" for DashScope quota resets
}

export interface ProviderConfigUpdate {
  name?: string | null
  provider?: string | null
  ai_api_key?: string | null
  base_url?: string | null
  model_id?: string | null
  vision_model_id?: string | null
  timeout_seconds?: number | null
  is_active?: boolean
  max_tokens?: number | null | null
  provider_name?: string | null
  display_order?: number | null
  model_2_id?: string | null
  model_3_id?: string | null
  model_1_capabilities?: string[] | null
  model_2_capabilities?: string[] | null
  model_3_capabilities?: string[] | null
  recovery_schedule?: string | null  // e.g., ":01,:31" for DashScope quota resets
}

export const getAIConfigs = () =>
  http.get<{ configs: ProviderConfig[] }>('/ai/config')

export const createAIConfig = (payload: ProviderConfigCreate) =>
  http.post<ProviderConfig>('/ai/config', payload)

export const updateProviderConfig = (id: string, payload: ProviderConfigUpdate) =>
  http.put<ProviderConfig>(`/ai/config/${id}`, payload)

export const reorderAIConfigs = (order: string[]) =>
  http.put<{ ok: boolean }>('/ai/config/reorder', { order })

export const resetCircuitBreaker = (id: string) =>
  http.post<{ ok: boolean }>(`/ai/config/${id}/reset-circuit`)

export const deleteAIConfig = (id: string) =>
  http.delete(`/ai/config/${id}`)

/** Resolve system-default max_tokens for a model_id (from system-config.yaml).
 *  Returns ``{ max_tokens: null }`` when no prefix matches.
 *  Used by the provider form to pre-fill the max_tokens field on model_id blur.
 */
export const getProviderDefaults = (modelId: string) =>
  http.get<{ max_tokens: number | null }>('/ai/config/defaults', {
    params: { model_id: modelId },
  })

export interface ModelTestResult {
  connected: boolean
  message: string | null
  latency_ms: number | null
}

export const testProviderConfig = (id: string) =>
  http.post<ModelTestResult>(`/ai/config/${id}/test`)

// ── Legacy flat config shape (kept for backward compat) ───────────────────────
export interface AIConfig {
  id: string | null
  ai_enabled: boolean
  ai_provider: string | null
  ai_api_key_masked: string | null
  ai_base_url: string | null
  ai_model_id: string | null
  ai_vision_model_id: string | null
  ai_timeout_seconds: number
  ai_test_connected: boolean | null
  ai_test_message: string | null
  ai_test_latency_ms: number | null
  ai_test_timestamp: string | null
  ai_test_thinking_success: boolean | null
  ai_test_thinking_message: string | null
  ai_test_thinking_latency_ms: number | null
  ai_test_thinking_timestamp: string | null
  ai_vision_test_success: boolean | null
  ai_vision_test_message: string | null
  ai_vision_test_latency_ms: number | null
  ai_vision_test_timestamp: string | null
  ai_vision_text_test_success: boolean | null
  ai_vision_text_test_message: string | null
  ai_vision_text_test_latency_ms: number | null
  ai_vision_text_test_timestamp: string | null
}

export interface AIConfigUpdate {
  ai_enabled?: boolean
  ai_provider?: string | null
  ai_api_key?: string | null
  ai_base_url?: string | null
  ai_model_id?: string | null
  ai_vision_model_id?: string | null
  ai_timeout_seconds?: number | null
}

export interface AIConfigTestResult {
  connected: boolean
  message: string
  latency_ms?: number
  thinking_success?: boolean | null
  thinking_message?: string | null
  thinking_latency_ms?: number | null
  vision_success?: boolean | null
  vision_message?: string | null
  vision_latency_ms?: number | null
  vision_text_success?: boolean | null
  vision_text_message?: string | null
  vision_text_latency_ms?: number | null
}

export interface AICapability {
  id: string
  name: string
  description: string
  category: string
  ui: {
    icon: string
    color: string
    route: string | null
    input_mode: string
    placeholder: string | null
    example_questions: string[]
  }
  policy: {
    allowed_roles: string[]
    require_confirmation: boolean
    max_tokens: number
    enable_thinking: boolean
    enable_tools: string[]
  }
  skill_id: string
  harness_config: Record<string, unknown>
}

// ── Skill Management types ────────────────────────────────────────────────────

export interface SkillDefinition {
  id: string
  skill_type: 'fixed' | 'builtin' | 'custom'
  name?: string
  description?: string
  icon?: string
  color?: string
  route?: string | null
  input_mode?: 'free_text' | 'trigger'
  examples?: string[]
  is_enabled: boolean
  display_order: number
  can_edit: boolean
  can_delete: boolean
}

export interface SkillListResponse {
  fixed: SkillDefinition[]
  builtin: SkillDefinition[]
  custom: SkillDefinition[]
}

export interface CustomSkillCreate {
  skill_id: string
  name: string
  description?: string
  icon: string
  color: string
  input_mode: 'trigger' | 'free_text'
  examples?: string[]
  prompt_content: string
}

export interface CustomSkillUpdate {
  name?: string
  description?: string
  icon?: string
  color?: string
  input_mode?: 'trigger' | 'free_text'
  examples?: string[]
  prompt_content?: string
}

// Backend response shapes
interface _BackendTestResult {
  id: string
  test_type: string
  success: boolean | null
  message: string | null
  latency_ms: number | null
  tested_at: string
}

interface _BackendConfig {
  id: string
  name: string
  provider: string
  ai_api_key_masked: string | null
  base_url: string | null
  model_id: string | null
  vision_model_id: string | null
  timeout_seconds: number | null
  is_active: boolean
  test_results: _BackendTestResult[]
}

function _findTest(results: _BackendTestResult[], type: string) {
  return results.find((r) => r.test_type === type) ?? null
}

function _mapConfig(cfg: _BackendConfig): AIConfig {
  const main = _findTest(cfg.test_results, 'main')
  const thinking = _findTest(cfg.test_results, 'thinking')
  const vision = _findTest(cfg.test_results, 'vision')
  const visionText = _findTest(cfg.test_results, 'vision_text')
  return {
    id: cfg.id,
    ai_enabled: cfg.is_active,
    ai_provider: cfg.provider,
    ai_api_key_masked: cfg.ai_api_key_masked,
    ai_base_url: cfg.base_url,
    ai_model_id: cfg.model_id,
    ai_vision_model_id: cfg.vision_model_id,
    ai_timeout_seconds: cfg.timeout_seconds ?? 60,
    ai_test_connected: main?.success ?? null,
    ai_test_message: main?.message ?? null,
    ai_test_latency_ms: main?.latency_ms ?? null,
    ai_test_timestamp: main?.tested_at ?? null,
    ai_test_thinking_success: thinking?.success ?? null,
    ai_test_thinking_message: thinking?.message ?? null,
    ai_test_thinking_latency_ms: thinking?.latency_ms ?? null,
    ai_test_thinking_timestamp: thinking?.tested_at ?? null,
    ai_vision_test_success: vision?.success ?? null,
    ai_vision_test_message: vision?.message ?? null,
    ai_vision_test_latency_ms: vision?.latency_ms ?? null,
    ai_vision_test_timestamp: vision?.tested_at ?? null,
    ai_vision_text_test_success: visionText?.success ?? null,
    ai_vision_text_test_message: visionText?.message ?? null,
    ai_vision_text_test_latency_ms: visionText?.latency_ms ?? null,
    ai_vision_text_test_timestamp: visionText?.tested_at ?? null,
  }
}

function _emptyConfig(): AIConfig {
  return {
    id: null, ai_enabled: false, ai_provider: null, ai_api_key_masked: null,
    ai_base_url: null, ai_model_id: null, ai_vision_model_id: null, ai_timeout_seconds: 60,
    ai_test_connected: null, ai_test_message: null, ai_test_latency_ms: null, ai_test_timestamp: null,
    ai_test_thinking_success: null, ai_test_thinking_message: null, ai_test_thinking_latency_ms: null, ai_test_thinking_timestamp: null,
    ai_vision_test_success: null, ai_vision_test_message: null, ai_vision_test_latency_ms: null, ai_vision_test_timestamp: null,
    ai_vision_text_test_success: null, ai_vision_text_test_message: null, ai_vision_text_test_latency_ms: null, ai_vision_text_test_timestamp: null,
  }
}

// Cached config id for update calls within the same session
let _cachedConfigId: string | null = null

export async function getAIConfig(): Promise<{ data: AIConfig }> {
  const res = await http.get<{ configs: _BackendConfig[] }>('/ai/config')
  const configs = res.data.configs ?? []
  const active = configs.find((c) => c.is_active) ?? configs[0] ?? null
  if (!active) return { data: _emptyConfig() }
  _cachedConfigId = active.id
  return { data: _mapConfig(active) }
}

export const getAICapabilities = () =>
  http.get<AICapability[]>('/ai/capabilities')

export async function updateAIConfig(data: AIConfigUpdate): Promise<{ data: AIConfig }> {
  const backendPayload: Record<string, unknown> = {}
  if (data.ai_provider !== undefined) backendPayload.provider = data.ai_provider
  if (data.ai_api_key !== undefined) backendPayload.ai_api_key = data.ai_api_key
  if (data.ai_base_url !== undefined) backendPayload.base_url = data.ai_base_url
  if (data.ai_model_id !== undefined) backendPayload.model_id = data.ai_model_id
  if (data.ai_vision_model_id !== undefined) backendPayload.vision_model_id = data.ai_vision_model_id
  if (data.ai_timeout_seconds !== undefined) backendPayload.timeout_seconds = data.ai_timeout_seconds
  if (data.ai_enabled !== undefined) backendPayload.is_active = data.ai_enabled

  if (_cachedConfigId !== null) {
    const res = await http.put<_BackendConfig>(`/ai/config/${_cachedConfigId}`, backendPayload)
    return { data: _mapConfig(res.data) }
  }

  // No existing config — create one
  const res = await http.post<_BackendConfig>('/ai/config', {
    name: 'default',
    provider: (data.ai_provider as string) ?? 'openai',
    ai_api_key: data.ai_api_key ?? undefined,
    base_url: data.ai_base_url ?? undefined,
    model_id: data.ai_model_id ?? undefined,
    vision_model_id: data.ai_vision_model_id ?? undefined,
    timeout_seconds: data.ai_timeout_seconds ?? 60,
    is_active: data.ai_enabled ?? false,
  })
  _cachedConfigId = res.data.id
  return { data: _mapConfig(res.data) }
}

function _testUrl(): string {
  if (_cachedConfigId === null) throw new Error('AI config not loaded')
  return `/ai/config/${_cachedConfigId}/test`
}

export const revealAIKey = (configId: string) =>
  http.get<{ api_key: string }>(`/ai/config/${configId}/reveal-key`)

export const testAIConfig = () => http.post<AIConfigTestResult>(_testUrl())
export const testMainModelOnly = () => http.post<AIConfigTestResult>(_testUrl())
export const testThinkingOnly = () => http.post<AIConfigTestResult>(_testUrl())
export const testVisionModelOnly = () => http.post<AIConfigTestResult>(_testUrl())
export const testVisionTextOCR = () => http.post<AIConfigTestResult>(_testUrl())

export interface AIReportResponse {
  report: AIReport | null
  generated_at?: string
}

export const getAIReport = () =>
  http.get<AIReportResponse>('/ai/report')

export interface AIMarkdownResponse {
  content: string
  filename: string
  generated_at: string
  file_size: number
}

export const getAIReportMarkdown = () =>
  http.get<AIMarkdownResponse>('/ai/report/markdown')


export interface AssetSuggestRequest {
  name: string
  category: string
  asset_type: string
}

export interface AssetSuggestResult {
  expected_lifespan_years: number | null
  annual_maintenance_cost_hint: string
  usage_frequency: string
  suggested_tags: string[]
  notes_hint: string
}

export const suggestAssetFields = (data: AssetSuggestRequest) =>
  http.post<AssetSuggestResult>('/ai/suggest/asset', data)

// P0-#3: Timeout wrapper for streaming fetch (matches backend 120s timeout)
const STREAM_TIMEOUT_MS = 120000
function combineSignalWithTimeout(signal?: AbortSignal): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(STREAM_TIMEOUT_MS)
  if (!signal) return timeoutSignal
  // If both signals exist, create combined abort controller
  const combinedController = new AbortController()
  signal.addEventListener('abort', () => combinedController.abort(signal.reason))
  timeoutSignal.addEventListener('abort', () => combinedController.abort(timeoutSignal.reason))
  return combinedController.signal
}



// ── AI Task Status ──────────────────────────────────────────────────────────

export interface AITaskStatus {
  status: 'idle' | 'running' | 'post_processing' | 'queued' | 'completed' | 'failed' | 'timeout' | 'cancelled'
  task_id?: string
  session_id?: string
  started_at?: string
  queue_position?: number | null
}

export async function getAITask(capability: string): Promise<AITaskStatus> {
  const res = await http.get<AITaskStatus>(`/ai/tasks/${capability}`)
  return res.data
}

export async function getAITaskSession(
  capability: string,
): Promise<{ session_id: string | null; task_id: string | null }> {
  const res = await http.get<{ session_id: string | null; task_id: string | null }>(
    `/ai/tasks/${capability}/session`,
  )
  return res.data
}

export async function cancelAITask(capability: string): Promise<{ ok: boolean }> {
  const res = await http.post<{ ok: boolean }>(`/ai/tasks/${capability}/cancel`)
  return res.data
}

// Streaming fetch helper — returns a ReadableStream reader.
// Auth uses httpOnly cookies (withCredentials), no Bearer token needed.
// Auto-refreshes token on 401 before retrying.
export async function startAIStream(
  endpoint: string,
  signal?: AbortSignal,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  let res = await fetch(`/api/v1${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    signal,
  })

  if (res.status === 401) {
    try {
      await refreshTokenIfNeeded()
    } catch {
      throw new Error('401')
    }
    res = await fetch(`/api/v1${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      signal,
    })
  }

  if (!res.ok) throw new Error(`${res.status}`)
  return res.body!.getReader()
}

// NDJSON event stream — returns reader for application/x-ndjson responses.
// Returns { reader, queued, queuePosition } — if queued=true, no stream is open.
// Auto-refreshes token on 401 before retrying.
export async function startAIEventStream(
  endpoint: string,
  signal?: AbortSignal,
): Promise<
  | { queued: false; reader: ReadableStreamDefaultReader<Uint8Array> }
  | { queued: true; taskId: string; queuePosition: number | null }
> {
  const doFetch = () =>
    fetch(`/api/v1${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      signal,
    })

  let res = await doFetch()

  if (res.status === 401) {
    try {
      await refreshTokenIfNeeded()
    } catch {
      throw new Error('401')
    }
    res = await doFetch()
  }

  if (res.status === 202) {
    const body = await res.json()
    return { queued: true, taskId: body.task_id, queuePosition: body.queue_position ?? null }
  }
  if (!res.ok) throw new Error(`${res.status}`)
  if (!res.body) throw new Error('Response body is null')
  return { queued: false, reader: res.body.getReader() }
}

/**
 * Start an agent-first task stream.
 *
 * Unlike capability-based startAIEventStream, this calls /ai/chat/stream with
 * agent_id routing, which activates per-agent skill scoping in agent_dispatch.
 * The triggerMessage is typically a skill trigger phrase (e.g. "生成资产报告").
 */
export async function startAgentTaskStream(
  agentId: string,
  triggerMessage: string,
  signal?: AbortSignal,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const payload = {
    question: triggerMessage,
    deep_think: false,
    web_search: false,
    agent_id: agentId,
  }

  let res = await fetch('/api/v1/ai/chat/stream', {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify(payload),
    signal,
  })

  if (res.status === 401) {
    try {
      await refreshTokenIfNeeded()
    } catch {
      throw new Error('401')
    }
    res = await fetch('/api/v1/ai/chat/stream', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify(payload),
      signal,
    })
  }

  if (!res.ok) throw new Error(`${res.status}`)
  if (!res.body) throw new Error('Response body is null')
  return res.body.getReader()
}

// ── MCP Server Management ─────────────────────────────────────────────────────

export interface MCPServer {
  id: string
  name: string
  url: string
  transport: 'sse' | 'stdio'
  env_vars: Record<string, string>  // empty object when not set or caller lacks permission
  is_enabled: boolean
  mcp_type: 'general' | 'websearch'
}

export interface MCPServerCreate {
  name: string
  url: string
  transport: 'sse' | 'stdio'
  env_vars?: Record<string, string> | null
  is_enabled?: boolean
  mcp_type?: 'general' | 'websearch'
}

export interface MCPServerUpdate {
  name?: string
  url?: string
  transport?: 'sse' | 'stdio'
  env_vars?: Record<string, string> | null
  is_enabled?: boolean
  mcp_type?: 'general' | 'websearch'
}

export const getMCPServers = () => http.get<MCPServer[]>('/ai/mcp')
export const createMCPServer = (data: MCPServerCreate) => http.post<MCPServer>('/ai/mcp', data)
export const updateMCPServer = (id: string, data: MCPServerUpdate) =>
  http.put<MCPServer>(`/ai/mcp/${id}`, data)
export const deleteMCPServer = (id: string) => http.delete(`/ai/mcp/${id}`)

// ── Skill Config Management ───────────────────────────────────────────────────

export interface SkillConfig {
  capability: string
  is_enabled: boolean
  custom_prompt: string | null
  default_prompt: string | null
}

export interface SkillConfigUpdate {
  is_enabled?: boolean
  custom_prompt?: string | null
}

export const getSkills = () => http.get<SkillConfig[]>('/ai/skills')
export const updateSkill = (capability: string, data: SkillConfigUpdate) =>
  http.put<SkillConfig>(`/ai/skills/${capability}`, data)
export const resetSkillPrompt = (capability: string) =>
  http.delete<SkillConfig>(`/ai/skills/${capability}/prompt`)

// ── Skill Management ──────────────────────────────────────────────────────────

export const getSkillsGrouped = () =>
  http.get<SkillListResponse>('/ai/skills/grouped').then(res => res.data)

export const createCustomSkill = (payload: CustomSkillCreate) =>
  http.post<SkillDefinition>('/ai/skills/custom', payload)

export const updateCustomSkill = (skillId: string, payload: CustomSkillUpdate) =>
  http.put<SkillDefinition>(`/ai/skills/custom/${skillId}`, payload)

export const deleteCustomSkill = (skillId: string) =>
  http.delete<{ ok: boolean }>(`/ai/skills/custom/${skillId}`)

export const toggleSkill = (skillId: string, isEnabled: boolean) =>
  http.put<SkillDefinition>(`/ai/skills/${skillId}/toggle`, { is_enabled: isEnabled })

export const reorderSkills = (skillIds: string[]) =>
  http.put<{ ok: boolean }>('/ai/skills/reorder', { skill_ids: skillIds })

// ── Skill Install & AI Create ──────────────────────────────────────────────────

export interface AICreateResponse {
  content: string
  parsed_name: string | null
  parsed_description: string | null
}

export interface RawSkillSavePayload {
  skill_id: string
  content: string
  icon: string
  color: string
}

export const installSkill = (command: string) =>
  http.post<SkillDefinition>('/ai/skills/install', { command }).then(res => res.data)

export const aiCreateSkill = (description: string) =>
  http.post<AICreateResponse>('/ai/skills/ai-create', { description }).then(res => res.data)

export const saveRawSkill = (payload: RawSkillSavePayload) =>
  http.post<SkillDefinition>('/ai/skills/custom/raw', payload).then(res => res.data)

// ── Chat Attachment Upload ─────────────────────────────────────────────────────

export interface ChatAttachmentResponse {
  file_id: string
  url: string
  filename: string
  size_bytes: number
}

export const uploadChatAttachment = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return http.post<ChatAttachmentResponse>('/ai/chat/attachments', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(res => res.data)
}

// ── Skill Install from Artifact ────────────────────────────────────────────────

export interface InstallFromArtifactPayload {
  session_id: string
  artifact_path: string
}

export const installSkillFromArtifact = (payload: InstallFromArtifactPayload) =>
  http.post<SkillDefinition>('/ai/skills/install-from-artifact', payload).then(res => res.data)

// ── finance_coach (D2/A1a dashboard card, Plan B T5) ─────────────────────────
//
// The backend /ai/finance-coach/generate endpoint returns either:
//   - cached JSON 200 (within 8h): { status: "cached", generated_at, report: { suggestions: [...] } }
//   - a fresh SSE stream whose terminal finance_coach.result frame carries the
//     same report shape.
// Auth is cookie-based (withCredentials), like startAIStream — no Bearer header.
// On 401 we refresh the cookie and retry once. On any other error we reject so
// the card hides silently (spec §7.2 design-lens).
export async function getFinanceCoach(force = false): Promise<FinanceCoachResponse> {
  const doFetch = () =>
    fetch(`/api/v1/ai/finance-coach/generate?force=${force}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    })

  let res = await doFetch()
  if (res.status === 401) {
    try {
      await refreshTokenIfNeeded()
    } catch {
      throw new Error('401')
    }
    res = await doFetch()
  }
  if (!res.ok) throw new Error(`finance_coach ${res.status}`)

  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    return (await res.json()) as FinanceCoachResponse
  }

  // Streaming response — consume SSE until the finance_coach.result frame.
  // Frames look like: event: custom\ndata: {"type":"finance_coach.result","payload":{"suggestions":[...]}}\n\n
  const reader = res.body?.getReader()
  if (!reader) throw new Error('no stream body')
  const decoder = new TextDecoder()
  let buf = ''
  let suggestions: FinanceSuggestion[] = []
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const frames = buf.split('\n\n')
    buf = frames.pop() || ''
    for (const frame of frames) {
      const dataLine = frame.split('\n').find((l) => l.startsWith('data: '))
      if (!dataLine) continue
      try {
        const data = JSON.parse(dataLine.slice(6))
        if (data.type === 'finance_coach.result' && data.payload?.suggestions) {
          suggestions = data.payload.suggestions
        }
      } catch {
        /* ignore malformed frame */
      }
    }
  }
  return { status: 'streaming', report: { suggestions } }
}

// ── /ai/context (A1b greenfield chat prefill, Plan B T6) ─────────────────────
//
// Fetch the family-scoped entity context to inject as the first user turn.
// Cookie auth (credentials:'include'), mirroring getFinanceCoach. The backend
// wraps the response in the EnvelopeResponse ({code:"OK", data:{source,summary}}),
// so unwrap .data here. signal allows the caller (useAiContext) to abort after 3s.
export interface AiContextResponse {
  source: string
  summary: string
}

export async function getAiContext(
  source: string,
  id: string,
  signal?: AbortSignal,
): Promise<AiContextResponse> {
  let res = await fetch(
    `/api/v1/ai/context?source=${encodeURIComponent(source)}&id=${encodeURIComponent(id)}`,
    { method: 'GET', credentials: 'include', signal },
  )
  if (res.status === 401) {
    try {
      await refreshTokenIfNeeded()
    } catch {
      throw new Error('401')
    }
    res = await fetch(
      `/api/v1/ai/context?source=${encodeURIComponent(source)}&id=${encodeURIComponent(id)}`,
      { method: 'GET', credentials: 'include', signal },
    )
  }
  if (!res.ok) throw new Error(`ai/context ${res.status}`)
  const body = (await res.json()) as { code?: string; data?: AiContextResponse } | AiContextResponse
  // Unwrap the EnvelopeResponse if present (backend default_response_class).
  if (body && typeof body === 'object' && 'data' in body && body.data) {
    return body.data
  }
  return body as AiContextResponse
}
