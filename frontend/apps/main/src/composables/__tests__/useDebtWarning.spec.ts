import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref, nextTick } from 'vue'
import { useDebtWarning } from '../useDebtWarning'
import type { Liability, Wish } from '@/types'

vi.mock('@/api/index', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { thresholds: {} } })),
  },
}))

function makeLiability(overrides: Partial<Liability> = {}): Liability {
  return {
    id: '1',
    user_id: 'u1',
    family_id: 'f1',
    category: 'credit_card',
    name: '信用卡',
    // Money fields are str on the wire (Liability type) — use strings so the
    // test exercises the Number() coercion path in useDebtWarning (regression
    // guard for the string-arithmetic NaN bug fixed in the review pass).
    original_amount: '10000',
    remaining_amount: '8000',
    currency: 'CNY',
    monthly_payment: '1000',
    interest_rate: 18,
    start_date: '2024-01-01',
    is_active: true,
    ...overrides,
  }
}

function makeWish(overrides: Partial<Wish> = {}): Wish {
  return {
    id: '1',
    family_id: 'f1',
    user_id: 'u1',
    name: '心愿A',
    currency: 'CNY',
    priority: 'high',
    status: 'pending',
    converts_to_asset: true,
    created_at: '',
    updated_at: '',
    monthly_saving: '500',
    ignore_debt_warning: false,
    ...overrides,
  }
}

describe('useDebtWarning', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('flags high-interest liabilities by their category threshold', async () => {
    // credit_card threshold default = 12; 18% is high, 8% is not.
    const liabilities = ref<Liability[]>([
      makeLiability({ id: '1', interest_rate: 18, remaining_amount: '12000' }),
      makeLiability({ id: '2', interest_rate: 8, remaining_amount: '5000' }),
    ])
    const wishes = ref<Wish[]>([])
    const { highInterestLiabilities } = useDebtWarning(liabilities, wishes)
    await nextTick()
    expect(highInterestLiabilities.value).toHaveLength(1)
    expect(highInterestLiabilities.value[0].id).toBe('1')
    // monthly_interest = 12000 * (18 / 100 / 12) = 12000 * 0.015 = 180
    expect(highInterestLiabilities.value[0].monthly_interest).toBe(180)
  })

  it('respects per-category thresholds (mortgage 6% default)', async () => {
    const liabilities = ref<Liability[]>([
      makeLiability({ id: '1', category: 'mortgage', interest_rate: 5, remaining_amount: '500000' }),
      makeLiability({ id: '2', category: 'mortgage', interest_rate: 7, remaining_amount: '500000' }),
    ])
    const wishes = ref<Wish[]>([])
    const { highInterestLiabilities } = useDebtWarning(liabilities, wishes)
    await nextTick()
    expect(highInterestLiabilities.value).toHaveLength(1)
    expect(highInterestLiabilities.value[0].id).toBe('2')
  })

  it('excludes inactive liabilities', async () => {
    const liabilities = ref<Liability[]>([
      makeLiability({ id: '1', interest_rate: 18, is_active: false }),
    ])
    const wishes = ref<Wish[]>([])
    const { highInterestLiabilities, hasHighInterestDebt } = useDebtWarning(liabilities, wishes)
    await nextTick()
    expect(highInterestLiabilities.value).toHaveLength(0)
    expect(hasHighInterestDebt.value).toBe(false)
  })

  it('shouldWarnForWish is true when monthly_saving>0 + high-interest debt + not ignored', async () => {
    const liabilities = ref<Liability[]>([makeLiability({ interest_rate: 18 })])
    const wishes = ref<Wish[]>([makeWish({ monthly_saving: '500', ignore_debt_warning: false })])
    const { shouldWarnForWish } = useDebtWarning(liabilities, wishes)
    await nextTick()
    expect(shouldWarnForWish(wishes.value[0])).toBe(true)
  })

  it('shouldWarnForWish is false when wish ignores the warning', async () => {
    const liabilities = ref<Liability[]>([makeLiability({ interest_rate: 18 })])
    const wishes = ref<Wish[]>([makeWish({ ignore_debt_warning: true })])
    const { shouldWarnForWish } = useDebtWarning(liabilities, wishes)
    await nextTick()
    expect(shouldWarnForWish(wishes.value[0])).toBe(false)
  })

  it('shouldWarnForWish is false when monthly_saving is 0', async () => {
    const liabilities = ref<Liability[]>([makeLiability({ interest_rate: 18 })])
    const wishes = ref<Wish[]>([makeWish({ monthly_saving: '0' })])
    const { shouldWarnForWish } = useDebtWarning(liabilities, wishes)
    await nextTick()
    expect(shouldWarnForWish(wishes.value[0])).toBe(false)
  })

  it('shouldWarnForWish is false when no high-interest debt exists', async () => {
    const liabilities = ref<Liability[]>([makeLiability({ interest_rate: 8 })])
    const wishes = ref<Wish[]>([makeWish({ monthly_saving: '500' })])
    const { shouldWarnForWish } = useDebtWarning(liabilities, wishes)
    await nextTick()
    expect(shouldWarnForWish(wishes.value[0])).toBe(false)
  })
})
