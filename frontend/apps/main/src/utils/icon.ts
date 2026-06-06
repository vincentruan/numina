const SAFE_ICON_RE = /^icon-[a-z0-9_-]+$/

/**
 * Resolve a category icon string to an SvgIcon name.
 * System categories use 'icon-*' sprite IDs; custom categories use emoji strings.
 * Returns the bare name (e.g., 'home') for SvgIcon, which expects names without 'icon-' prefix.
 */
export function getIconId(icon: string | undefined): string {
  if (!icon || !SAFE_ICON_RE.test(icon)) return 'other'
  return icon.slice(5) // strip 'icon-' prefix
}
