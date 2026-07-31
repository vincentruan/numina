import http from './index'

export interface ChildManifestoData {
  manifesto_id: string
  title: string
  body: string
  template_id: string
  signed: boolean
  signer_names: string[]
  signed_at?: string | null
}

export interface TrackableClausesData {
  has_trackable: boolean
  trackable_clause_indices: number[]
}

export function getChildManifesto() {
  return http.get<ChildManifestoData>('/child/manifesto')
}

export function signChildManifesto(signatureData: string | null) {
  return http.post('/child/manifesto/sign', { signature_data: signatureData })
}

export function getTrackableClauses() {
  return http.get<TrackableClausesData>('/child/manifesto/trackable-clauses')
}
