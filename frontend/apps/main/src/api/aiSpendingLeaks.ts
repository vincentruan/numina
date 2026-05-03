import http from './index'

export interface SpendingLeakItem {
  id: string
  asset_id: string
  asset_name: string
  leak_type: 'high_idle_cost' | 'redundant' | 'high_maintenance'
  severity: 'low' | 'medium' | 'high'
  estimated_annual_waste: number | null
  suggestion: string | null
  created_at: string
}

export const getSpendingLeaks = (): Promise<SpendingLeakItem[]> =>
  http.get('/ai/spending-leaks')

export const refreshSpendingLeaks = (): Promise<{ refreshed: number }> =>
  http.post('/ai/spending-leaks/refresh')

export const dismissSpendingLeak = (id: string): Promise<{ ok: boolean }> =>
  http.post(`/ai/spending-leaks/${id}/dismiss`)
