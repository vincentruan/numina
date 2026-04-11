/**
 * Resolve a category icon string to an SVG sprite ID.
 * System categories use 'icon-*' sprite IDs; custom categories use emoji strings.
 */
export function getIconId(icon: string | undefined): string {
  if (!icon) return 'icon-other'
  return icon.startsWith('icon-') ? icon : 'icon-other'
}
