import http from './index'
import type {
  Trip,
  TripCreate,
  TripUpdate,
  ExpenseEntry,
  ExpenseEntryCreate,
  ExpenseCategory,
  SplitGroup,
  SplitSettlement,
  SharedExpense,
} from '@/types/travel'

// Trip API
export function getTrips(params?: { status?: string; active_only?: boolean }) {
  return http.get<Trip[]>('/trips', { params })
}

export function createTrip(data: TripCreate) {
  return http.post<Trip>('/trips', data)
}

export function getTrip(id: string) {
  return http.get<Trip>(`/trips/${id}`)
}

export function updateTrip(id: string, data: TripUpdate) {
  return http.patch<Trip>(`/trips/${id}`, data)
}

export function deleteTrip(id: string) {
  return http.delete(`/trips/${id}`)
}

export function cancelTrip(id: string) {
  return http.post(`/trips/${id}/cancel`)
}

export function graduateWish(wishId: string) {
  return http.post<Trip>('/trips/graduate', { wish_id: wishId })
}

// Expense API
export function getExpenses(tripId: string) {
  return http.get<ExpenseEntry[]>(`/trips/${tripId}/expenses`)
}

export function createExpense(tripId: string, data: ExpenseEntryCreate) {
  return http.post<ExpenseEntry>(`/trips/${tripId}/expenses`, data)
}

export function deleteExpense(tripId: string, entryId: string) {
  return http.delete(`/trips/${tripId}/expenses/${entryId}`)
}

// Expense Category API
export function getExpenseCategories() {
  return http.get<ExpenseCategory[]>('/expense-categories')
}

export function createExpenseCategory(data: { name: string; icon?: string }) {
  return http.post<ExpenseCategory>('/expense-categories', data)
}

// Split Group API
export function getSplitGroup(tripId: string) {
  return http.get<SplitGroup>(`/trips/${tripId}/split`)
}

export function createSplitGroup(tripId: string) {
  return http.post<SplitGroup>(`/trips/${tripId}/split`)
}

export function joinSplitGroup(inviteCode: string, name: string) {
  return http.post(`/travel/shared/${inviteCode}/join`, { name })
}

export function getSharedExpenses(inviteCode: string) {
  return http.get<SharedExpense>(`/travel/shared/${inviteCode}`)
}

export function simplifyDebts(tripId: string) {
  return http.post<SplitSettlement[]>(`/trips/${tripId}/split/settle`)
}

export function getSettlements(tripId: string) {
  return http.get<SplitSettlement[]>(`/trips/${tripId}/split/settlements`)
}

export function markSettlementComplete(tripId: string, settlementId: string) {
  return http.patch(`/trips/${tripId}/split/settlements/${settlementId}/complete`)
}

export function reverseSettlement(tripId: string, settlementId: string) {
  return http.delete(`/trips/${tripId}/split/settlements/${settlementId}/complete`)
}

// Participant management
export function removeParticipant(tripId: string, participantId: string) {
  return http.delete(`/trips/${tripId}/split/participants/${participantId}`)
}

export function regenerateInviteCode(tripId: string) {
  return http.post<SplitGroup>(`/trips/${tripId}/split/regenerate-code`)
}

// Co-organizer management
export function addCoOrganizer(tripId: string, targetUserId: string) {
  return http.post(`/trips/${tripId}/split/co-organizers`, { target_user_id: targetUserId })
}

export function removeCoOrganizer(tripId: string, targetUserId: string) {
  return http.delete(`/trips/${tripId}/split/co-organizers/${targetUserId}`)
}

// Receipt API
export interface ReceiptExtractionResult {
  vendor: string
  amount: number | null
  currency: string
  date: string | null
  expense_category: string | null
}

export interface ReceiptUploadResponse {
  receipt_image_url: string
  trip_id: string
  extracted_data: ReceiptExtractionResult | null
  confidence: string
}

export function uploadReceipt(tripId: string, file: File) {
  const formData = new FormData()
  formData.append('trip_id', tripId)
  formData.append('file', file)
  return http.post<ReceiptUploadResponse>('/import/parse-travel-receipt', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
