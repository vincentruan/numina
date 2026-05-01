import http from './index'
import type { Asset, AssetFilter, AssetSellRequest, AssetSellResponse, AssetValuation } from '@/types'

// Batch operation types
interface BatchOperationResponse {
  success_count: number
  failed_count: number
  errors: string[]
}

interface BatchExportResponse {
  data: Asset[]
  count: number
}

export function getAssets(params?: AssetFilter) {
  return http.get<Asset[]>('/assets', { params })
}

export function getAsset(id: string) {
  return http.get<Asset>(`/assets/${id}`)
}

export function createAsset(data: Partial<Asset>) {
  return http.post<Asset>('/assets', data)
}

export function updateAsset(id: string, data: Partial<Asset>) {
  return http.put<Asset>(`/assets/${id}`, data)
}

export function deleteAsset(id: string) {
  return http.delete(`/assets/${id}`)
}

export function updateAssetValue(id: string, currentValue: number) {
  return http.put<Asset>(`/assets/${id}/value`, { current_value: currentValue })
}

export function sellAsset(id: string, data: AssetSellRequest) {
  return http.post<AssetSellResponse>(`/assets/${id}/sell`, data)
}

export function retireAsset(id: string) {
  return http.post<Asset>(`/assets/${id}/retire`)
}

export function reactivateAsset(id: string) {
  return http.post<Asset>(`/assets/${id}/reactivate`)
}

export function getValuations(id: string) {
  return http.get<AssetValuation[]>(`/assets/${id}/valuations`)
}

// Batch operations
export function batchArchiveAssets(assetIds: string[]) {
  return http.post<BatchOperationResponse>('/assets/batch/archive', { asset_ids: assetIds })
}

export function batchUpdateCategory(assetIds: string[], categoryId: string) {
  return http.put<BatchOperationResponse>('/assets/batch/category', { asset_ids: assetIds, category_id: categoryId })
}

export function batchUpdateTags(assetIds: string[], tagIds: string[]) {
  return http.put<BatchOperationResponse>('/assets/batch/tags', { asset_ids: assetIds, tag_ids: tagIds })
}

export function batchUpdateStatus(assetIds: string[], status: string) {
  return http.put<BatchOperationResponse>('/assets/batch/status', { asset_ids: assetIds, status })
}

export function batchExportAssets(assetIds: string[]) {
  return http.post<BatchExportResponse>('/assets/batch/export', { asset_ids: assetIds })
}
