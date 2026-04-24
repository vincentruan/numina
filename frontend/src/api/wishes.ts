import http from './index'
import type { Wish, WishRealizeRequest } from '@/types'

export function getWishes(status?: string) {
  return http.get<Wish[]>('/wishes/', { params: status ? { status } : undefined })
}

export function getWish(id: string) {
  return http.get<Wish>(`/wishes/${id}`)
}

export function createWish(data: Partial<Wish>) {
  return http.post<Wish>('/wishes/', data)
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