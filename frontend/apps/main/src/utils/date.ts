/**
 * Returns the next occurrence of the day-of-month from startDate,
 * on or after today. Clamps to the last day of the month if needed.
 */
export function getNextPaymentDate(startDate: string | null | undefined): Date | null {
  if (!startDate) return null

  const parts = startDate.split('-').map(Number)
  if (parts.length < 3 || parts.some(isNaN)) return null
  const parsed = new Date(parts[0], parts[1] - 1, parts[2])
  if (isNaN(parsed.getTime())) return null

  const payDay = parsed.getDate() // day-of-month from the start date

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  // Try this month first, then next month
  for (let monthOffset = 0; monthOffset <= 1; monthOffset++) {
    const year = today.getFullYear()
    const month = today.getMonth() + monthOffset

    // Clamp payDay to the last day of the target month
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const clampedDay = Math.min(payDay, daysInMonth)

    const candidate = new Date(year, month, clampedDay)
    candidate.setHours(0, 0, 0, 0)

    if (candidate >= today) {
      return candidate
    }
  }

  return null
}

/**
 * Returns the number of days until the next payment date.
 * 0 means today. Returns null if startDate is absent.
 */
export function getDaysUntilPayment(startDate: string | null | undefined): number | null {
  const next = getNextPaymentDate(startDate)
  if (!next) return null

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const diffMs = next.getTime() - today.getTime()
  return Math.round(diffMs / (1000 * 60 * 60 * 24))
}

/**
 * Normalize a stored ``HH:MM`` value to the two-digit form the API accepts.
 *
 * The backend validates ``digest_time`` with ``^([01]\d|2[0-3]):[0-5]\d$``, but
 * rows written before that check existed can hold unpadded values like
 * ``"8:00"``. Every save echoes this field back verbatim, so an untouched
 * legacy value would make the whole update fail validation — the channel
 * could not even be renamed. Normalize on read so the dirty value is repaired
 * on the next save instead of blocking it.
 *
 * Anything unparseable falls back to ``fallback`` rather than throwing: the
 * field is a scheduling hint, not user data worth surfacing an error for.
 */
export function normalizeDigestTime(
  value: string | null | undefined,
  fallback = '21:00'
): string {
  if (!value) return fallback
  const match = /^\s*(\d{1,2}):(\d{1,2})\s*$/.exec(value)
  if (!match) return fallback
  const hour = Number(match[1])
  const minute = Number(match[2])
  if (hour > 23 || minute > 59) return fallback
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}
