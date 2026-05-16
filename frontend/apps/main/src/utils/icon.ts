const SAFE_ICON_RE = /^icon-[a-z0-9_-]+$/i

/**
 * Resolve a category icon string to an SVG sprite ID.
 * System categories use 'icon-*' sprite IDs; custom categories use emoji strings.
 */
export function getIconId(icon: string | undefined): string {
  if (!icon || !SAFE_ICON_RE.test(icon)) return 'icon-other'
  return icon
}
