import { computed } from 'vue'
import { formatCurrency, formatPercent } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'
import { useExchangeRate } from './useExchangeRate'

export function useCurrency() {
  const authStore = useAuthStore()
  const { getCachedRate, ensureRate } = useExchangeRate()

  const currency = computed(() => authStore.user?.default_currency || 'CNY')

  // Money is str on the wire (money-as-str); formatCurrency coerces. Accept both.
  const format = (amount: number | string) => formatCurrency(amount, currency.value)

  // Format an amount in a specific currency (e.g. an asset's own currency),
  // independent of the user's default_currency.
  const formatIn = (amount: number | string, currencyCode: string) => formatCurrency(amount, currencyCode)

  /**
   * Convert an amount to the user's default_currency using cached exchange rates.
   *
   * Rates are stored as "1 CNY = rate target" (e.g. USD rate 0.148 means
   * 1 CNY = 0.148 USD). The conversion matrix:
   *   CNY → target: amount * targetRate
   *   X   → CNY:    amount / xRate
   *   X   → target: amount / xRate * targetRate
   *
   * If either rate is not yet cached, falls back to showing the amount in its
   * native currency. Components should call `ensureRate(code)` to warm the cache.
   */
  function convertAmount(amount: number | string, fromCurrency: string): number {
    const targetCurrency = currency.value
    if (fromCurrency === targetCurrency) {
      return Number(amount) || 0
    }

    const targetRate = getCachedRate(targetCurrency)
    if (!targetRate) {
      return Number(amount) || 0
    }

    const numAmount = Number(amount) || 0
    if (fromCurrency === 'CNY') {
      return numAmount * targetRate.rate
    }

    const fromRate = getCachedRate(fromCurrency)
    if (!fromRate) {
      return numAmount
    }
    // fromRate: 1 CNY = fromRate fromCurrency  =>  1 fromCurrency = 1/fromRate CNY
    return (numAmount / fromRate.rate) * targetRate.rate
  }

  /**
   * Synchronous convert+format. Falls back to native currency display if rates
   * are not yet available.
   */
  const formatConverted = (amount: number | string, fromCurrency: string): string => {
    const targetCurrency = currency.value
    if (fromCurrency === targetCurrency) {
      return formatCurrency(amount, targetCurrency)
    }

    const targetRate = getCachedRate(targetCurrency)
    if (!targetRate) {
      // Target rate not yet cached — show in native currency as fallback
      return formatCurrency(amount, fromCurrency)
    }

    // Also verify source rate is available; convertAmount silently returns raw if not
    if (fromCurrency !== 'CNY' && !getCachedRate(fromCurrency)) {
      return formatCurrency(amount, fromCurrency)
    }

    const converted = convertAmount(amount, fromCurrency)
    return formatCurrency(converted, targetCurrency)
  }

  return {
    format,
    formatIn,
    formatConverted,
    convertAmount,
    convertAndFormat: async (amount: number | string, fromCurrency: string) => {
      await ensureRate(currency.value)
      if (fromCurrency !== 'CNY' && fromCurrency !== currency.value) {
        await ensureRate(fromCurrency)
      }
      return formatConverted(amount, fromCurrency)
    },
    formatPercent,
    currency,
  }
}
