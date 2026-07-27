import api from '@/api'
import type {
  WebSearchProvider,
  WebSearchProviderCreate,
  WebSearchProviderTemplate,
  WebSearchProviderUpdate,
  WebSearchStatus,
} from '@/types/webSearch'

export function getWebSearchTemplates(): Promise<WebSearchProviderTemplate[]> {
  return api.get('/ai/web-search/templates').then((r) => r.data)
}

export function getWebSearchProviders(): Promise<WebSearchProvider[]> {
  return api.get('/ai/web-search').then((r) => r.data)
}

export function createWebSearchProvider(payload: WebSearchProviderCreate): Promise<WebSearchProvider> {
  return api.post('/ai/web-search', payload).then((r) => r.data)
}

export function updateWebSearchProvider(
  id: string,
  payload: WebSearchProviderUpdate,
): Promise<WebSearchProvider> {
  return api.put(`/ai/web-search/${id}`, payload).then((r) => r.data)
}

export function reorderWebSearchProviders(order: string[]): Promise<{ ok: boolean }> {
  return api.put('/ai/web-search/reorder', { order }).then((r) => r.data)
}

export function deleteWebSearchProvider(id: string): Promise<void> {
  return api.delete(`/ai/web-search/${id}`)
}

export function enableWebSearchProvider(id: string): Promise<WebSearchProvider> {
  return api.post(`/ai/web-search/${id}/enable`).then((r) => r.data)
}

export function disableWebSearchProvider(id: string): Promise<WebSearchProvider> {
  return api.post(`/ai/web-search/${id}/disable`).then((r) => r.data)
}

export function testWebSearchProvider(id: string): Promise<{ success: boolean; message: string }> {
  return api.post(`/ai/web-search/${id}/test`).then((r) => r.data)
}

export function revealWebSearchKey(id: string): Promise<{ api_key: string }> {
  return api.post(`/ai/web-search/${id}/reveal-key`).then((r) => r.data)
}

export function getWebSearchStatus(): Promise<WebSearchStatus> {
  return api.get('/ai/web-search/status').then((r) => r.data)
}
