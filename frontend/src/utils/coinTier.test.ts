import { describe, it, expect } from 'vitest'
import { splitCoinTiers, formatCoinTiers } from '@/utils/coinTier'

describe('splitCoinTiers', () => {
  it('returns all zeros for 0 coins', () => {
    expect(splitCoinTiers(0)).toEqual({ gold: 0, silver: 0, copper: 0 })
  })

  it('returns only copper for small amounts', () => {
    expect(splitCoinTiers(5)).toEqual({ gold: 0, silver: 0, copper: 5 })
  })

  it('converts copper to silver at threshold', () => {
    expect(splitCoinTiers(10)).toEqual({ gold: 0, silver: 1, copper: 0 })
    expect(splitCoinTiers(15)).toEqual({ gold: 0, silver: 1, copper: 5 })
  })

  it('converts silver to gold at threshold', () => {
    expect(splitCoinTiers(100)).toEqual({ gold: 1, silver: 0, copper: 0 })
    expect(splitCoinTiers(125)).toEqual({ gold: 1, silver: 2, copper: 5 })
  })

  it('handles large amounts correctly', () => {
    // 999 = 9 gold (900) + 9 silver (90) + 9 copper
    expect(splitCoinTiers(999)).toEqual({ gold: 9, silver: 9, copper: 9 })
  })

  it('respects custom copperToSilver rate', () => {
    expect(splitCoinTiers(5, 5, 10)).toEqual({ gold: 0, silver: 1, copper: 0 })
    expect(splitCoinTiers(7, 5, 10)).toEqual({ gold: 0, silver: 1, copper: 2 })
  })

  it('respects custom silverToGold rate', () => {
    expect(splitCoinTiers(50, 10, 5)).toEqual({ gold: 1, silver: 0, copper: 0 })
    expect(splitCoinTiers(75, 10, 5)).toEqual({ gold: 1, silver: 2, copper: 5 })
  })

  it('boundary: exactly one gold coin', () => {
    expect(splitCoinTiers(100, 10, 10)).toEqual({ gold: 1, silver: 0, copper: 0 })
  })

  it('boundary: one below gold threshold', () => {
    expect(splitCoinTiers(99, 10, 10)).toEqual({ gold: 0, silver: 9, copper: 9 })
  })
})

describe('formatCoinTiers', () => {
  it('formats all tiers', () => {
    expect(formatCoinTiers({ gold: 1, silver: 2, copper: 5 })).toBe('1金 2银 5铜')
  })

  it('omits zero tiers', () => {
    expect(formatCoinTiers({ gold: 0, silver: 3, copper: 0 })).toBe('3银')
    expect(formatCoinTiers({ gold: 2, silver: 0, copper: 0 })).toBe('2金')
  })

  it('shows copper when all zero', () => {
    expect(formatCoinTiers({ gold: 0, silver: 0, copper: 0 })).toBe('0铜')
  })
})
