import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Asset, AssetFilter } from '@/types'
import * as assetApi from '@/api/assets'

export const useAssetStore = defineStore('asset', () => {
  const assets = ref<Asset[]>([])
  const currentAsset = ref<Asset | null>(null)
  const loading = ref(false)

  async function fetchAssets(filters?: AssetFilter) {
    loading.value = true
    try {
      const res = await assetApi.getAssets(filters)
      assets.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchAsset(id: string) {
    loading.value = true
    try {
      const res = await assetApi.getAsset(id)
      currentAsset.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createAsset(data: Partial<Asset>) {
    const res = await assetApi.createAsset(data)
    assets.value.unshift(res.data)
    return res.data
  }

  async function updateAsset(id: string, data: Partial<Asset>) {
    const res = await assetApi.updateAsset(id, data)
    const idx = assets.value.findIndex(a => a.id === id)
    if (idx !== -1) assets.value[idx] = res.data
    if (currentAsset.value?.id === id) currentAsset.value = res.data
    return res.data
  }

  async function deleteAsset(id: string) {
    await assetApi.deleteAsset(id)
    assets.value = assets.value.filter(a => a.id !== id)
    if (currentAsset.value?.id === id) currentAsset.value = null
  }

  async function updateValue(id: string, value: number) {
    const res = await assetApi.updateAssetValue(id, value)
    const idx = assets.value.findIndex(a => a.id === id)
    if (idx !== -1) assets.value[idx] = res.data
    if (currentAsset.value?.id === id) currentAsset.value = res.data
  }

  return { assets, currentAsset, loading, fetchAssets, fetchAsset, createAsset, updateAsset, deleteAsset, updateValue }
})
