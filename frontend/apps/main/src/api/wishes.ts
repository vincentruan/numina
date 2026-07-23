import http from './index'
import type { SavingsLog, Wish, WishAdvice, WishRealizeRequest, WishRedistribution, WishRequestPayload } from '@/types'

export function getWishes(status?: string) {
  return http.get<Wish[]>('/wishes', { params: status ? { status } : undefined })
}

export function getWish(id: string) {
  return http.get<Wish>(`/wishes/${id}`)
}

export function createWish(data: WishRequestPayload) {
  return http.post<Wish>('/wishes', data)
}

export function updateWish(id: string, data: WishRequestPayload) {
  return http.put<Wish>(`/wishes/${id}`, data)
}

export function deleteWish(id: string) {
  return http.delete(`/wishes/${id}`)
}

export function realizeWish(id: string, data: WishRealizeRequest) {
  return http.post(`/wishes/${id}/realize`, data)
}

// W5 (Plan B T8): per-wish opt-out of the high-interest-debt linkage hint.
// T3 added the backend route (PATCH /wishes/{id}/ignore-debt-warning, body {ignore}).
export function setIgnoreDebtWarning(id: string, ignore: boolean) {
  return http.patch<Wish>(`/wishes/${id}/ignore-debt-warning`, { ignore })
}

// W1 savings CRUD (Plan B T9 frontend). T3 added the backend routes.
export function recordSaving(wishId: string, amount: string, logDate?: string, note?: string) {
  return http.post<SavingsLog>(`/wishes/${wishId}/savings`, { amount, log_date: logDate, note })
}

export function getSavingsLog(wishId: string, page = 1) {
  return http.get<SavingsLog[]>(`/wishes/${wishId}/savings`, { params: { page } })
}

export function deleteSavingsLog(wishId: string, logId: string) {
  return http.delete(`/wishes/${wishId}/savings/${logId}`)
}

// W4 wish-priority advice (Plan B T7). The endpoint returns a bare
// JSONResponse {status, generated_at?, report} (NOT EnvelopeResponse-wrapped),
// so the http interceptor passes it through unchanged.
export function getWishAdvice(force = false) {
  return http.post<{ status: string; generated_at?: string; report: WishAdvice | null }>(
    '/ai/wish-advice/generate',
    null,
    { params: { force } },
  )
}

// Batch PATCH each wish's monthly_saving per the redistribution. Returns
// per-item success/failure (Promise.allSettled) so the card can show partial.
export function adoptWishAdvice(redistribution: WishRedistribution[]) {
  return Promise.allSettled(
    redistribution.map((r) => updateWish(r.wish_id, { monthly_saving: r.suggested_amount })),
  )
}