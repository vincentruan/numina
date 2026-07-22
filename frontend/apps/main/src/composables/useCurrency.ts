import { computed } from 'vue'
import { formatCurrency, formatPercent } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'

export function useCurrency() {
  const authStore = useAuthStore()

  const currency = computed(() => authStore.user?.default_currency || 'CNY')

  // Money is str on the wire (money-as-str); formatCurrency coerces. Accept both.
  const format = (amount: number | string) => formatCurrency(amount, currency.value)

  return {
    format,
    formatPercent,
    currency
  }
}
