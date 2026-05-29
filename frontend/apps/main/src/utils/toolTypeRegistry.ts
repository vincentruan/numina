/**
 * U4: Tool type registry for frontend summary templates.
 *
 * Backend is the source of truth for tool_type, display_name, and icon.
 * This registry only maps tool_type → summaryTemplate (localized description).
 *
 * Unknown tool types fallback to generic template.
 */


// Summary templates keyed by tool_type (business categorization)
// Templates are displayed during tool execution (e.g., "正在查询资产...")
export const TOOL_SUMMARY_TEMPLATES: Record<string, string> = {
  asset_query: 'aiChat.toolSummaryAssetQuery',
  report_gen: 'aiChat.toolSummaryReportGen',
  trend_calc: 'aiChat.toolSummaryTrendCalc',
  wish_analysis: 'aiChat.toolSummaryWishAnalysis',
  liability_analysis: 'aiChat.toolSummaryLiabilityAnalysis',
  allocation_analysis: 'aiChat.toolSummaryAllocationAnalysis',
}

// Default template for unknown tool types
export const DEFAULT_TOOL_SUMMARY = 'aiChat.toolSummaryUnknown'

/**
 * Get the summary template for a tool type.
 *
 * @param toolType - Business-level categorization from backend
 * @returns i18n key for the summary template
 */
export function getToolSummaryTemplate(toolType: string): string {
  return TOOL_SUMMARY_TEMPLATES[toolType] || DEFAULT_TOOL_SUMMARY
}

// Icon defaults for fallback (backend should provide, but these are safety defaults)
export const TOOL_ICON_DEFAULTS: Record<string, string> = {
  asset_query: '📊',
  report_gen: '📄',
  trend_calc: '📈',
  wish_analysis: '💫',
  liability_analysis: '💳',
  allocation_analysis: '🎯',
}

export const DEFAULT_TOOL_ICON = '⚙️'

/**
 * Get the fallback icon for a tool type if backend doesn't provide one.
 *
 * @param toolType - Business-level categorization
 * @returns Icon string (emoji or icon name)
 */
export function getToolIconFallback(toolType: string): string {
  return TOOL_ICON_DEFAULTS[toolType] || DEFAULT_TOOL_ICON
}