/**
 * Shared date constants for form date pickers.
 * Used by AssetForm and LiabilityForm to ensure consistent picker ranges.
 */

/** Earliest selectable date (~126 years ago). */
export const DATE_PICKER_MIN_DATE = new Date(1950, 0, 1)

/** Latest selectable date (current year + 50). */
export const DATE_PICKER_MAX_DATE = new Date(new Date().getFullYear() + 50, 11, 31)

/**
 * Sentinel value representing "infinite" / "no end date" (无限期).
 * When end_date equals this value, the UI shows it as infinite.
 */
export const INFINITE_DATE_SENTINEL = '2100-01-01'
