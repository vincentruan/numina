import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Wish, WishRequestPayload } from '@/types'
import * as wishApi from '@/api/wishes'

export const useWishStore = defineStore('wish', () => {
  const wishes = ref<Wish[]>([])
  const currentWish = ref<Wish | null>(null)
  const loading = ref(false)

  // Dedup: module-level promise so concurrent callers share one in-flight request
  let _fetchPromise: Promise<void> | null = null

  async function fetchWishes(status?: string) {
    if (_fetchPromise !== null) {
      return _fetchPromise
    }
    loading.value = true
    _fetchPromise = (async () => {
      try {
        const res = await wishApi.getWishes(status)
        wishes.value = res.data
      } finally {
        loading.value = false
        _fetchPromise = null
      }
    })()
    return _fetchPromise
  }

  async function fetchWish(id: string) {
    loading.value = true
    try {
      const res = await wishApi.getWish(id)
      currentWish.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createWish(data: WishRequestPayload) {
    const res = await wishApi.createWish(data)
    wishes.value.unshift(res.data)
    return res.data
  }

  async function updateWish(id: string, data: WishRequestPayload) {
    const res = await wishApi.updateWish(id, data)
    const idx = wishes.value.findIndex(w => w.id === id)
    if (idx !== -1) wishes.value[idx] = res.data
    if (currentWish.value?.id === id) currentWish.value = res.data
    return res.data
  }

  async function deleteWish(id: string) {
    await wishApi.deleteWish(id)
    wishes.value = wishes.value.filter(w => w.id !== id)
    if (currentWish.value?.id === id) currentWish.value = null
  }

  return {
    wishes, currentWish, loading,
    fetchWishes, fetchWish, createWish, updateWish, deleteWish,
  }
})