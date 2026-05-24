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

export function formatCurrency(amount: number, currency = 'CNY'): string {
  const absAmount = Math.abs(amount)
  const sign = amount < 0 ? '-' : ''
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

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

export function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
