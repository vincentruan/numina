import { computed } from 'vue'
import type { Wish } from '@/types'

export type AffordState =
  | { kind: 'unset_monthly' }                                      // 未设定月存
  | { kind: 'progress'; months: number; etaDate: string | null }  // 预计 N 月达成
  | { kind: 'reached' }                                            // 已达成 ✓
  | { kind: 'need_accelerate'; requiredMonthly: number; daysLeft: number } // 需加速

/**
 * W2 afford-bar logic (spec §3.1). listMode: single-line compact; detail: full.
 *
 * `wish` is a getter so the computed values stay reactive to the parent's
 * current wish (list passes a per-wish getter; detail passes the live wish).
 * `netWorth` is a getter for the secondary purchasing-power line (detail only).
 */
export function useAffordBar(wish: () => Wish | undefined, netWorth: () => number) {
  const price = computed(() => Number(wish()?.expected_price ?? 0))
  const saved = computed(() => Number(wish()?.saved_amount ?? 0))
  const monthly = computed(() => Number(wish()?.monthly_saving ?? 0))
  const targetDate = computed(() => wish()?.target_date ?? null)

  const state = computed<AffordState>(() => {
    if (price.value > 0 && saved.value >= price.value) return { kind: 'reached' }
    if (monthly.value <= 0) return { kind: 'unset_monthly' }
    const remaining = price.value - saved.value
    const months = Math.ceil(remaining / monthly.value)
    const eta = new Date()
    eta.setMonth(eta.getMonth() + months)
    return { kind: 'progress', months, etaDate: eta.toISOString().slice(0, 10) }
  })

  // target_date 加速对照 (spec §3.1 row 4): 距目标 D 天，需月存 ¥X
  const accelerate = computed(() => {
    if (!targetDate.value || monthly.value <= 0 || state.value.kind === 'reached') return null
    const target = new Date(targetDate.value)
    const daysLeft = Math.ceil((target.getTime() - Date.now()) / 86400000)
    if (daysLeft <= 0) return null
    const remaining = price.value - saved.value
    const requiredMonthly = remaining / Math.max(1, Math.ceil(daysLeft / 30))
    if (requiredMonthly > monthly.value) return { requiredMonthly: Math.ceil(requiredMonthly), daysLeft }
    return null
  })

  // Net-worth purchasing-power secondary line (spec §3.1 secondary, detail only)
  const purchasingPower = computed(() => ({
    covered: price.value > 0 && netWorth() >= price.value,
    netWorth: netWorth(),
  }))

  const progressPercent = computed(() =>
    price.value > 0 ? Math.min(100, Math.round((saved.value / price.value) * 100)) : 0,
  )
  const progressColor = computed(() => {
    if (saved.value > price.value) return '#faad14' // 金 (超额)
    if (progressPercent.value >= 80) return '#07c160' // 绿
    if (progressPercent.value >= 50) return '#1989fa' // 蓝
    return '#ff976a' // 橙
  })

  return { state, accelerate, purchasingPower, progressPercent, progressColor, price, saved, monthly }
}
