import { describe, it, expect } from 'vitest'
import { CONTINENT_THEMES, DEFAULT_THEME, getContinentTheme, getTerrainClass } from '../continentThemes'

/** Subject slugs that can render in the castle across both taxonomies (U3). */
const OS_TAXONOMY_CORE = ['mathematics', 'science', 'english', 'history']
const OS_TAXONOMY_ADDED = [
  'computing',
  'learning_to_learn',
  'life_skills',
  'personal_social',
]
const BEIJING_ADDED = [
  'ethics_law',
  'general_technology',
  'pe_health',
  'labor',
  'comprehensive_practical',
]

describe('continentThemes — castle subject coverage', () => {
  it.each([...OS_TAXONOMY_CORE, ...OS_TAXONOMY_ADDED, ...BEIJING_ADDED])(
    'resolves %s to a non-default theme',
    (subject) => {
      const theme = getContinentTheme(subject)
      expect(theme).not.toEqual(DEFAULT_THEME)
      expect(theme.subject).toBe(subject)
    },
  )

  it.each([...OS_TAXONOMY_ADDED, ...BEIJING_ADDED])(
    'gives %s a real colour token, not the default secondary text colour',
    (subject) => {
      const theme = getContinentTheme(subject)
      expect(theme.color).toContain('--color-brand-')
      // --color-brand-sage is never defined in clay.css — must not be used.
      expect(theme.color).not.toContain('--color-brand-sage')
    },
  )

  it.each([...OS_TAXONOMY_ADDED, ...BEIJING_ADDED])(
    'returns a valid terrain class for %s',
    (subject) => {
      expect(getTerrainClass(subject)).toMatch(/^territory--(math|science|language|social|arts)$/)
    },
  )

  it('still falls back to DEFAULT_THEME for unknown subjects', () => {
    expect(getContinentTheme('astrology')).toEqual(DEFAULT_THEME)
    expect(getTerrainClass('astrology')).toBe('territory--default')
  })

  it('keeps every theme entry keyed by its own subject', () => {
    for (const [key, theme] of Object.entries(CONTINENT_THEMES)) {
      expect(theme.subject).toBe(key)
    }
  })
})
