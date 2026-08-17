import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { RentalContract, RentalRequestPayload, RentalSummary } from '@/types'
import * as rentalApi from '@/api/rentalContracts'

export const useRentalContractStore = defineStore('rentalContract', () => {
  const contracts = ref<RentalContract[]>([])
  const summary = ref<RentalSummary | null>(null)
  const loading = ref(false)

  async function fetchContracts(params?: { role?: 'landlord' | 'tenant'; active_only?: boolean }) {
    loading.value = true
    try {
      const res = await rentalApi.getRentalContracts(params)
      contracts.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchSummary() {
    const res = await rentalApi.getRentalSummary()
    summary.value = res.data
  }

  async function createContract(data: RentalRequestPayload) {
    const res = await rentalApi.createRentalContract(data)
    contracts.value.unshift(res.data)
    return res.data
  }

  async function updateContract(id: string, data: RentalRequestPayload) {
    const res = await rentalApi.updateRentalContract(id, data)
    const idx = contracts.value.findIndex(c => c.id === id)
    if (idx !== -1) contracts.value[idx] = res.data
    return res.data
  }

  async function deactivateContract(id: string) {
    await rentalApi.deleteRentalContract(id)
    contracts.value = contracts.value.filter(c => c.id !== id)
  }

  return {
    contracts, summary, loading,
    fetchContracts, fetchSummary, createContract, updateContract, deactivateContract,
  }
})
