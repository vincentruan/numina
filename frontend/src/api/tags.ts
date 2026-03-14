import http from './index'
import type { Tag } from '@/types'

export function getTags() {
  return http.get<Tag[]>('/tags')
}

export function createTag(data: Partial<Tag>) {
  return http.post<Tag>('/tags', data)
}

export function updateTag(id: string, data: Partial<Tag>) {
  return http.put<Tag>(`/tags/${id}`, data)
}

export function deleteTag(id: string) {
  return http.delete(`/tags/${id}`)
}
