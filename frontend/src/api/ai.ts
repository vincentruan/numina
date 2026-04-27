import http from './index'
import type { AIReport, AssetAlert, DisposalSuggestion, LiabilityAdviceResponse, AllocationDriftResponse, ChatMessage } from '@/types'

export interface AIConfig {
  ai_enabled: boolean
  ai_provider: string | null
  ai_api_key_masked: string | null
  ai_base_url: string | null
  ai_model_id: string | null
  ai_vision_model_id: string | null
  // 主模型连接测试结果（独立）
  ai_test_connected: boolean | null
  ai_test_message: string | null
  ai_test_latency_ms: number | null
  ai_test_timestamp: string | null
  // 主模型thinking测试结果（独立）
  ai_test_thinking_success: boolean | null
  ai_test_thinking_message: string | null
  ai_test_thinking_latency_ms: number | null
  ai_test_thinking_timestamp: string | null
  // 图像模型测试结果（独立存储）
  ai_vision_test_success: boolean | null
  ai_vision_test_message: string | null
  ai_vision_test_latency_ms: number | null
  ai_vision_test_timestamp: string | null
}

export interface AIConfigUpdate {
  ai_enabled?: boolean
  ai_provider?: string | null
  ai_api_key?: string | null
  ai_base_url?: string | null
  ai_model_id?: string | null
  ai_vision_model_id?: string | null
}

export interface AIConfigTestResult {
  connected: boolean // 连接测试成功与否
  message: string
  latency_ms?: number
  // 思考能力测试结果（独立）
  thinking_success?: boolean | null
  thinking_message?: string | null
  thinking_latency_ms?: number | null
  // 图像模型测试结果（独立）
  vision_success?: boolean | null
  vision_message?: string | null
  vision_latency_ms?: number | null
}

export const getAIConfig = () =>
  http.get<AIConfig>('/ai/config')

export const updateAIConfig = (data: AIConfigUpdate) =>
  http.put<AIConfig>('/ai/config', data)

export const testAIConfig = () =>
  http.post<AIConfigTestResult>('/ai/config/test')

export const testMainModelOnly = () =>
  http.post<AIConfigTestResult>('/ai/config/test/main')

export const testThinkingOnly = () =>
  http.post<AIConfigTestResult>('/ai/config/test/thinking')

export const testVisionModelOnly = () =>
  http.post<AIConfigTestResult>('/ai/config/test/vision')

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

export const getChatHistory = () =>
  http.get<ChatMessage[]>('/ai/chat/history')

export const clearChatHistory = () =>
  http.delete('/ai/chat/history')

export const markChatRead = () =>
  http.put('/ai/chat/read')

export const createWsTicket = () =>
  http.post<{ ticket: string }>('/ai/report/ws-ticket')
