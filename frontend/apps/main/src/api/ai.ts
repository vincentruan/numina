import http from './index'
import type { AIReport, AssetAlert, DisposalSuggestion, LiabilityAdviceResponse, AllocationDriftResponse, ChatMessage } from '@/types'

// Frontend-facing flat config shape (mapped from backend multi-config model)
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

export const generateAIReport = () =>
  http.post<AIReportResponse>('/ai/report/generate')

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

// Asset alerts
export const getAssetAlerts = () =>
  http.get<AssetAlert[]>('/ai/asset-alerts')

export const refreshAssetAlerts = () =>
  http.post('/ai/asset-alerts/refresh')

export const dismissAssetAlert = (id: string) =>
  http.post(`/ai/asset-alerts/${id}/dismiss`)

// Disposal suggestions
export const getDisposalSuggestions = () =>
  http.get<DisposalSuggestion[]>('/ai/disposal-suggestions')

export const refreshDisposalSuggestions = () =>
  http.post('/ai/disposal-suggestions/refresh')

export const dismissDisposalSuggestion = (id: string) =>
  http.post(`/ai/disposal-suggestions/${id}/dismiss`)

// Liability advice
export const getLiabilityAdvice = () =>
  http.get<LiabilityAdviceResponse>('/ai/liability-advice')

// Allocation target & drift
export const getAllocationTarget = () =>
  http.get<{ has_target: boolean; category_targets?: Record<string, number>; drift_threshold?: number }>('/ai/allocation-target')

export const setAllocationTarget = (data: { category_targets: Record<string, number>; drift_threshold: number }) =>
  http.put('/ai/allocation-target', data)

export const checkAllocationDrift = () =>
  http.get<AllocationDriftResponse>('/ai/allocation-target/check')

// Chat
export const sendChatMessage = (question: string, signal?: AbortSignal) =>
  http.post<{ question: string; answer: string; message_id: string }>('/ai/chat', { question }, { signal })

export function sendChatMessageStream(
  question: string,
  deepThink: boolean,
  signal?: AbortSignal,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  return fetch('/api/v1/ai/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ question, deep_think: deepThink }),
    signal,
  }).then((res) => {
    if (!res.ok) throw new Error(`${res.status}`)
    if (!res.body) throw new Error('streaming_not_supported')
    return res.body.getReader()
  })
}

export const getChatHistory = () =>
  http.get<ChatMessage[]>('/ai/chat/history')

export const clearChatHistory = () =>
  http.delete('/ai/chat/history')

export const markChatRead = () =>
  http.put('/ai/chat/read')

export const createWsTicket = () =>
  http.post<{ ticket: string }>('/ai/report/ws-ticket')

// ── AI Task Status ──────────────────────────────────────────────────────────

export interface AITaskStatus {
  status: 'idle' | 'running' | 'completed' | 'failed' | 'timeout'
  task_id?: string
  session_id?: string
  started_at?: string
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

// Streaming fetch helper — returns a ReadableStream reader.
// Auth uses httpOnly cookies (withCredentials), no Bearer token needed.
export function startAIStream(
  endpoint: string,
  signal?: AbortSignal,
): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  return fetch(`/api/v1${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    signal,
  }).then((res) => {
    if (!res.ok) throw new Error(`${res.status}`)
    return res.body!.getReader()
  })
}

// ── MCP Server Management ─────────────────────────────────────────────────────

export interface MCPServer {
  id: string
  name: string
  url: string
  transport: 'sse' | 'stdio'
  env_vars: Record<string, string>  // empty object when not set or caller lacks permission
  is_enabled: boolean
}

export interface MCPServerCreate {
  name: string
  url: string
  transport: 'sse' | 'stdio'
  env_vars?: Record<string, string> | null
  is_enabled?: boolean
}

export interface MCPServerUpdate {
  name?: string
  url?: string
  transport?: 'sse' | 'stdio'
  env_vars?: Record<string, string> | null
  is_enabled?: boolean
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
