import { describe, expect, it } from 'vitest'
import {
  CONTINENT_THEMES,
  DEFAULT_THEME,
  getContinentTheme,
  getTerrainClass,
} from '../continentThemes'

describe('continentThemes', () => {
  it('has themes for all common subjects', () => {
    const expected = [
      'mathematics', 'science', 'chinese', 'english', 'physics',
      'chemistry', 'biology', 'history', 'geography', 'politics',
      'art', 'music', 'physical_education', 'information_technology',
    ]
    for (const subject of expected) {
      expect(CONTINENT_THEMES[subject]).toBeDefined()
      expect(CONTINENT_THEMES[subject].terrain).toBeTruthy()
      expect(CONTINENT_THEMES[subject].icon).toBeTruthy()
    }
  })

  it('returns default theme for unknown subjects', () => {
    const theme = getContinentTheme('nonexistent')
    expect(theme).toBe(DEFAULT_THEME)
    expect(theme.terrain).toBe('default')
    expect(theme.icon).toBe('📚')
  })

  it('returns correct theme for known subjects', () => {
    expect(getContinentTheme('mathematics').terrain).toBe('math')
    expect(getContinentTheme('mathematics').icon).toBe('📐')
    expect(getContinentTheme('science').terrain).toBe('science')
    expect(getContinentTheme('chinese').terrain).toBe('language')
  })

  it('getTerrainClass returns correct CSS class', () => {
    expect(getTerrainClass('mathematics')).toBe('territory--math')
    expect(getTerrainClass('art')).toBe('territory--arts')
    expect(getTerrainClass('unknown')).toBe('territory--default')
  })
})
