import http from './index'

export interface ImportPreviewItem {
  temp_id: string
  name: string
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
}

export interface ImportPreview {
  source: string
  report_date: string | null
  items: ImportPreviewItem[]
}

export interface ImportConfirmResult {
  updated: number
  created: number
  skipped: number
}

export async function parseReport(file: File): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  const resp = await http.post<ImportPreview>('/import/parse-pdf', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 35000,
  })
  return resp.data
}

export async function confirmImport(items: ImportPreviewItem[]): Promise<ImportConfirmResult> {
  const resp = await http.post<ImportConfirmResult>('/import/confirm', { items })
  return resp.data
}
