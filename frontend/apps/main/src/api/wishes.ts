import http from './index'
import type { Wish, WishAdvice, WishRealizeRequest, WishRedistribution } from '@/types'

export function getWishes(status?: string) {
  return http.get<Wish[]>('/wishes', { params: status ? { status } : undefined })
}

export function getWish(id: string) {
  return http.get<Wish>(`/wishes/${id}`)
}

export function createWish(data: Partial<Wish>) {
  return http.post<Wish>('/wishes', data)
}

export function updateWish(id: string, data: Partial<Wish>) {
  return http.put<Wish>(`/wishes/${id}`, data)
}

export function deleteWish(id: string) {
  return http.delete(`/wishes/${id}`)
}

export function realizeWish(id: string, data: WishRealizeRequest) {
  return http.post(`/wishes/${id}/realize`, data)
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