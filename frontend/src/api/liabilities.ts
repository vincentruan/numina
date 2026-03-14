import http from './index'
import type { Liability } from '@/types'

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
