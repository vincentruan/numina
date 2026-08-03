import http from './index'

export interface ImportPreviewItem {
  temp_id: string
  name: string
  target_model: 'asset' | 'liability'
  asset_type: string
  category_hint: string
  current_value: number | null
  currency: string
  quantity: number | null
  notes: string | null
  matched_asset_id: string | null
  matched_asset_name: string | null
  action: 'update' | 'create'
  warning: string | null
  confidence: number | null
  // Liability-specific fields
  original_amount: number | null
  remaining_amount: number | null
  monthly_payment: number | null
  interest_rate: number | null
  liability_category: string | null
}

export interface ImportPreview {
  source: string
  report_date: string | null
  items: ImportPreviewItem[]
  message: string | null
  draft_id: string | null
}

export interface ConfirmResultItem {
  temp_id: string
  status: 'created' | 'updated' | 'skipped' | 'error'
  id: string | null
  name: string | null
  error: string | null
}

export interface ConfirmResponse {
  updated: number
  created: number
  skipped: number
  items: ConfirmResultItem[]
}

export interface HistoryItem {
  id: string
  source_filename: string
  source_format: string
  status: 'pending' | 'committed' | 'rolled_back'
  item_count: number
  created_at: string
  can_rollback: boolean
}

export async function parseFile(file: File): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  const resp = await http.post<ImportPreview>('/import/parse', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // AI parsing can take up to 2 minutes for large files
  })
  return resp.data
}

export async function confirmImport(
  items: ImportPreviewItem[],
  draftId?: string | null
): Promise<ConfirmResponse> {
  const resp = await http.post<ConfirmResponse>('/import/confirm', {
    items,
    draft_id: draftId,
  })
  return resp.data
}

export async function getImportHistory(): Promise<HistoryItem[]> {
  const resp = await http.get<HistoryItem[]>('/import/history')
  return resp.data
}

export async function rollbackImport(draftId: string): Promise<{ status: string; archived_count: number }> {
  const resp = await http.post(`/import/rollback/${draftId}`)
  return resp.data
}
