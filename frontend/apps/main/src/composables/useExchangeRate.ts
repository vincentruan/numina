import { getRate } from '@/api/currencies'
import { reactive } from 'vue'
import type { RateResponse } from '@/types'

// Reactive cache — persists across component instances within a page session
// Using reactive() so components re-render when rates are fetched asynchronously
const rateCache = reactive(new Map<string, { rate: number; fetched_at: string }>())

// Pre-seed CNY rate (identity) so synchronous lookups never fail for CNY
rateCache.set('CNY', { rate: 1.0, fetched_at: new Date().toISOString() })

export function useExchangeRate() {
  /** Synchronous lookup from the in-memory cache. Returns null if not yet loaded. */
  function getCachedRate(currency: string): { rate: number; fetched_at: string } | null {
    return rateCache.get(currency) ?? null
  }

  async function getRateInfo(currency: string): Promise<{ rate: number; fetched_at: string } | null> {
    if (currency === 'CNY') {
      return { rate: 1.0, fetched_at: new Date().toISOString() }
    }

    // Check cache
    if (rateCache.has(currency)) {
      return rateCache.get(currency)!
    }

    // Fetch from API
    try {
      const res = await getRate(currency)
      const data: RateResponse = res.data
      const info = { rate: data.rate, fetched_at: data.fetched_at }
      rateCache.set(currency, info)
      return info
    } catch (e) {
      console.warn('Failed to fetch rate:', e)
      return null
    }
  }

  /** Ensure a specific currency rate is loaded (idempotent). Safe to call repeatedly. */
  async function ensureRate(currency: string): Promise<void> {
    if (currency === 'CNY' || rateCache.has(currency)) return
    await getRateInfo(currency)
  }

  return {
    getRateInfo,
    getCachedRate,
    ensureRate,
  }
}
