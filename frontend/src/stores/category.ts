import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Category } from '@/types'
import * as categoryApi from '@/api/categories'

export const useCategoryStore = defineStore('category', () => {
  const categories = ref<Category[]>([])
  const loading = ref(false)

  async function fetchCategories(assetType?: string) {
    loading.value = true
    try {
      const res = await categoryApi.getCategories(assetType ? { asset_type: assetType } : undefined)
      categories.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createCategory(data: Partial<Category>) {
    const res = await categoryApi.createCategory(data)
    categories.value.push(res.data)
    return res.data
  }

  async function updateCategory(id: string, data: Partial<Category>) {
    const res = await categoryApi.updateCategory(id, data)
    const idx = categories.value.findIndex(c => c.id === id)
    if (idx !== -1) categories.value[idx] = res.data
    return res.data
  }

  async function deleteCategory(id: string) {
    await categoryApi.deleteCategory(id)
    categories.value = categories.value.filter(c => c.id !== id)
  }

  return { categories, loading, fetchCategories, createCategory, updateCategory, deleteCategory }
})
