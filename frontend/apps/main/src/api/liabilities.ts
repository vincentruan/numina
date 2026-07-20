import http from './index'
import type { Liability, LiabilitySimResult, PaymentRecord } from '@/types'

export function getLiabilities(params?: { is_active?: boolean }) {
  return http.get<Liability[]>('/liabilities', { params })
}

export function getLiability(id: string) {
  return http.get<Liability>(`/liabilities/${id}`)
}

export function createLiability(data: Partial<Liability>) {
  return http.post<Liability>('/liabilities', data)
}

export function updateLiability(id: string, data: Partial<Liability>) {
  return http.put<Liability>(`/liabilities/${id}`, data)
}

export function deleteLiability(id: string) {
  return http.delete(`/liabilities/${id}`)
}

export function recordPayment(id: string, amount: number) {
  return http.put<Liability>(`/liabilities/${id}/payment`, { amount })
}

export function getPayments(id: string) {
  return http.get<PaymentRecord[]>(`/liabilities/${id}/payments`)
}

// L2 (Plan B T9 frontend): amortization simulate. T4 added POST /liabilities/simulate.
export function simulateLiability(req: {
  remaining: string
  annual_rate: string
  monthly_payment?: string
  extra_monthly?: string
}) {
  return http.post<LiabilitySimResult>('/liabilities/simulate', req)
}
