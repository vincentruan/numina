/**
 * Resolve a CONTINENT_THEMES color to something three.js can parse.
 *
 * Theme colors are CSS variables (`var(--color-brand-ochre)`) so the 2D views
 * can follow theme changes. three.js cannot parse those — passing one straight
 * to MeshStandardMaterial yields a black tower. Resolve through the live
 * stylesheet at build time.
 */
import { CONTINENT_THEMES } from '@/data/continentThemes'

export function resolveThemeColor(subject: string): string {
  const theme = CONTINENT_THEMES[subject]
  const raw = theme?.color
  if (!raw) return '#808080'

  const varMatch = /^var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+))?\)$/.exec(raw.trim())
  if (!varMatch) return raw // Already a literal color

  const [, cssVar, fallback] = varMatch

  if (typeof document !== 'undefined') {
    const value = getComputedStyle(document.documentElement)
      .getPropertyValue(cssVar)
      .trim()
    if (value) return value
  }

  return fallback?.trim() || '#808080'
}
