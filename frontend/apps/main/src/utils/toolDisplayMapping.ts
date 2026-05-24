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

// Known tool mappings with Chinese friendly labels
const TOOL_DISPLAY_MAP: Record<string, ToolDisplayInfo> = {
  web_search: {
    displayName: '搜索文档',
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
  get_asset_list: {
    displayName: '获取资产列表',
    icon: '📊',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条资产',
  },
  analyze_portfolio: {
    displayName: '分析资产组合',
    icon: '📈',
    argsTemplate: '资产范围：{scope}',
    resultTemplate: '生成分析报告',
  },
  get_liability_list: {
    displayName: '获取负债列表',
    icon: '📉',
    argsTemplate: '筛选：{filter}',
    resultTemplate: '返回 {count} 条负债',
  },
  calculate_net_worth: {
    displayName: '计算净资产',
    icon: '💰',
    argsTemplate: '时间范围：{period}',
    resultTemplate: '净资产 {value}',
  },
}

/**
 * Get display info for a tool, falling back to defaults for unknown tools.
 * Backend-provided display_name/icon take precedence when available.
 */
export function getToolDisplayInfo(
  toolName: string,
  backendDisplayName?: string,
  backendIcon?: string,
): ToolDisplayInfo {
  const mapping = TOOL_DISPLAY_MAP[toolName] || DEFAULT_DISPLAY

  return {
    displayName: backendDisplayName || mapping.displayName,
    icon: backendIcon || mapping.icon,
    argsTemplate: mapping.argsTemplate,
    resultTemplate: mapping.resultTemplate,
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
