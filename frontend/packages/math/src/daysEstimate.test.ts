import { describe, it, expect } from 'vitest'
import { daysEstimate } from './daysEstimate'
import type { PrioritySimulationEntry, LedgerEntry } from './types'

const NOW = new Date('2026-05-24T12:00:00Z').getTime()

const daysAgo = (n: number) => new Date(NOW - n * 24 * 60 * 60 * 1000).toISOString()

const sim = (overrides: Partial<PrioritySimulationEntry> = {}): PrioritySimulationEntry => ({
  wish_id: 'w1',
  name: 'Wish 1',
  priority: 'medium',
  star_coin_cost: 100,
  progress: 0.25,
  covered: false,
  ...overrides,
})

describe('daysEstimate', () => {
  it('returns null when balance already covers the wish', () => {
    const ledger: LedgerEntry[] = [
      { amount: 5, created_at: daysAgo(1) },
      { amount: 5, created_at: daysAgo(2) },
      { amount: 5, created_at: daysAgo(3) },
    ]
    const result = daysEstimate(150, sim({ star_coin_cost: 100 }), ledger, NOW)
    expect(result).toBeNull()
  })

  it('returns null when fewer than 3 distinct earning days exist in last 7', () => {
    const ledger: LedgerEntry[] = [
      { amount: 10, created_at: daysAgo(1) },
      { amount: 10, created_at: daysAgo(2) },
    ]
    const result = daysEstimate(0, sim({ star_coin_cost: 100 }), ledger, NOW)
    expect(result).toBeNull()
  })

  it('returns null when ledger has only outgoing transactions', () => {
    const ledger: LedgerEntry[] = [
      { amount: -5, created_at: daysAgo(1) },
      { amount: -5, created_at: daysAgo(2) },
      { amount: -5, created_at: daysAgo(3) },
    ]
    const result = daysEstimate(0, sim({ star_coin_cost: 100 }), ledger, NOW)
    expect(result).toBeNull()
  })

  it('computes ceil(remaining / dailyAvg) for stable ledger', () => {
    // 3 distinct days, sum 15 -> dailyAvg 5. Remaining = 100 - 25 = 75. days = ceil(75/5) = 15
    const ledger: LedgerEntry[] = [
      { amount: 5, created_at: daysAgo(1) },
      { amount: 5, created_at: daysAgo(2) },
      { amount: 5, created_at: daysAgo(3) },
    ]
    const result = daysEstimate(25, sim({ star_coin_cost: 100 }), ledger, NOW)
    expect(result).toBe(15)
  })

  it('rounds up — 11/5 = 3 days, not 2', () => {
    const ledger: LedgerEntry[] = [
      { amount: 5, created_at: daysAgo(1) },
      { amount: 5, created_at: daysAgo(2) },
      { amount: 5, created_at: daysAgo(3) },
    ]
    const result = daysEstimate(89, sim({ star_coin_cost: 100 }), ledger, NOW)
    // remaining = 11, dailyAvg = 5, ceil(11/5) = 3
    expect(result).toBe(3)
  })

  it('ignores transactions older than 7 days', () => {
    const ledger: LedgerEntry[] = [
      { amount: 100, created_at: daysAgo(8) }, // outside window
      { amount: 5, created_at: daysAgo(1) },
      { amount: 5, created_at: daysAgo(2) },
      { amount: 5, created_at: daysAgo(3) },
    ]
    const result = daysEstimate(25, sim({ star_coin_cost: 100 }), ledger, NOW)
    // Should ignore the 100, dailyAvg stays at 5
    expect(result).toBe(15)
  })

  it('returns null on empty ledger', () => {
    const result = daysEstimate(0, sim({ star_coin_cost: 100 }), [], NOW)
    expect(result).toBeNull()
  })

  it('returns null when star_coin_cost is missing (defensive)', () => {
    const ledger: LedgerEntry[] = [
      { amount: 5, created_at: daysAgo(1) },
      { amount: 5, created_at: daysAgo(2) },
      { amount: 5, created_at: daysAgo(3) },
    ]
    const result = daysEstimate(0, sim({ star_coin_cost: null as unknown as number }), ledger, NOW)
    expect(result).toBeNull()
  })

  it('handles fractional dailyAvg correctly — ceil to nearest day', () => {
    // 3 days totaling 7 -> dailyAvg = 7/3 ≈ 2.333. Remaining = 10. days = ceil(10 / 2.333) = 5
    const ledger: LedgerEntry[] = [
      { amount: 2, created_at: daysAgo(1) },
      { amount: 2, created_at: daysAgo(2) },
      { amount: 3, created_at: daysAgo(3) },
    ]
    const result = daysEstimate(0, sim({ star_coin_cost: 10 }), ledger, NOW)
    expect(result).toBe(5)
  })
})
