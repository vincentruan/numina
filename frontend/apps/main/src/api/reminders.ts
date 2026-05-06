import http from './index'

export interface ReminderResponse {
  id: string
  family_id: string
  reminder_type: 'large_purchase' | 'allocation_drift' | 'expiring_soon' | 'maturity'
  title: string
  body: string
  severity: 'info' | 'warning' | 'critical'
  asset_id: string | null
  status: 'active' | 'dismissed' | 'resolved'
  dismissed_at: string | null
  resolved_at: string | null
  created_at: string
}

export interface ReminderSummary {
  large_purchase: number
  allocation_drift: number
  expiring_soon: number
  maturity: number
  total: number
}

export const remindersApi = {
  getSummary(): Promise<ReminderSummary> {
    return http.get<ReminderSummary>('/reminders/summary').then((r) => r.data)
  },
  list(status = 'active'): Promise<ReminderResponse[]> {
    return http.get<ReminderResponse[]>('/reminders', { params: { status } }).then((r) => r.data)
  },
  dismiss(id: string): Promise<ReminderResponse> {
    return http.patch<ReminderResponse>(`/reminders/${id}/dismiss`).then((r) => r.data)
  },
}
