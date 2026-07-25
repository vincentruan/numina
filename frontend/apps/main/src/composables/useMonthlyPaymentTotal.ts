import { computed } from 'vue'
import type { Liability } from '@/types'

/**
 * 计算活跃负债的月度还款总额
 * - 如果负债有 monthly_payment，直接使用
 * - 否则根据 remaining_amount 和 interest_rate 估算（年利率 / 12 / 100 * 剩余金额）
 */
export function useMonthlyPaymentTotal(liabilities: () => Liability[] | undefined) {
  const activeLiabilities = computed(() =>
    (liabilities() || []).filter((l) => l.is_active)
  )

  const monthlyPaymentTotal = computed(() =>
    activeLiabilities.value.reduce((sum, l) => {
      const mp = Number(l.monthly_payment ?? 0)
      if (mp > 0) return sum + mp
      const rate = (l.interest_rate ?? 0) / 100 / 12
      return sum + Number(l.remaining_amount ?? 0) * rate
    }, 0)
  )

  const monthlyPaymentIsEstimate = computed(() =>
    activeLiabilities.value.some((l) => !l.monthly_payment || Number(l.monthly_payment) === 0)
  )

  return {
    activeLiabilities,
    monthlyPaymentTotal,
    monthlyPaymentIsEstimate,
  }
}
