import http from './index'
import type { Liability, LiabilityRequestPayload, LiabilitySimResult, PaymentRecord } from '@/types'

export function getLiabilities(params?: { is_active?: boolean }) {
  return http.get<Liability[]>('/liabilities', { params })
}

export function getLiability(id: string) {
  return http.get<Liability>(`/liabilities/${id}`)
}

export function createLiability(data: LiabilityRequestPayload) {
  return http.post<Liability>('/liabilities', data)
}

export function updateLiability(id: string, data: LiabilityRequestPayload) {
  return http.put<Liability>(`/liabilities/${id}`, data)
}

export function deleteLiability(id: string) {
  return http.delete(`/liabilities/${id}`)
}

export function recordPayment(id: string, amount: number, paid_at?: string) {
  return http.put<Liability>(`/liabilities/${id}/payment`, { amount, paid_at })
}

export function getPayments(id: string) {
  return http.get<PaymentRecord[]>(`/liabilities/${id}/payments`)
}

// L2 (Plan B T9 frontend): amortization simulate. T4 added POST /liabilities/simulate.
// U2: extended with repayment_method + total_periods for multi-method support.
export function simulateLiability(req: {
  remaining: string
  annual_rate: string
  monthly_payment?: string
  extra_monthly?: string
  repayment_method?: string
  total_periods?: number | null
}) {
  return http.post<LiabilitySimResult>('/liabilities/simulate', req)
}
