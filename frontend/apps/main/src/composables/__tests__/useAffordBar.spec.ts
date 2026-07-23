import { describe, it, expect } from 'vitest'
import { useAffordBar } from '../useAffordBar'
import type { Wish } from '@/types'

function wish(partial: Partial<Wish>): Wish {
  return {
    id: '1',
    family_id: '1',
    user_id: '1',
    name: 'x',
    currency: 'CNY',
    priority: 'medium',
    status: 'pending',
    converts_to_asset: true,
    saved_amount: '0',
    monthly_saving: '0',
    target_date: null,
    savings_count: 0,
    ignore_debt_warning: false,
    created_at: '',
    updated_at: '',
    ...partial,
  } as Wish
}

describe('useAffordBar', () => {
  it('unset_monthly when monthly_saving=0', () => {
    const { state } = useAffordBar(
      () => wish({ expected_price: '1000', saved_amount: '0', monthly_saving: '0' }),
      () => 0,
    )
    expect(state.value.kind).toBe('unset_monthly')
  })

  it('reached when saved >= price', () => {
    const { state } = useAffordBar(
      () => wish({ expected_price: '1000', saved_amount: '1000', monthly_saving: '100' }),
      () => 0,
    )
    expect(state.value.kind).toBe('reached')
  })

  it('progress computes months', () => {
    const { state } = useAffordBar(
      () => wish({ expected_price: '1000', saved_amount: '200', monthly_saving: '200' }),
      () => 0,
    )
    expect(state.value.kind).toBe('progress')
    if (state.value.kind === 'progress') expect(state.value.months).toBe(4)
  })

  it('accelerate flags when target_date needs higher monthly', () => {
    const soon = new Date()
    soon.setDate(soon.getDate() + 30)
    const { accelerate } = useAffordBar(
      () =>
        wish({
          expected_price: '10000',
          saved_amount: '0',
          monthly_saving: '100',
          target_date: soon.toISOString().slice(0, 10),
        }),
      () => 0,
    )
    expect(accelerate.value).not.toBeNull()
    expect(accelerate.value!.requiredMonthly).toBeGreaterThan(100)
  })

  it('purchasingPower reflects net worth coverage', () => {
    const { purchasingPower } = useAffordBar(
      () => wish({ expected_price: '1000', saved_amount: '0', monthly_saving: '0' }),
      () => 1500,
    )
    expect(purchasingPower.value.covered).toBe(true)
    expect(purchasingPower.value.netWorth).toBe(1500)
  })

  it('progressPercent + color tiers', () => {
    const low = useAffordBar(
      () => wish({ expected_price: '1000', saved_amount: '100', monthly_saving: '100' }),
      () => 0,
    )
    expect(low.progressPercent.value).toBe(10)
    expect(low.progressColor.value).toBe('#ff976a') // <50% → 橙

    const high = useAffordBar(
      () => wish({ expected_price: '1000', saved_amount: '850', monthly_saving: '100' }),
      () => 0,
    )
    expect(high.progressPercent.value).toBe(85)
    expect(high.progressColor.value).toBe('#07c160') // >=80% → 绿
  })
})
