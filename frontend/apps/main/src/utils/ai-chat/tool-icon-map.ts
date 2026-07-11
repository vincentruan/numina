/**
 * DeerFlow 工具图标映射
 *
 * 参考: frontend/src/components/workspace/messages/message-group.tsx ToolCall
 * 参考: frontend/src/core/tools/utils.ts explainLastToolCall()
 */

export const TOOL_ICON_MAP: Record<string, string> = {
  // DeerFlow 内置工具
  'web_search': 'search',
  'web_fetch': 'globe',
  'image_search': 'search',
  'read_file': 'file-text',
  'write_file': 'file-edit',
  'str_replace': 'file-edit',
  'bash': 'terminal',
  'ls': 'folder',
  'ask_clarification': 'help-circle',
  'write_todos': 'list-todo',
  'present_files': 'file',

  // MCP tools (带前缀)
  'mcp://web_search': 'search',
  'mcp://read_file': 'file-text',
  'mcp://write_file': 'file-edit',
  'mcp://bash': 'terminal',

  // Numina domain tools（含实际流式传输的复数/变体名）
  'get_asset': 'coin',
  'get_assets': 'coin',
  'get_liability': 'credit-card',
  'get_liabilities': 'credit-card',
  'get_allocation': 'pie-chart',
  'get_dashboard': 'dashboard',
  'get_dashboard_overview': 'dashboard',
  'get_family_members': 'users',
  'get_members': 'users',
  'get_family_overview': 'dashboard',

  // Subagent (task 由 SubtaskCard 处理)
  'task': 'agent',
  'subagent': 'agent',

  // Default
  'default': 'tool',
}

/**
 * 工具显示名称 i18n key 映射
 *
 * 调用方需使用 t(key) 翻译
 */
export const TOOL_DISPLAY_NAME_KEY_MAP: Record<string, string> = {
  'web_search': 'tool.displayName.web_search',
  'web_fetch': 'tool.displayName.web_fetch',
  'image_search': 'tool.displayName.image_search',
  'read_file': 'tool.displayName.read_file',
  'write_file': 'tool.displayName.write_file',
  'str_replace': 'tool.displayName.str_replace',
  'bash': 'tool.displayName.bash',
  'ls': 'tool.displayName.ls',
  'ask_clarification': 'tool.displayName.ask_clarification',
  'write_todos': 'tool.displayName.write_todos',
  'present_files': 'tool.displayName.present_files',
  'task': 'tool.displayName.task',
  'get_asset': 'tool.displayName.get_asset',
  'get_assets': 'tool.displayName.get_asset',
  'get_liability': 'tool.displayName.get_liability',
  'get_liabilities': 'tool.displayName.get_liability',
  'get_allocation': 'tool.displayName.get_allocation',
  'get_dashboard': 'tool.displayName.get_dashboard',
  'get_dashboard_overview': 'tool.displayName.get_dashboard',
  'get_family_members': 'tool.displayName.get_family_members',
  'get_members': 'tool.displayName.get_family_members',
  'get_family_overview': 'tool.displayName.get_dashboard',
}

/**
 * 从工具名中提取短名（用于匹配已知工具）。
 *
 * 处理三种格式：
 * 1. `mcp://tool_name` / `skill://tool_name` / `builtin://tool_name` (协议前缀)
 * 2. `Server Name_tool_name` (LangChain MCP adapter 格式，server_name 可含空格)
 * 3. 纯工具名 `tool_name`
 *
 * 对于格式2：server_name 含空格（如 "Numina Backend MCP"），分隔符是最后一个
 * 空格之后的第一个下划线。tool_name 本身可能含下划线（如 get_family_overview），
 * 所以不能用 lastIndexOf('_')。
 */
