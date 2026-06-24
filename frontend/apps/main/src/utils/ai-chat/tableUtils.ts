/**
 * Table utility functions for markdown table operations.
 *
 * - htmlTableToMarkdown: Convert HTML table to markdown table string
 * - htmlTableToCsv: Convert HTML table to CSV with UTF-8 BOM
 * - downloadCsv: Trigger CSV file download in browser
 */

/** Parse HTML table into rows of cell strings */
function parseHtmlTable(html: string): string[][] {
  const rows: string[][] = []
  // Match <tr> elements
  const trRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/gi
  const tdRegex = /<t[hd][^>]*>([\s\S]*?)<\/t[hd]>/gi

  let trMatch: RegExpExecArray | null
  while ((trMatch = trRegex.exec(html)) !== null) {
    const row: string[] = []
    const rowContent = trMatch[1]
    let tdMatch: RegExpExecArray | null
    while ((tdMatch = tdRegex.exec(rowContent)) !== null) {
      // Strip inner HTML tags and decode entities
      const cell = tdMatch[1]
        .replace(/<[^>]+>/g, '')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&nbsp;/g, ' ')
        .trim()
      row.push(cell)
    }
    if (row.length > 0) {
      rows.push(row)
    }
  }
  return rows
}

/** Convert HTML table to markdown table string */
export function htmlTableToMarkdown(html: string): string {
  const rows = parseHtmlTable(html)
  if (rows.length === 0) return ''

  // Normalize column count
  const maxCols = Math.max(...rows.map(r => r.length))
  const normalized = rows.map(r => {
    while (r.length < maxCols) r.push('')
    return r
  })

  const lines: string[] = []
  // Header row
  lines.push('| ' + normalized[0].join(' | ') + ' |')
  // Separator
  lines.push('| ' + normalized[0].map(() => '---').join(' | ') + ' |')
  // Data rows
  for (let i = 1; i < normalized.length; i++) {
    lines.push('| ' + normalized[i].join(' | ') + ' |')
  }
  return lines.join('\n')
}

/** Escape a CSV field (handle commas, quotes, newlines) */
export function escapeCsvField(field: string): string {
  if (field.includes(',') || field.includes('"') || field.includes('\n')) {
    return '"' + field.replace(/"/g, '""') + '"'
  }
  return field
}

/** Convert HTML table to CSV string with UTF-8 BOM */
export function htmlTableToCsv(html: string): string {
  const rows = parseHtmlTable(html)
  if (rows.length === 0) return ''

  const BOM = '﻿'
  const csvContent = rows
    .map(row => row.map(escapeCsvField).join(','))
    .join('\r\n')
  return BOM + csvContent
}

/** Trigger a CSV file download in the browser */
export function downloadCsv(csvContent: string, filename = 'table.csv'): void {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/** Copy text to clipboard with toast feedback */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
