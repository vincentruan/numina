import { describe, it, expect } from 'vitest'
import { previewSpend } from './previewSpend'
import type { PrioritySimulationEntry, LedgerEntry } from './types'

const NOW = new Date('2026-05-24T12:00:00Z').getTime()
const daysAgo = (n: number) => new Date(NOW - n * 24 * 60 * 60 * 1000).toISOString()

const stableLedger: LedgerEntry[] = [
  { amount: 5, created_at: daysAgo(1) },
  { amount: 5, created_at: daysAgo(2) },
  { amount: 5, created_at: daysAgo(3) },
]

const sim = (overrides: Partial<PrioritySimulationEntry>): PrioritySimulationEntry => ({
  wish_id: 'wX',
  name: 'Wish',
  priority: 'medium',
  star_coin_cost: 100,
  progress: 0,
  covered: false,
  ...overrides,
})

describe('previewSpend', () => {
  it('returns deltas with the spend wish itself excluded', () => {
    const simulation = [
      sim({ wish_id: 'a', star_coin_cost: 50, progress: 1, covered: true }),
      sim({ wish_id: 'b', star_coin_cost: 80 }),
      sim({ wish_id: 'c', star_coin_cost: 200 }),
    ]
    const result = previewSpend('a', 50, simulation, stableLedger, NOW)
    expect(result.deltas.find(d => d.wish_id === 'a')).toBeUndefined()
    expect(result.deltas.length).toBe(2)
  })

  it('AE3: pressing a covered wish moves uncovered wishes by their days_added', () => {
    // balance=50, wish A covered at 50, wish B cost=80 (needs 30 more), wish C cost=200 (needs 150 more)
    // dailyAvg from stableLedger = 5. Spend on A drops balance to 0.
    // Wish B: before remaining = 30, days_before = ceil(30/5) = 6. After: remaining = 80, days_after = 16.
    //   days_added = 16 - 6 = 10. (post-spend balance is 0, so before/after computed at balance=50 vs 0)
    // Wish C: before remaining = 150, days_before = 30. After: remaining = 200, days_after = 40. days_added = 10.
    const simulation = [
      sim({ wish_id: 'a', star_coin_cost: 50, progress: 1, covered: true }),
      sim({ wish_id: 'b', star_coin_cost: 80 }),
      sim({ wish_id: 'c', star_coin_cost: 200 }),
    ]
    const { deltas } = previewSpend('a', 50, simulation, stableLedger, NOW)
    const b = deltas.find(d => d.wish_id === 'b')!
    const c = deltas.find(d => d.wish_id === 'c')!
    expect(b.days_added).toBe(10)
    expect(c.days_added).toBe(10)
  })

  it('returns days_added: 0 for wishes that remain covered after the spend', () => {
    // balance=200, wish A cost=50 (covered), wish B cost=100 (not covered, but post-spend balance=150 still > 100)
    const simulation = [
      sim({ wish_id: 'a', star_coin_cost: 50, progress: 1, covered: true }),
      sim({ wish_id: 'b', star_coin_cost: 100, progress: 1, covered: true }),
    ]
    const { deltas } = previewSpend('a', 200, simulation, stableLedger, NOW)
    const b = deltas.find(d => d.wish_id === 'b')!
    expect(b.days_added).toBe(0)
  })

  it('returns days_added: 0 when ledger is unstable (cannot compute)', () => {
    const simulation = [
      sim({ wish_id: 'a', star_coin_cost: 50, progress: 1, covered: true }),
      sim({ wish_id: 'b', star_coin_cost: 80 }),
    ]
    const { deltas } = previewSpend('a', 50, simulation, [], NOW)
    expect(deltas[0].days_added).toBe(0)
  })

  it('reports before_progress and after_progress as fractional [0..1] values', () => {
    // balance=40, wish B cost=80, before progress = 40/80 = 0.5; spend on A=50 puts balance=-10; clamp to 0 -> 0%.
    // For preview math, post-spend balance must not go negative — clamp at 0.
    const simulation = [
      sim({ wish_id: 'a', star_coin_cost: 50, progress: 0.8, covered: false }),
      sim({ wish_id: 'b', star_coin_cost: 80 }),
    ]
    const { deltas } = previewSpend('a', 40, simulation, stableLedger, NOW)
    const b = deltas.find(d => d.wish_id === 'b')!
    expect(b.before_progress).toBeCloseTo(0.5)
    expect(b.after_progress).toBeCloseTo(0)
  })

  it('returns empty deltas when simulation has only the pressed wish', () => {
    const simulation = [sim({ wish_id: 'a', star_coin_cost: 50, covered: true })]
    const { deltas } = previewSpend('a', 50, simulation, stableLedger, NOW)
    expect(deltas).toEqual([])
  })

  it('returns empty deltas when simulation is empty', () => {
    const { deltas } = previewSpend('nonexistent', 100, [], stableLedger, NOW)
    expect(deltas).toEqual([])
  })

  it('handles when the pressed wish is not covered (still simulates the spend)', () => {
    // Pressing a wish you cannot afford: math still runs assuming you spent its cost.
    // This is non-committing UI; previewSpend is a pure projection.
    const simulation = [
      sim({ wish_id: 'a', star_coin_cost: 60 }),
      sim({ wish_id: 'b', star_coin_cost: 100 }),
    ]
    const { deltas } = previewSpend('a', 50, simulation, stableLedger, NOW)
    // balance was 50, spend 60 -> clamped to 0
    const b = deltas.find(d => d.wish_id === 'b')!
    expect(b.before_progress).toBeCloseTo(0.5) // 50/100
    expect(b.after_progress).toBeCloseTo(0) // 0/100
  })
})
