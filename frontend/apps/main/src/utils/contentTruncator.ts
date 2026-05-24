export interface TruncationResult {
  truncated: string
  isTruncated: boolean
  fullContent: string
}

/**
 * Truncate text content with configurable max chars.
 * Returns both truncated and full content for expand/collapse UI.
 */
export function truncateContent(content: string, maxChars: number = 200): TruncationResult {
  if (!content) {
    return { truncated: '', isTruncated: false, fullContent: '' }
  }

  if (content.length <= maxChars) {
    return { truncated: content, isTruncated: false, fullContent: content }
  }

  return {
    truncated: content.slice(0, maxChars) + '...',
    isTruncated: true,
    fullContent: content,
  }
}

/**
 * Truncate JSON representation with configurable max chars.
 */
export function truncateJson(obj: unknown, maxChars: number = 300): TruncationResult {
  if (obj === null || obj === undefined) {
    return { truncated: '', isTruncated: false, fullContent: '' }
  }

  const fullJson = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2)

  if (fullJson.length <= maxChars) {
    return { truncated: fullJson, isTruncated: false, fullContent: fullJson }
  }

  // For objects, try to show structure hint
  if (typeof obj === 'object' && obj !== null) {
    const objType = Array.isArray(obj) ? `Array(${obj.length})` : `Object(${Object.keys(obj).length} keys)`
    return {
      truncated: `${objType} { ... }`,
      isTruncated: true,
      fullContent: fullJson,
    }
  }

  return {
    truncated: fullJson.slice(0, maxChars) + '...',
    isTruncated: true,
    fullContent: fullJson,
  }
}

/**
 * Calculate size label for truncated content (e.g., "2.3KB").
 */
export function formatContentSize(content: string): string {
  const bytes = new Blob([content]).size
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}
