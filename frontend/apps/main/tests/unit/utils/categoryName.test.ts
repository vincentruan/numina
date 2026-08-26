import { describe, it, expect, afterEach } from 'vitest'
import { getCategoryName } from '@/utils/categoryName'
import i18n from '@/i18n'

const setLocale = (locale: 'zh-CN' | 'en-US') => {
  ;(i18n.global.locale as unknown as { value: string }).value = locale
}

afterEach(() => {
  setLocale('zh-CN')
})

describe('getCategoryName', () => {
  it('returns the localized name for system categories in zh-CN', () => {
    expect(getCategoryName({ name: '房产', is_system: true })).toBe('房产')
    expect(getCategoryName({ name: '数字货币', is_system: true })).toBe('数字货币')
  })

  it('returns the English translation for system categories in en-US', () => {
    setLocale('en-US')
    expect(getCategoryName({ name: '房产', is_system: true })).toBe('Real Estate')
    expect(getCategoryName({ name: '理财产品', is_system: true })).toBe('Wealth Management')
  })

  it('keeps the raw name for custom categories', () => {
    expect(getCategoryName({ name: '我的自定义', is_system: false })).toBe('我的自定义')
  })

  it('falls back to the raw name when the system name is unknown', () => {
    setLocale('en-US')
    expect(getCategoryName({ name: '未知分类', is_system: true })).toBe('未知分类')
  })

  it('translates by name when is_system is absent (e.g. CategoryInfo)', () => {
    setLocale('en-US')
    expect(getCategoryName({ name: '基金' })).toBe('Funds')
  })
})
