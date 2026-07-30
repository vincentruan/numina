import http from './index'

// ── ASR Provider Config types ─────────────────────────────────────────────────

export interface ASRProviderConfig {
  id: string
  name: string
  provider: string
  ai_api_key_masked: string | null
  base_url: string | null
  model_id: string | null
  model_2_id: string | null
  model_3_id: string | null
  is_active: boolean
  display_order: number
  circuit_state: 'closed' | 'open' | 'half_open'
  failure_count: number
  last_failure_at: string | null
  test_passed: boolean | null
  test_message: string | null
  test_latency_ms: number | null
  tested_at: string | null
}

export interface ASRConfigCreate {
  name: string
  provider: string
  ai_api_key?: string | null
  base_url?: string | null
  model_id?: string | null
  model_2_id?: string | null
  model_3_id?: string | null
  display_order?: number | null
}

export interface ASRConfigUpdate {
  name?: string | null
  provider?: string | null
  ai_api_key?: string | null
  base_url?: string | null
  model_id?: string | null
  model_2_id?: string | null
  model_3_id?: string | null
  is_active?: boolean | null
  display_order?: number | null
}

export interface ASRDiffOp {
  op: 'equal' | 'sub' | 'ins' | 'del'
  ref: string | null
  hyp: string | null
}

export interface ASRLangTestResult {
  language: string
  reference: string
  transcribed: string
  error_rate_pct: number
  error_count: number
  reference_length: number
  passed: boolean
  ops: ASRDiffOp[]
  latency_ms: number | null
  error: string | null
}

export interface ASRTestResult {
  success: boolean
  message: string
  language_results: ASRLangTestResult[]
}

export interface ASRStatus {
  available: boolean
  reason: string | null
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const getASRConfigs = () =>
  http.get<{ configs: ASRProviderConfig[] }>('/asr/config')

export const createASRConfig = (payload: ASRConfigCreate) =>
  http.post<ASRProviderConfig>('/asr/config', payload)

export const updateASRConfig = (id: string, payload: ASRConfigUpdate) =>
  http.put<ASRProviderConfig>(`/asr/config/${id}`, payload)

export const deleteASRConfig = (id: string) =>
  http.delete(`/asr/config/${id}`)

export const testASRConfig = (id: string) =>
  http.post<ASRTestResult>(`/asr/config/${id}/test`)

export const getASRStatus = () =>
  http.get<ASRStatus>('/asr/status')

export const transcribeAudio = (file: File) => {
  const formData = new FormData()
  formData.append('audio', file)
  return http.post<{ text: string }>('/asr/transcribe', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(res => res.data)
}
