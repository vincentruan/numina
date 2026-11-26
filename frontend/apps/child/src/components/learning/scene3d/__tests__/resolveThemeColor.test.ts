import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/data/continentThemes', () => ({
  CONTINENT_THEMES: {
    mathematics: { color: 'var(--color-brand-ochre)' },
    science: { color: 'var(--color-brand-teal, #e6f7f5)' },
    literal: { color: '#123456' },
  },
}))

import { resolveThemeColor } from '../resolveThemeColor'

describe('resolveThemeColor', () => {
  beforeEach(() => {
    vi.stubGlobal('getComputedStyle', () => ({
      getPropertyValue: (name: string) =>
        name === '--color-brand-ochre' ? '#e8b94a' : '',
    }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('passes through literal colors', () => {
    expect(resolveThemeColor('literal')).toBe('#123456')
  })

  it('resolves var(--color-brand-ochre) from document styles', () => {
    expect(resolveThemeColor('mathematics')).toBe('#e8b94a')
  })

  it('uses the inline fallback when the CSS var is empty', () => {
    expect(resolveThemeColor('science')).toBe('#e6f7f5')
  })

  it('returns #808080 for an unknown subject', () => {
    expect(resolveThemeColor('unknown')).toBe('#808080')
  })
})
