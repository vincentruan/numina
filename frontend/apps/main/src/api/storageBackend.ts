import http from './index'

export interface GitHubStorageConfig {
  repo_owner: string
  repo_name: string
  branch: string
  token: string
}

export interface WebDAVStorageConfig {
  base_url: string
  username: string
  password: string
}

export type StorageConfig = GitHubStorageConfig | WebDAVStorageConfig

export interface StorageBackendResponse {
  id: string
  backend_type: 'github' | 'webdav'
  display_name: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface StorageBackendStatusResponse {
  configured: boolean
  backend_type: 'github' | 'webdav' | null
  display_name: string | null
  is_active: boolean
}

export interface StorageBackendCreateRequest {
  backend_type: 'github' | 'webdav'
  config: StorageConfig
  display_name?: string | null
  is_active?: boolean
}

export interface StorageBackendUpdateRequest {
  config?: StorageConfig
  display_name?: string | null
  is_active?: boolean
}

export function getStorageBackendStatus() {
  return http.get<StorageBackendStatusResponse>('/family/storage/status')
}

export function getStorageBackend() {
  return http.get<StorageBackendResponse | null>('/family/storage')
}

export function createStorageBackend(data: StorageBackendCreateRequest) {
  return http.post<StorageBackendResponse>('/family/storage', data)
}

export function updateStorageBackend(id: string, data: StorageBackendUpdateRequest) {
  return http.patch<StorageBackendResponse>(`/family/storage/${id}`, data)
}

export function deleteStorageBackend(id: string) {
  return http.delete(`/family/storage/${id}`)
}
