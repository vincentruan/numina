import http from './index'
import type { Wish } from '@/types'

export function getWishes() {
  return http.get<Wish[]>('/wishes')
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

export function fulfillWish(id: string, assetId: string) {
  return http.post<Wish>(`/wishes/${id}/fulfill`, { asset_id: assetId })
}
