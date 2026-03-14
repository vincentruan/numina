export function formatCurrency(amount: number, currency = 'CNY'): string {
  const absAmount = Math.abs(amount)
  const sign = amount < 0 ? '-' : ''

  if (absAmount >= 100000000) {
    return `${sign}¥${(absAmount / 100000000).toFixed(2)}亿`
  } else if (absAmount >= 10000) {
    return `${sign}¥${(absAmount / 10000).toFixed(2)}万`
  } else if (absAmount >= 1000) {
    return `${sign}¥${absAmount.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
  } else {
    return `${sign}¥${absAmount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
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
