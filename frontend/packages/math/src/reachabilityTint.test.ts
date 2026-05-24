import { describe, it, expect } from 'vitest'
import { reachabilityTint } from './reachabilityTint'
import type { PrioritySimulationEntry } from './types'

const sim = (overrides: Partial<PrioritySimulationEntry> = {}): PrioritySimulationEntry => ({
  wish_id: 'w1',
  name: 'Wish 1',
  priority: 'medium',
  star_coin_cost: 100,
  progress: 0.25,
  covered: false,
  ...overrides,
})

describe('reachabilityTint', () => {
  it('returns "green" when wish is covered', () => {
    const entry = sim({ covered: true })
    expect(reachabilityTint(entry, 5)).toBe('green')
  })

  it('returns "green" when covered, even with null daysEstimate', () => {
    const entry = sim({ covered: true })
    expect(reachabilityTint(entry, null)).toBe('green')
  })

  it('returns "gray" when not covered AND daysEstimate is null (unstable)', () => {
    const entry = sim({ covered: false })
    expect(reachabilityTint(entry, null)).toBe('gray')
  })

  it('returns "yellow" when not covered AND daysEstimate <= 14', () => {
    const entry = sim({ covered: false })
    expect(reachabilityTint(entry, 1)).toBe('yellow')
    expect(reachabilityTint(entry, 7)).toBe('yellow')
    expect(reachabilityTint(entry, 14)).toBe('yellow')
  })

  it('returns "red" when not covered AND daysEstimate > 14', () => {
    const entry = sim({ covered: false })
    expect(reachabilityTint(entry, 15)).toBe('red')
    expect(reachabilityTint(entry, 30)).toBe('red')
    expect(reachabilityTint(entry, 365)).toBe('red')
  })

  it('boundary at exactly 14 days = yellow; exactly 15 days = red', () => {
    const entry = sim({ covered: false })
    expect(reachabilityTint(entry, 14)).toBe('yellow')
    expect(reachabilityTint(entry, 15)).toBe('red')
  })

  it('AE1: balance scenario — 3 wishes (covered / 10d / 30d) => green / yellow / red', () => {
    expect(reachabilityTint(sim({ covered: true }), null)).toBe('green')
    expect(reachabilityTint(sim({ covered: false }), 10)).toBe('yellow')
    expect(reachabilityTint(sim({ covered: false }), 30)).toBe('red')
  })

  it('AE4: gray when ledger is unstable for non-covered wish', () => {
    const entry = sim({ covered: false })
    expect(reachabilityTint(entry, null)).toBe('gray')
  })
})
