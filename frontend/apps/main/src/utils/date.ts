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
