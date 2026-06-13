/**
 * Chinese summary mapping for AI step display.
 *
 * This utility provides user-friendly Chinese summaries for tool names.
 * Backend already provides display_name/icon/tool_type, so this file focuses
 * on Chinese UX transformation only (not category mapping).
 */

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

import type { ProcessStep } from '@/types/agent-stream'

/**
 * Merged summary item for display.
 * Either a single step or a merged group of same-category steps.
 */
export interface MergedSummaryItem {
  /** Unique ID for this merged item */
  id: string
  /** Whether this is a merged group or single step */
  isMerged: boolean
  /** Original steps in this group (1 for single, >1 for merged) */
  steps: ProcessStep[]
  /** Category key for merged display */
  category?: string
  /** Display text: "计算分析" or "计算分析 (3次)" */
  displayText: string
  /** i18n key for display text */
  displayTextKey: string
  /** Count of merged steps (undefined for single) */
  count?: number
}

/**
 * Merge consecutive same-category steps into summary items.
 *
 * @param steps - Process steps from normalizer
 * @returns Array of MergedSummaryItem for display
 */
export function mergeConsecutiveSteps(steps: ProcessStep[]): MergedSummaryItem[] {
  if (!steps || steps.length === 0) return []

  // Only process tool_call steps; other types pass through unchanged
  const result: MergedSummaryItem[] = []
  let currentGroup: ProcessStep[] = []
  let currentCategory: string | undefined

  for (const step of steps) {
    // Non-tool_call steps are not merged
    if (step.type !== 'tool_call') {
      // Flush any pending group first
      if (currentGroup.length > 0) {
        result.push(createMergedItem(currentGroup, currentCategory))
        currentGroup = []
        currentCategory = undefined
      }
      // Pass through non-tool steps unchanged
      result.push(createSingleItem(step))
      continue
    }

    const toolType = step.toolType || 'unknown'

    // Check if this step continues the current category group
    if (currentGroup.length === 0) {
      // Start new group
      currentGroup = [step]
      currentCategory = toolType
    } else if (toolType === currentCategory) {
      // Continue current group
      currentGroup.push(step)
    } else {
      // Category changed: flush previous group, start new one
      result.push(createMergedItem(currentGroup, currentCategory))
      currentGroup = [step]
      currentCategory = toolType
    }
  }

  // Flush final group
  if (currentGroup.length > 0) {
    result.push(createMergedItem(currentGroup, currentCategory))
  }

  return result
}

/**
 * Create a merged item from a group of same-category steps.
 */
function createMergedItem(steps: ProcessStep[], category?: string): MergedSummaryItem {
  const isMerged = steps.length > 1
  const firstStep = steps[0]

  // displayName/name only exist on tool_call type
  const isToolCall = firstStep.type === 'tool_call'
  const displayName = isToolCall ? firstStep.displayName : undefined
  const name = isToolCall ? firstStep.name : undefined

  return {
    id: `merged-${firstStep.id}`,
    isMerged,
    steps,
    category,
    displayText: isMerged ? '' : (displayName ?? name ?? ''),
    displayTextKey: isMerged ? getToolCategory(category) : getChineseSummary(name ?? '', displayName),
    count: isMerged ? steps.length : undefined,
  }
}

/**
 * Create a single item for non-tool_call steps.
 */
function createSingleItem(step: ProcessStep): MergedSummaryItem {
  return {
    id: step.id,
    isMerged: false,
    steps: [step],
    displayText: '', // Populated by component
    displayTextKey: '', // Non-tool steps use their own display logic
  }
}