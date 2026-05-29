/**
 * U6: Suggestion templates with interpolation.
 *
 * Templates like "查看{category}详情" with context-derived variable values.
 * v1: frontend-only interpolation from conversation context.
 * v2: will connect to backend LLM API for dynamic generation.
 */

// Template definitions with variable placeholders
export const SUGGESTION_TEMPLATES = [
  '查看{category}详情',
  '{category}趋势如何',
  '分析我的{category}配置',
  '对比{category}变化',
] as const

// Context for extracting variable values
export interface SuggestionContext {
  /** Asset categories mentioned in the conversation (e.g., ['房产', '基金']) */
  categories?: string[]
  /** Default category fallback if none detected */
  defaultCategory?: string
}

// Default values for missing variables
const DEFAULT_VALUES: Record<string, string> = {
  category: '资产',
}

/**
 * Interpolate a template string with context values.
 *
 * Example: "查看{category}详情" + { categories: ['房产'] } → "查看房产详情"
 */
export function interpolateTemplate(
  template: string,
  context: SuggestionContext
): string {
  // Extract first available category or use default
  const category =
    context.categories?.[0] || context.defaultCategory || DEFAULT_VALUES['category']

  // Replace placeholders
  return template.replace(/\{(\w+)\}/g, (match, key) => {
    if (key === 'category') {
      return category
    }
    return DEFAULT_VALUES[key] || match
  })
}

/**
 * Generate suggestion chips from templates and context.
 *
 * Uses deterministic selection (cycled by category hash) for stable computed results.
 *
 * @param context - Conversation context for variable extraction
 * @param maxSuggestions - Maximum number of suggestions to return (default: 4)
 * @returns Array of interpolated suggestion strings
 */
export function generateSuggestions(
  context: SuggestionContext,
  maxSuggestions: number = 4
): string[] {
  const suggestions: string[] = []

  // Deterministic ordering: shift templates based on first category hashcode
  const seed = (context.categories?.[0] || context.defaultCategory || '').length
  const offset = seed % SUGGESTION_TEMPLATES.length
  const ordered = [
    ...SUGGESTION_TEMPLATES.slice(offset),
    ...SUGGESTION_TEMPLATES.slice(0, offset),
  ]

  for (const template of ordered) {
    if (suggestions.length >= maxSuggestions) break
    const interpolated = interpolateTemplate(template, context)
    if (!suggestions.includes(interpolated)) {
      suggestions.push(interpolated)
    }
  }

  return suggestions
}

/**
 * Extract categories from conversation messages.
 *
 * Looks for known asset categories in message content.
 */
export function extractCategoriesFromMessages(messages: string[]): string[] {
  // Known category keywords (expand as needed)
  const categoryKeywords = [
    '房产',
    '基金',
    '股票',
    '存款',
    '理财',
    '保险',
    '车辆',
    '收藏',
    '资产',
  ]

  const found: string[] = []
  for (const msg of messages) {
    for (const keyword of categoryKeywords) {
      if (msg.includes(keyword) && !found.includes(keyword)) {
        found.push(keyword)
      }
    }
  }

  return found.length > 0 ? found : ['资产']
}