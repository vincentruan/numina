import { getRate } from '@/api/currencies'
import type { RateResponse } from '@/types'

// Module-level cache — persists across component instances within a page session
const rateCache = new Map<string, { rate: number; fetched_at: string }>()

export function useExchangeRate() {
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

  return {
    getRateInfo,
  }
}