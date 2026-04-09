/**
 * Resolve a category icon string to an SVG sprite ID.
 * System categories use 'icon-*' sprite IDs; custom categories use emoji strings.
 */
export function getIconId(icon: string): string {
  return icon.startsWith('icon-') ? icon : 'icon-other'
}
