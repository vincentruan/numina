export const EMOJI_TO_ICONIFY: Record<string, string> = {
  '🤖': 'lucide:bot',
  '🏥': 'lucide:hospital',
  '💰': 'lucide:coins',
  '🎯': 'lucide:target',
  '📊': 'lucide:bar-chart-3',
  '🔍': 'lucide:search',
  '💡': 'lucide:lightbulb',
  '🛡️': 'lucide:shield-check',
  '🛡': 'lucide:shield-check',
  '📈': 'lucide:trending-up',
  '🧮': 'lucide:calculator',
  '🏠': 'lucide:home',
  '💳': 'lucide:credit-card',
  '🎓': 'lucide:graduation-cap',
  '🌟': 'lucide:star',
  '⚡': 'lucide:zap',
  '🔧': 'lucide:wrench',
  '📋': 'lucide:clipboard-list',
  '🧠': 'lucide:brain',
  '✨': 'lucide:sparkles',
  '🎨': 'lucide:palette'
}

export const ICON_OPTIONS = [
  'lucide:bot',
  'lucide:hospital',
  'lucide:coins',
  'lucide:target',
  'lucide:bar-chart-3',
  'lucide:search',
  'lucide:lightbulb',
  'lucide:shield-check',
  'lucide:trending-up',
  'lucide:calculator',
  'lucide:home',
  'lucide:credit-card',
  'lucide:graduation-cap',
  'lucide:star',
  'lucide:zap',
  'lucide:wrench',
  'lucide:clipboard-list',
  'lucide:brain',
  'lucide:sparkles',
  'lucide:palette'
]

/**
 * Checks if a string represents an emoji icon (or doesn't use Iconify's colon notation)
 */
export function isEmoji(str?: string): boolean {
  if (!str) return false
  return !str.includes(':')
}

/**
 * Resolves an agent icon name, mapping emojis to Iconify equivalents if available
 */
export function getAgentIcon(iconName?: string): string {
  if (!iconName) return 'lucide:bot'
  return EMOJI_TO_ICONIFY[iconName] || iconName
}
