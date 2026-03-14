import http from './index'
import type { Category } from '@/types'

export function getCategories(params?: { asset_type?: string }) {
  return http.get<Category[]>('/categories', { params })
}

export function createCategory(data: Partial<Category>) {
  return http.post<Category>('/categories', data)
}

export function updateCategory(id: string, data: Partial<Category>) {
  return http.put<Category>(`/categories/${id}`, data)
}

export function deleteCategory(id: string) {
  return http.delete(`/categories/${id}`)
}
