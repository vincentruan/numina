export interface ToolDisplayInfo {
  displayName: string
  icon: string
  argsTemplate: string
  resultTemplate: string
}

// Default fallback for unknown tools
const DEFAULT_DISPLAY: ToolDisplayInfo = {
  displayName: '调用工具',
  icon: '⚙️',
  argsTemplate: '参数：{args}',
  resultTemplate: '执行完成',
}

// Known tool mappings with Chinese friendly labels.
// Backend `display_name`/`icon` always win when present (per plan KD: backend
// is the source of truth for tool_type/display_name/icon). This map only
// supplies argsTemplate/resultTemplate fallbacks and per-name defaults that
// kick in when the backend metadata is missing.
const TOOL_DISPLAY_MAP: Record<string, ToolDisplayInfo> = {
  web_search: {
    displayName: '搜索网络',
    icon: '🔍',
    argsTemplate: '查询：{query}',
    resultTemplate: '找到 {count} 个结果',
  },
  tavily_search: {
    displayName: '搜索网络',
    icon: '🔍',
    argsTemplate: '查询：{query}',
    resultTemplate: '找到 {count} 个结果',
  },
  read_file: {
    displayName: '读取文件',
    icon: '📄',
    argsTemplate: '文件：{path}',
    resultTemplate: '读取 {lines} 行',
  },
  write_file: {
    displayName: '写入文件',
    icon: '✏️',
    argsTemplate: '文件：{path}',
    resultTemplate: '写入 {lines} 行',
  },
  bash: {
    displayName: '执行命令',
    icon: '⚙️',
    argsTemplate: '命令：{command}',
    resultTemplate: '执行成功',
  },
  // Asset queries (4 core business tools — plan §U4)
  get_assets: {
    displayName: '查询资产',
    icon: '📊',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条资产',
  },
  get_asset_list: {
    displayName: '查询资产列表',
    icon: '📊',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条资产',
  },
  get_dashboard_overview: {
    displayName: '读取资产概览',
    icon: '📊',
    argsTemplate: '范围：{scope}',
    resultTemplate: '总资产 {total}',
  },
  get_dashboard_allocation: {
    displayName: '读取资产配置',
    icon: '📊',
    argsTemplate: '范围：{scope}',
    resultTemplate: '生成配置图',
  },
  get_low_usage_assets: {
    displayName: '扫描闲置资产',
    icon: '📊',
    argsTemplate: '阈值：{threshold} 天',
    resultTemplate: '发现 {count} 个闲置',
  },
  get_liabilities: {
    displayName: '查询负债',
    icon: '📊',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条负债',
  },
  get_liability_list: {
    displayName: '获取负债列表',
    icon: '📉',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条负债',
  },
  // Trend calculation
  get_dashboard_trend: {
    displayName: '计算资产趋势',
    icon: '📈',
    argsTemplate: '时间范围：{range}',
    resultTemplate: '趋势 {trend}',
  },
  calculate_net_worth: {
    displayName: '计算净资产',
    icon: '💰',
    argsTemplate: '时间范围：{period}',
    resultTemplate: '净资产 {value}',
  },
  // Reports
  generate_report: {
    displayName: '生成家庭报告',
    icon: '📝',
    argsTemplate: '报告类型：{report_type}',
    resultTemplate: '生成 {sections} 节报告',
  },
  compose_summary: {
    displayName: '生成摘要',
    icon: '📝',
    argsTemplate: '主题：{topic}',
    resultTemplate: '摘要 {chars} 字',
  },
  analyze_portfolio: {
    displayName: '分析资产组合',
    icon: '📈',
    argsTemplate: '资产范围：{scope}',
    resultTemplate: '生成分析报告',
  },
  // Wish / spending analysis (心愿)
  analyze_wishes: {
    displayName: '分析心愿计划',
    icon: '💝',
    argsTemplate: '心愿：{wish_name}',
    resultTemplate: '可达性 {reachability}',
  },
  analyze_spending_leaks: {
    displayName: '分析支出漏洞',
    icon: '💝',
    argsTemplate: '范围：{scope}',
    resultTemplate: '发现 {count} 项漏洞',
  },
}

// tool_type → fallback display info, used when backend supplied a tool_type
// but the specific tool name isn't in TOOL_DISPLAY_MAP (e.g. a new asset
// query tool added to the backend registry without a frontend entry).
const TOOL_TYPE_FALLBACK: Record<string, Pick<ToolDisplayInfo, 'displayName' | 'icon'>> = {
  asset_query: { displayName: '查询资产', icon: '📊' },
  trend_calc: { displayName: '计算趋势', icon: '📈' },
  report_gen: { displayName: '生成报告', icon: '📝' },
  wish_analysis: { displayName: '分析心愿', icon: '💝' },
  web_search: { displayName: '搜索网络', icon: '🔍' },
}

/**
 * Get display info for a tool, falling back to defaults for unknown tools.
 * Backend-provided display_name/icon take precedence when available.
 * When the tool name isn't in the map, tool_type provides a second-level
 * fallback (e.g. "asset_query" → 📊 查询资产).
 */
export function getToolDisplayInfo(
  toolName: string,
  backendDisplayName?: string,
  backendIcon?: string,
  toolType?: string,
): ToolDisplayInfo {
  const mapping = TOOL_DISPLAY_MAP[toolName]
  const typeFallback = toolType ? TOOL_TYPE_FALLBACK[toolType] : undefined

  return {
    displayName: backendDisplayName || mapping?.displayName || typeFallback?.displayName || DEFAULT_DISPLAY.displayName,
    icon: backendIcon || mapping?.icon || typeFallback?.icon || DEFAULT_DISPLAY.icon,
    argsTemplate: mapping?.argsTemplate || DEFAULT_DISPLAY.argsTemplate,
    resultTemplate: mapping?.resultTemplate || DEFAULT_DISPLAY.resultTemplate,
  }
}

/**
 * Format args summary using template or fallback to JSON truncation.
 */
export function formatArgsSummary(
  args: Record<string, unknown>,
  template: string,
  maxChars: number = 60,
): string {
  // Try template-based formatting
  const formatted = template.replace(/\{(\w+)\}/g, (_, key) => {
    const value = args[key]
    if (value === undefined) return ''
    if (typeof value === 'string') return value.length > maxChars ? value.slice(0, maxChars) + '...' : value
    return String(value)
  })

  // If template produced meaningful content, use it
  if (formatted !== template && formatted.length > 0) {
    return formatted
  }

  // Fallback: truncate JSON representation
  const json = JSON.stringify(args)
  return json.length > maxChars ? json.slice(0, maxChars) + '...' : json
}

/**
 * Format result summary using template or provided summary.
 */
export function formatResultSummary(
  result: unknown,
  template: string,
  providedSummary?: string,
  success: boolean = true,
  maxChars: number = 80,
): string {
  // Use backend-provided summary if available
  if (providedSummary) {
    return providedSummary.length > maxChars ? providedSummary.slice(0, maxChars) + '...' : providedSummary
  }

  // Template-based formatting for known result patterns
  if (result && typeof result === 'object') {
    const obj = result as Record<string, unknown>
    const formatted = template.replace(/\{(\w+)\}/g, (_, key) => {
      const value = obj[key]
      if (value === undefined) return ''
      return String(value)
    })
    if (formatted !== template) return formatted
  }

  // Success/error fallback
  return success ? '执行完成' : '执行失败'
}
