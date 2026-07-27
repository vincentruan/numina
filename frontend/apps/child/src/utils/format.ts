/**
 * Parse an ISO date string from the backend API.
 *
 * Backend stores naive UTC datetimes (no timezone suffix). JavaScript's
 * ``new Date()`` treats such strings as local time — an 8h error for UTC+8
 * users. This function detects the missing timezone and appends ``Z`` so the
 * date is correctly interpreted as UTC.
 *
 * Already timezone-aware strings (ending with ``Z`` or ``±HH:MM``) pass through.
 */
export function parseApiDate(dateStr: string | number): Date {
  if (dateStr == null || dateStr === '') return new Date(NaN)
  // Numeric epoch (e.g. test mocks or Date.now()) — parse directly
  if (typeof dateStr === 'number') return new Date(dateStr)
  // Already has timezone info — parse as-is
  if (dateStr.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(dateStr)) {
    return new Date(dateStr)
  }
  // Naive ISO string from backend — treat as UTC
  return new Date(dateStr + 'Z')
}

/**
 * Parse a date-only string (``YYYY-MM-DD``) as **local** midnight.
 *
 * ``new Date("2024-03-15")`` per ECMA-262 parses as *UTC* midnight, which
 * in UTC+8 is 08:00 local.  When comparing against ``new Date()`` (local)
 * for day-level arithmetic the result is off by one day.  This helper
 * constructs a local-midnight Date so day diffs are calendar-correct.
 */
export function parseLocalDate(dateStr: string): Date {
  if (!dateStr) return new Date(NaN)
  const parts = dateStr.split('-').map(Number)
  if (parts.length < 3 || parts.some(isNaN)) return new Date(NaN)
  return new Date(parts[0], parts[1] - 1, parts[2])
}
