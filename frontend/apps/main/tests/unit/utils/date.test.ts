import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { getNextPaymentDate, getDaysUntilPayment } from '@/utils/date'

describe('getNextPaymentDate', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns null for null input', () => {
    expect(getNextPaymentDate(null)).toBeNull()
  })

  it('returns null for undefined input', () => {
    expect(getNextPaymentDate(undefined)).toBeNull()
  })

  it('returns null for empty string', () => {
    expect(getNextPaymentDate('')).toBeNull()
  })

  it('returns this month date when pay day has not passed yet', () => {
    // Today is June 10, 2026; start_date day=15 → next payment is June 15
    vi.setSystemTime(new Date(2026, 5, 10))
    const result = getNextPaymentDate('2026-06-15')
    expect(result).not.toBeNull()
    expect(result!.getFullYear()).toBe(2026)
    expect(result!.getMonth()).toBe(5) // June = 5
    expect(result!.getDate()).toBe(15)
  })

  it('returns next month date when pay day has already passed', () => {
    // Today is June 10, 2026; start_date day=5 → next payment is July 5
    vi.setSystemTime(new Date(2026, 5, 10))
    const result = getNextPaymentDate('2026-06-05')
    expect(result).not.toBeNull()
    expect(result!.getFullYear()).toBe(2026)
    expect(result!.getMonth()).toBe(6) // July = 6
    expect(result!.getDate()).toBe(5)
  })

  it('returns today when pay day is today', () => {
    // Today is June 15, 2026; start_date day=15 → next payment is today
    vi.setSystemTime(new Date(2026, 5, 15))
    const result = getNextPaymentDate('2026-06-15')
    expect(result).not.toBeNull()
    expect(result!.getFullYear()).toBe(2026)
    expect(result!.getMonth()).toBe(5)
    expect(result!.getDate()).toBe(15)
  })

  it('clamps day 31 to Feb 28 in a non-leap year', () => {
    // Today is Feb 1, 2025 (non-leap); start_date day=31 → Feb 28
    vi.setSystemTime(new Date(2025, 1, 1))
    const result = getNextPaymentDate('2025-01-31')
    expect(result).not.toBeNull()
    expect(result!.getFullYear()).toBe(2025)
    expect(result!.getMonth()).toBe(1) // February = 1
    expect(result!.getDate()).toBe(28)
  })

  it('clamps day 31 to Feb 29 in a leap year', () => {
    // Today is Feb 1, 2028 (leap year); start_date day=31 → Feb 29
    vi.setSystemTime(new Date(2028, 1, 1))
    const result = getNextPaymentDate('2028-01-31')
    expect(result).not.toBeNull()
    expect(result!.getFullYear()).toBe(2028)
    expect(result!.getMonth()).toBe(1) // February = 1
    expect(result!.getDate()).toBe(29)
  })

  it('clamps day 31 to April 30', () => {
    // Today is Apr 1, 2026; start_date day=31 → April 30
    vi.setSystemTime(new Date(2026, 3, 1))
    const result = getNextPaymentDate('2026-01-31')
    expect(result).not.toBeNull()
    expect(result!.getFullYear()).toBe(2026)
    expect(result!.getMonth()).toBe(3) // April = 3
    expect(result!.getDate()).toBe(30)
  })
})

describe('getDaysUntilPayment', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns 0 when due date is today', () => {
    vi.setSystemTime(new Date(2026, 5, 15))
    expect(getDaysUntilPayment('2026-06-15')).toBe(0)
  })

  it('returns null for null input', () => {
    expect(getDaysUntilPayment(null)).toBeNull()
  })

  it('returns null for undefined input', () => {
    expect(getDaysUntilPayment(undefined)).toBeNull()
  })

  it('returns positive number of days until next payment', () => {
    // Today is June 10; pay day is 15 → 5 days
    vi.setSystemTime(new Date(2026, 5, 10))
    expect(getDaysUntilPayment('2026-06-15')).toBe(5)
  })
})
