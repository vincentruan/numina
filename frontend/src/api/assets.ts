import http from './index'
import type { Asset, AssetFilter, AssetSellRequest, AssetSellResponse, AssetValuation } from '@/types'

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
