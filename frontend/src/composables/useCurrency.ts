import { computed } from 'vue'
import { formatCurrency, formatPercent } from '@/utils/format'
import { useAuthStore } from '@/stores/auth'

export function useCurrency() {
  const authStore = useAuthStore()

  const currency = computed(() => authStore.user?.default_currency || 'CNY')

  const format = (amount: number) => formatCurrency(amount, currency.value)

  return {
    format,
    formatPercent,
    currency
  }
}