export function extractShortToolName(toolName: string): string {
  if (!toolName) return ''
  const stripped = toolName.replace(/^(mcp|skill|builtin):\/\//, '')
  // MCP "{Server Name}_{tool}" 格式：找最后一个空格之后的第一个下划线
  const lastSpaceIdx = stripped.lastIndexOf(' ')
  if (lastSpaceIdx >= 0) {
    const afterSpace = stripped.slice(lastSpaceIdx + 1)
    // afterSpace 形如 "MCP_get_family_overview"，取第一个 "_" 之后的部分
    const firstUnderscoreIdx = afterSpace.indexOf('_')
    if (firstUnderscoreIdx > 0 && firstUnderscoreIdx < afterSpace.length - 1) {
      return afterSpace.slice(firstUnderscoreIdx + 1)
    }
    // 无下划线则返回 afterSpace 本身
    return afterSpace
  }
  return stripped
}

/**
 * 获取工具图标
 *
 * @param toolName - 工具名称（可能带 mcp://, skill://, builtin:// 前缀，或 MCP Server Name 前缀）
 * @returns 图标名称
 */
export function getToolIcon(toolName: string): string {
  const normalized = toolName.replace(/^(mcp|skill|builtin):\/\//, '')
  if (TOOL_ICON_MAP[normalized]) return TOOL_ICON_MAP[normalized]
  // MCP "{Server Name}_{tool}" 格式：用短名匹配
  const shortName = extractShortToolName(toolName)
  if (shortName !== normalized && TOOL_ICON_MAP[shortName]) {
    return TOOL_ICON_MAP[shortName]
  }
  return TOOL_ICON_MAP['default']
}

/**
 * 获取工具显示名称的 i18n key
 *
 * @param toolName - 工具名称
 * @returns i18n key（调用方需使用 t(key) 翻译）
 */
export function getToolDisplayNameKey(toolName: string): string {
  const normalized = toolName.replace(/^(mcp|skill|builtin):\/\//, '')
  if (TOOL_DISPLAY_NAME_KEY_MAP[normalized]) return TOOL_DISPLAY_NAME_KEY_MAP[normalized]
  // MCP "{Server Name}_{tool}" 格式：用短名匹配
  const shortName = extractShortToolName(toolName)
  if (shortName !== normalized && TOOL_DISPLAY_NAME_KEY_MAP[shortName]) {
    return TOOL_DISPLAY_NAME_KEY_MAP[shortName]
  }
  return `tool.displayName.${shortName}`
}

/**
 * 工具动作说明 i18n key 映射
 *
 * 返回 { key, params } 对象，调用方需使用 t(key, params) 翻译
 */
export const TOOL_ACTION_KEY_MAP: Record<string, (args?: Record<string, unknown>) => { key: string; params?: Record<string, string> }> = {
  'web_search': (args) => {
    const query = args?.query as string | undefined
    return query
      ? { key: 'tool.action.web_search_with_query', params: { query: query.slice(0, 20) } }
      : { key: 'tool.action.web_search' }
  },
  'web_fetch': (args) => {
    const url = args?.url as string | undefined
    return url
      ? { key: 'tool.action.web_fetch_with_url', params: { url: url.slice(0, 30) } }
      : { key: 'tool.action.web_fetch' }
  },
  'image_search': () => ({ key: 'tool.action.image_search' }),
  'read_file': (args) => {
    const path = (args?.file_path as string | undefined) || (args?.path as string | undefined)
    return path
      ? { key: 'tool.action.read_file_with_path', params: { path } }
      : { key: 'tool.action.read_file' }
  },
  'write_file': (args) => {
    const path = (args?.file_path as string | undefined) || (args?.path as string | undefined)
    return path
      ? { key: 'tool.action.write_file_with_path', params: { path } }
      : { key: 'tool.action.write_file' }
  },
  'str_replace': (args) => {
    const path = (args?.file_path as string | undefined) || (args?.path as string | undefined)
    return path
      ? { key: 'tool.action.write_file_with_path', params: { path } }
      : { key: 'tool.action.write_file' }
  },
  'bash': (args) => {
    const command = args?.command as string | undefined
    return command
      ? { key: 'tool.action.bash_with_command', params: { command: command.slice(0, 30) } }
      : { key: 'tool.action.bash' }
  },
  'task': (args) => {
    const description = args?.description as string | undefined
    return description
      ? { key: 'tool.action.task_with_desc', params: { description: description.slice(0, 30) } }
      : { key: 'tool.action.task' }
  },
  'present_files': () => ({ key: 'tool.action.present_files' }),
  'ask_clarification': () => ({ key: 'tool.action.ask_clarification' }),
  // Numina 域工具 - 行动描述（参考 server message_classifier.py display_name）
  'get_asset': () => ({ key: 'tool.action.get_asset' }),
  'get_assets': () => ({ key: 'tool.action.get_asset' }),
  'get_liability': () => ({ key: 'tool.action.get_liability' }),
  'get_liabilities': () => ({ key: 'tool.action.get_liability' }),
  'get_allocation': () => ({ key: 'tool.action.get_allocation' }),
  'get_dashboard': () => ({ key: 'tool.action.get_dashboard' }),
  'get_dashboard_overview': () => ({ key: 'tool.action.get_dashboard' }),
  'get_family_members': () => ({ key: 'tool.action.get_family_members' }),
  'get_members': () => ({ key: 'tool.action.get_family_members' }),
  'get_family_overview': () => ({ key: 'tool.action.get_family_overview' }),
  // MCP namespaced variants（旧格式，保留兼容）
  'numina-family-data_get_assets': () => ({ key: 'tool.action.get_asset' }),
  'numina-family-data_get_liabilities': () => ({ key: 'tool.action.get_liability' }),
  'numina-family-data_get_members': () => ({ key: 'tool.action.get_family_members' }),
  'numina-family-data_get_family_overview': () => ({ key: 'tool.action.get_family_overview' }),
}

/**
 * 生成工具调用说明的 i18n key 和参数
 *
 * 参考 DeerFlow explainLastToolCall()
 *
 * @param toolName - 工具名称
 * @param args - 工具参数
 * @returns { key, params } 对象（调用方需使用 t(key, params) 翻译）
 */
export function explainToolCallKey(
  toolName: string,
  args?: Record<string, unknown>,
): { key: string; params?: Record<string, string> } {
  // 空名兜底：后端有时发出 name="" 的 tool_call（genId('tc') 占位条目）
  if (!toolName) {
    return { key: 'tool.action.unknown' }
  }

  const normalized = toolName.replace(/^(mcp|skill|builtin):\/\//, '')

  // 使用动作模板生成说明（精确匹配）
  const template = TOOL_ACTION_KEY_MAP[normalized]
  if (template) {
    return template(args)
  }

  // MCP 工具命名格式："{Server Name}_{tool_name}"（如 "Numina Backend MCP_get_assets"）
  // 用 extractShortToolName 提取短名后再尝试匹配
  const shortName = extractShortToolName(toolName)
  if (shortName !== normalized) {
    const shortTemplate = TOOL_ACTION_KEY_MAP[shortName]
    if (shortTemplate) {
      return shortTemplate(args)
    }
  }

  // MCP 工具通用说明
  if (toolName.startsWith('mcp://')) {
    return { key: 'tool.action.mcp_generic', params: { name: normalized } }
  }

  // Skill 工具通用说明
  if (toolName.startsWith('skill://')) {
    return { key: 'tool.action.skill_generic', params: { name: normalized } }
  }

  // 含下划线的 MCP 命名（如 "Numina Backend MCP_get_xxx"）按 MCP 通用处理
  if (shortName !== normalized) {
    return { key: 'tool.action.mcp_generic', params: { name: shortName } }
  }

  // 通用 fallback
  return { key: 'tool.action.generic', params: { name: normalized } }
}