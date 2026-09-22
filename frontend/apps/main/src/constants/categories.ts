/**
 * System category seed names — the raw Chinese names used by the backend seed
 * (see `server/apps/backend/app/bootstrap/categories.py`).
 *
 * These are the STABLE identifiers for system categories. The display name
 * shown in the UI is localised via `getCategoryName()` → `categoryNames.*`
 * i18n keys, but the `name` field on a seeded Category row is always one of
 * these Chinese strings.
 *
 * Centralise magic-string comparisons here so a future rename only touches
 * one file.
 */

/** "其他" wish-type categories — non-asset wish types that hide converts_to_asset. */
export const WISH_TYPE_CATEGORY_NAMES = new Set(['旅游', '租房'])

/** Travel wish category name. */
export const TRAVEL_CATEGORY_NAME = '旅游'

/** Rental wish category name. */
export const RENTAL_CATEGORY_NAME = '租房'

/** Check whether a category name belongs to a wish-type ("other") category. */
export function isWishTypeCategory(name: string | undefined): boolean {
  return !!name && WISH_TYPE_CATEGORY_NAMES.has(name)
}
