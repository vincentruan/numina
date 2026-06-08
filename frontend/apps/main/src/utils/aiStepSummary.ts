/**
 * Chinese summary mapping for AI step display.
 *
 * This utility provides user-friendly Chinese summaries for tool names.
 * Backend already provides display_name/icon/tool_type, so this file focuses
 * on Chinese UX transformation only (not category mapping).
 */

import { useI18n } from 'vue-i18n'

/**
 * Get Chinese summary text for a tool name.
 *
 * @param toolName - The raw tool name from backend (e.g., 'get_asset_allocation')
 * @param displayName - Backend-provided display name (fallback if no mapping)
 * @returns User-friendly Chinese summary text
 */
export function getChineseSummary(toolName: string, displayName?: string): string {
  // Map known tool names to i18n keys
  const mapping = TOOL_SUMMARY_MAP[toolName]

  // If we have a mapping, use i18n (returns Chinese text)
  if (mapping) {
    // Note: i18n must be called from component context
    // This function returns the i18n key; caller handles translation
    return mapping
  }

  // Fallback: use backend display_name if available
  if (displayName) {
    return displayName
  }

  // Final fallback: raw tool name (not ideal but safe)
  return toolName
}

/**
 * Tool name to i18n key mapping.
 * Keys reference aiStepSummary namespace in zh-CN.ts.
 */
const TOOL_SUMMARY_MAP: Record<string, string> = {
  // Data query tools
  get_asset_allocation: 'aiStepSummary.getAssetAllocation',
  get_liability_summary: 'aiStepSummary.getLiabilitySummary',
  query_assets: 'aiStepSummary.queryAssets',
  query_family_members: 'aiStepSummary.queryFamilyMembers',
  get_dashboard_overview: 'aiStepSummary.getDashboardOverview',
  get_dashboard_allocation: 'aiStepSummary.getDashboardAllocation',
  get_dashboard_trend: 'aiStepSummary.getDashboardTrend',
  get_low_usage_assets: 'aiStepSummary.getLowUsageAssets',

  // Calculation tools
  calculate_trend: 'aiStepSummary.calculateTrend',
  calculate_net_worth: 'aiStepSummary.calculateNetWorth',
  compute_allocation_ratio: 'aiStepSummary.computeAllocationRatio',
  analyze_spending: 'aiStepSummary.analyzeSpending',

  // Report generation tools
  generate_report: 'aiStepSummary.generateReport',
  create_chart: 'aiStepSummary.createChart',
  export_data: 'aiStepSummary.exportData',

  // Web search tools
  web_search: 'aiStepSummary.webSearch',
  fetch_url: 'aiStepSummary.fetchUrl',
  scrape_content: 'aiStepSummary.scrapeContent',

  // File operations
  read_file: 'aiStepSummary.readFile',
  write_file: 'aiStepSummary.writeFile',
  upload_file: 'aiStepSummary.uploadFile',

  // External API calls
  call_external_api: 'aiStepSummary.callExternalApi',
  fetch_exchange_rate: 'aiStepSummary.fetchExchangeRate',

  // Planning tools
  write_todos: 'aiStepSummary.writeTodos',

  // Generic fallback categories
  tool_unknown: 'aiStepSummary.unknownTool',
}

/**
 * Get tool category for grouping/merging consecutive steps.
 * This is a convenience function that maps tool_type to display category.
 */
export function getToolCategory(toolType?: string): string {
  if (!toolType) return 'unknown'

  const categoryMap: Record<string, string> = {
    data_query: 'aiStepSummary.categoryDataQuery',
    calculation: 'aiStepSummary.categoryCalculation',
    report_gen: 'aiStepSummary.categoryReportGen',
    web_search: 'aiStepSummary.categoryWebSearch',
    file_ops: 'aiStepSummary.categoryFileOps',
    external_api: 'aiStepSummary.categoryExternalApi',
    internal: 'aiStepSummary.categoryInternal',
  }

  return categoryMap[toolType] || 'aiStepSummary.categoryUnknown'
}

export { TOOL_SUMMARY_MAP }