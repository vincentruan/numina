/**
 * materials — bridge from clay.css design tokens to three.js Color instances.
 *
 * Reads CSS custom properties via getComputedStyle() and caches three.js Color
 * objects keyed by token name. When brand colors change (e.g., dark mode toggle),
 * call `invalidateCache()` so the next `clayColor()` call re-reads from the DOM.
 *
 * Usage:
 *   import { clayColor, invalidateCache } from '@/motion/materials'
 *   const primary = clayColor('primary') // THREE.Color from --color-primary
 */
import { Color } from 'three'

const cache = new Map<string, Color>()

/** Clay token name → CSS custom property mapping. */
const TOKEN_MAP: Record<string, string> = {
  primary: '--color-primary',
  canvas: '--color-canvas',
  ink: '--color-ink',
  body: '--color-body',
  muted: '--color-muted',
  'surface-card': '--color-surface-card',
  'surface-soft': '--color-surface-soft',
  hairline: '--color-hairline',
  'brand-pink': '--color-brand-pink',
  'brand-teal': '--color-brand-teal',
  'brand-lavender': '--color-brand-lavender',
  'brand-peach': '--color-brand-peach',
  'brand-ochre': '--color-brand-ochre',
  'brand-mint': '--color-brand-mint',
  'brand-coral': '--color-brand-coral',
  'ocean-sea': '--ocean-sea-color',
  'ocean-land': '--ocean-land-color',
}

/**
 * Resolve a clay.css token to a three.js Color.
 * Returns a cached instance — callers must not mutate it.
 */
export function clayColor(token: string): Color {
  const cached = cache.get(token)
  if (cached) return cached

  const cssVar = TOKEN_MAP[token]
  if (!cssVar) {
    console.warn(`[materials] Unknown clay token: "${token}"`)
    return new Color(0x808080)
  }

  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(cssVar)
    .trim()

  if (!value) {
    console.warn(`[materials] CSS var "${cssVar}" is empty`)
    return new Color(0x808080)
  }

  const color = new Color(value)
  cache.set(token, color)
  return color
}

/** Clear the color cache — call after theme changes or dark mode toggle. */
export function invalidateCache(): void {
  // Dispose cached Color objects to free references
  cache.forEach((color) => { color.set(0x000000) })
  cache.clear()
}

/**
 * Watch for dark mode toggle and invalidate the color cache.
 * Call once at module load — sets up a MutationObserver on <html>.
 */
function watchThemeChanges(): void {
  if (typeof MutationObserver === 'undefined' || typeof document === 'undefined') return
  const observer = new MutationObserver(() => { invalidateCache() })
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
}
watchThemeChanges()
