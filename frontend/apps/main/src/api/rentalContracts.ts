import http from './index'
import type { RentalContract, RentalRequestPayload, RentalSummary } from '@/types'

export function getRentalContracts(params?: { role?: 'landlord' | 'tenant'; active_only?: boolean }) {
  return http.get<RentalContract[]>('/rental-contracts', { params })
}

export function getRentalContract(id: string) {
  return http.get<RentalContract>(`/rental-contracts/${id}`)
}

export function createRentalContract(data: RentalRequestPayload) {
  return http.post<RentalContract>('/rental-contracts', data)
}

export function updateRentalContract(id: string, data: RentalRequestPayload) {
  return http.patch<RentalContract>(`/rental-contracts/${id}`, data)
}

export function deleteRentalContract(id: string) {
  return http.delete(`/rental-contracts/${id}`)
}

export function getRentalSummary() {
  return http.get<RentalSummary>('/rental-contracts/summary')
}
