export const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: '¥',
  USD: '$',
  EUR: '€',
  GBP: '£',
  JPY: '¥',
  HKD: 'HK$',
}

const CURRENCY_LOCALES: Record<string, string> = {
  CNY: 'zh-CN',
  USD: 'en-US',
  EUR: 'de-DE',
  GBP: 'en-GB',
  JPY: 'ja-JP',
  HKD: 'zh-HK',
}

// Money arrives as a numeric string on the wire (money-as-str: Decimal in compute,
// str on the wire; JS double loses precision >2^53). Accept both and coerce once here
// so callers can pass wire values directly. Number() coercion is runtime-benign for
// numeric strings ("100.00" -> 100).
export function formatCurrency(amount: number | string, currency = 'CNY'): string {
  const n = Number(amount) || 0
  const absAmount = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  const symbol = CURRENCY_SYMBOLS[currency] || currency
  const locale = CURRENCY_LOCALES[currency] || 'zh-CN'

  // CNY使用万/亿单位
  if (currency === 'CNY') {
    if (absAmount >= 100000000) {
      return `${sign}${symbol}${(absAmount / 100000000).toFixed(2)}亿`
    } else if (absAmount >= 10000) {
      return `${sign}${symbol}${(absAmount / 10000).toFixed(2)}万`
    }
  }

  // 其他货币使用标准格式
  if (absAmount >= 1000) {
    return `${sign}${symbol}${absAmount.toLocaleString(locale, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
  } else {
    return `${sign}${symbol}${absAmount.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
}

export function formatNumber(num: number): string {
  return num.toLocaleString('zh-CN')
}

export function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

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

export function formatDate(dateStr: string): string {
  const date = parseApiDate(dateStr)
  return date.toLocaleDateString(undefined, { year: 'numeric', month: '2-digit', day: '2-digit' })
}

export function formatDateTime(dateStr: string): string {
  const date = parseApiDate(dateStr)
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
