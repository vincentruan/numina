import http from './index'
import type {
  Manifesto,
  ManifestoDashboardSummary,
  ManifestoFeedback,
  ManifestoVersionHistoryItem,
  UnsignedManifestoCheck,
} from '@/types/manifesto'

export interface CreateManifestoRequest {
  template_id: string
  title: string
  body: string
  change_type: 'initial' | 'minor' | 'major'
  trackable_clause_indices?: number[] | null
  signing_deadline?: string | null
}

export interface PublishUpdateRequest {
  template_id: string
  title: string
  body: string
  change_type: 'minor' | 'major'
  trackable_clause_indices?: number[] | null
  signing_deadline?: string | null
}

export function createManifesto(req: CreateManifestoRequest) {
  return http.post<Manifesto>('/family/manifesto', req)
}

export function getCurrentManifesto() {
  return http.get<Manifesto>('/family/manifesto', { _silentErrorCodes: ['MANIFESTO_NOT_FOUND'] })
}

export function getUnsignedCheck() {
  return http.get<UnsignedManifestoCheck>('/family/manifesto/unsigned-check')
}

export function publishUpdate(req: PublishUpdateRequest) {
  return http.patch<Manifesto>('/family/manifesto', req)
}

export function signManifesto(signatureData: string | null) {
  return http.post<Manifesto>('/family/manifesto/sign', { signature_data: signatureData })
}

export function getVersionHistory() {
  return http.get<ManifestoVersionHistoryItem[]>('/family/manifesto/history')
}

export function submitFeedback(content: string) {
  return http.post<ManifestoFeedback>('/family/manifesto/feedback', { content })
}

export function getFeedbackList() {
  return http.get<ManifestoFeedback[]>('/family/manifesto/feedback', {
    _silentErrorCodes: ['MANIFESTO_NOT_FOUND'],
  })
}

export function getDashboardSummary() {
  return http.get<ManifestoDashboardSummary>('/family/manifesto/dashboard-summary')
}
