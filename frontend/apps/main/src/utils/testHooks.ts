/**
 * Dev-only test hooks for automated UI testing.
 *
 * Exposes internal store methods and API helpers on `window.__numina_test__`
 * so automated tests can bypass DOM event dispatch (which is unreliable with
 * synthetic CDP events on Vue/Vant components).
 *
 * Gated behind `import.meta.env.DEV` — stripped from production builds.
 *
 * Usage in tests (browser-use / Chrome DevTools MCP):
 *   const result = js(`__numina_test__.createItineraryItem('TRIP_ID', { date: '2026-10-01', type: 'dining', cost_amount: '100' })`)
 */

import type { ExpenseEntryCreate, ItineraryItemCreate } from '@/types/travel'

export interface NuminaTestAPI {
  // Travel / itinerary
  createItineraryItem(tripId: string, data: ItineraryItemCreate): Promise<unknown>
  updateItineraryItem(tripId: string, itemId: string, data: ItineraryItemCreate): Promise<unknown>

  // Travel / expense
  createExpense(tripId: string, data: ExpenseEntryCreate): Promise<unknown>

  // API helpers — raw fetch wrappers that reuse the app's auth session
  apiGet(path: string): Promise<unknown>
  apiPost(path: string, body?: unknown): Promise<unknown>
  apiPatch(path: string, body?: unknown): Promise<unknown>
  apiDelete(path: string): Promise<unknown>

  // Utility
  ping(): string
}

/**
 * Register test hooks on window when in dev mode.
 * No-op in production (the entire module is tree-shaken).
 */
export function registerTestHooks(): void {
  if (import.meta.env.PROD) return

  // Lazily import stores/API to avoid circular deps at module init time
  const hooks: NuminaTestAPI = {
    ping() {
      return 'numina-test-hooks-ready'
    },

    async createItineraryItem(tripId: string, data: ItineraryItemCreate) {
      const { useTravelStore } = await import('@/stores/travel')
      return useTravelStore().createItineraryItem(tripId, data)
    },

    async updateItineraryItem(tripId: string, itemId: string, data: ItineraryItemCreate) {
      const { useTravelStore } = await import('@/stores/travel')
      return useTravelStore().updateItineraryItem(tripId, itemId, data)
    },

    async createExpense(tripId: string, data: ExpenseEntryCreate) {
      const { useTravelStore } = await import('@/stores/travel')
      return useTravelStore().createExpense(tripId, data)
    },

    async apiGet(path: string) {
      const http = (await import('@/api')).default
      return (await http.get(path)).data
    },

    async apiPost(path: string, body?: unknown) {
      const http = (await import('@/api')).default
      return (await http.post(path, body)).data
    },

    async apiPatch(path: string, body?: unknown) {
      const http = (await import('@/api')).default
      return (await http.patch(path, body)).data
    },

    async apiDelete(path: string) {
      const http = (await import('@/api')).default
      return (await http.delete(path)).data
    },
  }

  ;(window as Window & { __numina_test__?: NuminaTestAPI }).__numina_test__ = hooks
}

// TypeScript declaration for window.__numina_test__
declare global {
  interface Window {
    __numina_test__?: NuminaTestAPI
  }
}
