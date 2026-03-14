import { formatCurrency, formatPercent } from '@/utils/format'

export function useCurrency() {
  return {
    format: formatCurrency,
    formatPercent
  }
}
