import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import MoneyDisplay from '../MoneyDisplay.vue'

// MoneyDisplay coerces its wire (possibly string) money props via Number(x) || 0 in
// numAmount/numOriginalValue. These tests exercise the string-amount rendering path
// that every other suite stubs out (MoneyDisplay: true).

// Display currency is CNY; no conversion unless sourceCurrency differs.
vi.mock('@/composables/useCurrency', () => ({
  useCurrency: () => ({
    currency: ref('CNY'),
    formatConverted: (n: number | string) => '¥' + n,
    convertAmount: (n: number | string) => Number(n) || 0,
  }),
}))
const getRateInfoMock = vi.fn(() => Promise.resolve(null))
const getCachedRateMock = vi.fn(() => null)
vi.mock('@/composables/useExchangeRate', () => ({
  useExchangeRate: () => ({ getRateInfo: getRateInfoMock, getCachedRate: getCachedRateMock }),
}))

describe('MoneyDisplay (string money-as-str coercion)', () => {
  it('renders a string amount grouped (numAmount coercion)', () => {
    const wrapper = mount(MoneyDisplay, { props: { amount: '1500' } })
    expect(wrapper.find('.money-value').text()).toBe('1,500')
    expect(wrapper.find('.money-prefix').text()).toBe('¥')
  })

  it('renders identically for string and number amounts', () => {
    const fromString = mount(MoneyDisplay, { props: { amount: '1500' } })
    const fromNumber = mount(MoneyDisplay, { props: { amount: 1500 } })
    expect(fromString.find('.money-value').text()).toBe(fromNumber.find('.money-value').text())
  })

  it('renders CNY 万 unit for large string amounts', () => {
    const wrapper = mount(MoneyDisplay, { props: { amount: '25000' } })
    expect(wrapper.find('.money-value').text()).toBe('2.50万')
  })

  it('collapses a non-numeric string to 0 rather than NaN', () => {
    const wrapper = mount(MoneyDisplay, { props: { amount: 'abc' } })
    expect(wrapper.find('.money-value').text()).toBe('0.00')
  })

  it('applies the negative color class and sign for a string negative', () => {
    const wrapper = mount(MoneyDisplay, {
      props: { amount: '-200', colorful: true, showSign: true },
    })
    expect(wrapper.find('.money-display').classes()).toContain('money-negative')
    expect(wrapper.find('.money-sign').text()).toBe('-')
    expect(wrapper.find('.money-value').text()).toBe('200.00')
  })

  it('applies the positive color class and + sign for a positive amount', () => {
    const wrapper = mount(MoneyDisplay, {
      props: { amount: '200', colorful: true, showSign: true },
    })
    expect(wrapper.find('.money-display').classes()).toContain('money-positive')
    expect(wrapper.find('.money-sign').text()).toBe('+')
  })

  it('shows conversion info only when sourceCurrency differs AND originalValue > 0', () => {
    // originalValue '500' (string) > 0 and sourceCurrency USD != CNY -> icon shown
    const withConversion = mount(MoneyDisplay, {
      props: { amount: '3500', sourceCurrency: 'USD', originalValue: '500' },
    })
    expect(withConversion.find('.conversion-info-icon').exists()).toBe(true)

    // originalValue 0 -> gate closed, no icon
    const noOriginal = mount(MoneyDisplay, {
      props: { amount: '3500', sourceCurrency: 'USD', originalValue: 0 },
    })
    expect(noOriginal.find('.conversion-info-icon').exists()).toBe(false)

    // same currency -> no conversion, no icon even with originalValue
    const sameCurrency = mount(MoneyDisplay, {
      props: { amount: '3500', sourceCurrency: 'CNY', originalValue: '500' },
    })
    expect(sameCurrency.find('.conversion-info-icon').exists()).toBe(false)
  })

  it('falls back to raw amount when conversion is not needed', () => {
    const wrapper = mount(MoneyDisplay, {
      props: { amount: '1500', sourceCurrency: 'CNY' },
    })
    // No conversion needed (same currency), should show raw amount
    expect(wrapper.find('.money-value').text()).toBe('1,500')
  })
})
