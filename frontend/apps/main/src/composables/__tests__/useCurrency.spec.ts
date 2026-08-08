import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// Mock dependencies BEFORE importing useCurrency
const getCachedRateMock = vi.fn()
const ensureRateMock = vi.fn()

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: ref({ default_currency: 'CNY' }),
  }),
}))

vi.mock('@/utils/format', () => ({
  formatCurrency: (amount: number | string, currency: string) => {
    const num = Number(amount) || 0
    const symbols: Record<string, string> = { CNY: '¥', USD: '$', EUR: '€', JPY: '¥' }
    return `${symbols[currency] || currency}${num.toFixed(2)}`
  },
  formatPercent: (n: number) => `${n.toFixed(2)}%`,
}))

vi.mock('../useExchangeRate', () => ({
  useExchangeRate: () => ({
    getRateInfo: vi.fn(),
    getCachedRate: getCachedRateMock,
    ensureRate: ensureRateMock,
  }),
}))

import { useCurrency } from '../useCurrency'

describe('useCurrency', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('format', () => {
    it('formats amount in user default currency', () => {
      const { format } = useCurrency()
      expect(format(1000)).toBe('¥1000.00')
    })
  })

  describe('formatIn', () => {
    it('formats amount in specified currency', () => {
      const { formatIn } = useCurrency()
      expect(formatIn(1000, 'USD')).toBe('$1000.00')
    })
  })

  describe('convertAmount', () => {
    it('returns raw amount when source equals target currency', () => {
      const { convertAmount } = useCurrency()
      expect(convertAmount(100, 'CNY')).toBe(100)
    })

    it('converts foreign currency to CNY (user default)', () => {
      // User default is CNY, source is USD
      // USD rate: 1 CNY = 0.14 USD => 1 USD = 1/0.14 CNY = 7.14 CNY
      getCachedRateMock.mockImplementation((currency: string) => {
        if (currency === 'CNY') return { rate: 1.0, fetched_at: '' }
        if (currency === 'USD') return { rate: 0.14, fetched_at: '' }
        return null
      })

      const { convertAmount } = useCurrency()
      // 100 USD / 0.14 * 1.0 = 714.29 CNY
      const result = convertAmount(100, 'USD')
      expect(result).toBeCloseTo(714.29, 1)
    })

    it('returns raw amount when target rate is not cached', () => {
      getCachedRateMock.mockReturnValue(null)

      const { convertAmount } = useCurrency()
      expect(convertAmount(100, 'USD')).toBe(100)
    })

    it('returns raw amount when source rate is not cached (non-CNY source)', () => {
      getCachedRateMock.mockImplementation((currency: string) => {
        if (currency === 'CNY') return { rate: 1.0, fetched_at: '' }
        return null // USD rate not cached
      })

      const { convertAmount } = useCurrency()
      expect(convertAmount(100, 'USD')).toBe(100)
    })
  })

  describe('formatConverted', () => {
    it('formats in target currency when same as source', () => {
      const { formatConverted } = useCurrency()
      expect(formatConverted(100, 'CNY')).toBe('¥100.00')
    })

    it('formats converted amount when rates are available', () => {
      getCachedRateMock.mockImplementation((currency: string) => {
        if (currency === 'CNY') return { rate: 1.0, fetched_at: '' }
        if (currency === 'USD') return { rate: 0.14, fetched_at: '' }
        return null
      })

      const { formatConverted } = useCurrency()
      // 100 USD -> ~714 CNY
      expect(formatConverted(100, 'USD')).toBe('¥714.29')
    })

    it('falls back to native currency when target rate missing', () => {
      getCachedRateMock.mockReturnValue(null)

      const { formatConverted } = useCurrency()
      expect(formatConverted(100, 'USD')).toBe('$100.00')
    })

    it('falls back to native currency when source rate missing (non-CNY)', () => {
      getCachedRateMock.mockImplementation((currency: string) => {
        if (currency === 'CNY') return { rate: 1.0, fetched_at: '' }
        return null
      })

      const { formatConverted } = useCurrency()
      expect(formatConverted(100, 'USD')).toBe('$100.00')
    })
  })

  describe('convertAndFormat', () => {
    it('ensures rates are loaded before formatting', async () => {
      getCachedRateMock.mockImplementation((currency: string) => {
        if (currency === 'CNY') return { rate: 1.0, fetched_at: '' }
        if (currency === 'USD') return { rate: 0.14, fetched_at: '' }
        return null
      })

      const { convertAndFormat } = useCurrency()
      const result = await convertAndFormat(100, 'USD')

      expect(ensureRateMock).toHaveBeenCalledWith('CNY')
      expect(ensureRateMock).toHaveBeenCalledWith('USD')
      expect(result).toBe('¥714.29')
    })

    it('skips ensureRate for CNY source', async () => {
      getCachedRateMock.mockImplementation((currency: string) => {
        if (currency === 'CNY') return { rate: 1.0, fetched_at: '' }
        return null
      })

      const { convertAndFormat } = useCurrency()
      await convertAndFormat(100, 'CNY')

      expect(ensureRateMock).toHaveBeenCalledWith('CNY')
      expect(ensureRateMock).not.toHaveBeenCalledWith('CNY', 'CNY')
    })
  })
})
