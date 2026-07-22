import { describe, it, expect } from 'vitest'
import { formatCurrency } from '../format'

// formatCurrency is the single coercion point for money-as-str: money arrives as a
// numeric string on the wire and is coerced via Number(amount) || 0. These tests pin
// the widened number|string signature and the coercion behavior.
describe('formatCurrency', () => {
  it('accepts a numeric string identical to a number', () => {
    expect(formatCurrency('1000')).toBe(formatCurrency(1000))
  })

  it('coerces a wire string with decimals', () => {
    expect(formatCurrency('1234.56')).toBe(formatCurrency(1234.56))
  })

  it('renders zero for string "0"', () => {
    expect(formatCurrency('0')).toBe('¥0.00')
    expect(formatCurrency(0)).toBe('¥0.00')
  })

  it('collapses empty / non-numeric strings to 0 (not NaN)', () => {
    // Number('') === 0, Number('abc') === NaN -> || 0 -> 0. Must not render ¥NaN.
    expect(formatCurrency('')).toBe('¥0.00')
    expect(formatCurrency('abc')).toBe('¥0.00')
  })

  it('renders the negative sign for string negatives', () => {
    expect(formatCurrency('-500')).toBe('-¥500.00')
    expect(formatCurrency(-500)).toBe('-¥500.00')
  })

  it('uses 万 unit for CNY >= 10000 (string input)', () => {
    expect(formatCurrency('10000', 'CNY')).toBe('¥1.00万')
    expect(formatCurrency('25000', 'CNY')).toBe('¥2.50万')
  })

  it('uses 亿 unit for CNY >= 100000000 (string input)', () => {
    expect(formatCurrency('100000000', 'CNY')).toBe('¥1.00亿')
  })

  it('groups thousands for non-CNY currencies', () => {
    expect(formatCurrency('1000', 'USD')).toBe('$1,000')
  })

  it('renders sub-1000 values with two decimals', () => {
    expect(formatCurrency('999.9', 'USD')).toBe('$999.90')
    expect(formatCurrency('5', 'CNY')).toBe('¥5.00')
  })
})
