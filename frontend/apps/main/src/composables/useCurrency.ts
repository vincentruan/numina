import { computed } from 'vue'
import { formatCurrency, formatPercent } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'

export function useCurrency() {
  const authStore = useAuthStore()

  const currency = computed(() => authStore.user?.default_currency || 'CNY')

  // Money is str on the wire (money-as-str); formatCurrency coerces. Accept both.
  const format = (amount: number | string) => formatCurrency(amount, currency.value)

  // Format an amount in a specific currency (e.g. an asset's own currency),
  // independent of the user's default_currency.
  const formatIn = (amount: number | string, currencyCode: string) => formatCurrency(amount, currencyCode)

  return {
    format,
    formatIn,
    formatPercent,
    currency
  }
}
