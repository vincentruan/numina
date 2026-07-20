import { computed, ref } from 'vue'
import type { Ref } from 'vue'
import http from '@/api/index'
import type { Liability, Wish } from '@/types'

type Category = 'mortgage' | 'car_loan' | 'credit_card' | 'personal_loan' | 'other'

const DEFAULT_THRESHOLDS: Record<Category, number> = {
  credit_card: 12,
  personal_loan: 10,
  mortgage: 6,
  car_loan: 10,
  other: 10,
}

export interface HighInterestLiability extends Liability {
  monthly_interest: number
}

/**
 * W5 (Plan B T8): high-interest-debt ↔ wish linkage (pure computation, spec §5).
 *
 * A liability is "high-interest" when its annual interest_rate >= its category's
 * threshold. The monthly_interest formula matches L1 (T4: remaining × monthly_rate).
 * Per-wish trigger (spec §5.2): wish has monthly_saving>0 AND high-interest debt
 * exists AND NOT wish.ignore_debt_warning.
 */
export function useDebtWarning(liabilities: Ref<Liability[]>, _wishes: Ref<Wish[]>) {
  const thresholds = ref<Record<string, number>>({ ...DEFAULT_THRESHOLDS })

  async function loadThresholds(): Promise<void> {
    try {
      const resp = await http.get<{ thresholds: Record<string, number> }>('/family/debt-thresholds')
      thresholds.value = { ...DEFAULT_THRESHOLDS, ...resp.data.thresholds }
    } catch {
      /* keep defaults */
    }
  }

  // Map liability.category → threshold key. car_loan falls under 'other'
  // (spec lists 信用卡/消费贷/房贷/其他; car_loan ≈ 消费贷 → personal_loan threshold).
  function thresholdFor(cat: string): number {
    if (cat === 'credit_card') return thresholds.value.credit_card
    if (cat === 'mortgage') return thresholds.value.mortgage
    if (cat === 'personal_loan') return thresholds.value.personal_loan
    if (cat === 'car_loan') return thresholds.value.car_loan
    return thresholds.value.other
  }

  // High-interest active liabilities: rate >= their category threshold.
  const highInterestLiabilities = computed<HighInterestLiability[]>(() =>
    (liabilities.value || [])
      .filter((l) => l.is_active && (l.interest_rate ?? 0) >= thresholdFor(l.category))
      .map((l) => ({
        ...l,
        monthly_interest:
          Math.round((l.remaining_amount * (l.interest_rate / 100 / 12) * 100) / 100),
      })),
  )

  const hasHighInterestDebt = computed(() => highInterestLiabilities.value.length > 0)

  // Per-wish trigger (spec §5.2): wish has monthly_saving>0 AND high-interest debt
  // exists AND NOT wish.ignore_debt_warning.
  function shouldWarnForWish(w: Wish): boolean {
    return (
      Number(w.monthly_saving) > 0 &&
      hasHighInterestDebt.value &&
      !w.ignore_debt_warning
    )
  }

  return {
    thresholds,
    loadThresholds,
    highInterestLiabilities,
    hasHighInterestDebt,
    shouldWarnForWish,
  }
}
