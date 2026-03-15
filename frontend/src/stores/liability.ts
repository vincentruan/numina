import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Liability } from '@/types'
import * as liabilityApi from '@/api/liabilities'

export const useLiabilityStore = defineStore('liability', () => {
  const liabilities = ref<Liability[]>([])
  const currentLiability = ref<Liability | null>(null)
  const loading = ref(false)

  async function fetchLiabilities(params?: { is_active?: boolean }) {
    loading.value = true
    try {
      const res = await liabilityApi.getLiabilities(params)
      liabilities.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchLiability(id: string) {
    loading.value = true
    try {
      const res = await liabilityApi.getLiability(id)
      currentLiability.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createLiability(data: Partial<Liability>) {
    const res = await liabilityApi.createLiability(data)
    liabilities.value.unshift(res.data)
    return res.data
  }

  async function updateLiability(id: string, data: Partial<Liability>) {
    const res = await liabilityApi.updateLiability(id, data)
    const idx = liabilities.value.findIndex(l => l.id === id)
    if (idx !== -1) liabilities.value[idx] = res.data
    if (currentLiability.value?.id === id) currentLiability.value = res.data
    return res.data
  }

  async function deleteLiability(id: string) {
    await liabilityApi.deleteLiability(id)
    liabilities.value = liabilities.value.filter(l => l.id !== id)
    if (currentLiability.value?.id === id) currentLiability.value = null
  }

  async function recordPayment(id: string, amount: number) {
    const res = await liabilityApi.recordPayment(id, amount)
    const idx = liabilities.value.findIndex(l => l.id === id)
    if (idx !== -1) liabilities.value[idx] = res.data
    if (currentLiability.value?.id === id) currentLiability.value = res.data
    return res.data
  }

  return { liabilities, currentLiability, loading, fetchLiabilities, fetchLiability, createLiability, updateLiability, deleteLiability, recordPayment }
})
