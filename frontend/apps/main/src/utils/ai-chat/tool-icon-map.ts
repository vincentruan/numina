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

  // Numina domain tools
  'get_asset': 'coin',
  'get_liability': 'credit-card',
  'get_allocation': 'pie-chart',
  'get_dashboard': 'dashboard',
  'get_family_members': 'users',

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
  'get_liability': 'tool.displayName.get_liability',
  'get_allocation': 'tool.displayName.get_allocation',
  'get_dashboard': 'tool.displayName.get_dashboard',
  'get_family_members': 'tool.displayName.get_family_members',
}

/**
 * 获取工具图标
 *
 * @param toolName - 工具名称（可能带 mcp://, skill://, builtin:// 前缀）
 * @returns 图标名称
 */
export function getToolIcon(toolName: string): string {
  // 处理 tool_type 前缀 (mcp://, skill://, builtin://)
  const normalized = toolName.replace(/^(mcp|skill|builtin):\/\//, '')
  return TOOL_ICON_MAP[normalized] || TOOL_ICON_MAP['default']
}

/**
 * 获取工具显示名称的 i18n key
 *
 * @param toolName - 工具名称
 * @returns i18n key（调用方需使用 t(key) 翻译）
 */
export function getToolDisplayNameKey(toolName: string): string {
  const normalized = toolName.replace(/^(mcp|skill|builtin):\/\//, '')
  return TOOL_DISPLAY_NAME_KEY_MAP[normalized] || `tool.displayName.${normalized}`
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
}

/**
 * 生成工具调用说明的 i18n key 和参数
 *
 * 参考 DeerFlow explainLastToolCall()
 *
 * @param toolName - 工具名称
 * @param args - 工具参数
 * @param result - 工具结果（可选，用于判断是否完成）
 * @returns { key, params } 对象（调用方需使用 t(key, params) 翻译）
 */
export function explainToolCallKey(
  toolName: string,
  args?: Record<string, unknown>,
  result?: unknown,
): { key: string; params?: Record<string, string> } {
  const normalized = toolName.replace(/^(mcp|skill|builtin):\/\//, '')

  // 有结果时，返回完成说明
  if (result !== undefined) {
    const displayNameKey = getToolDisplayNameKey(normalized)
    // 返回复合 key，调用方需拼接：t(displayNameKey) + t('tool.action.completed_suffix')
    return { key: displayNameKey, params: { suffix: ' ✓' } }
  }

  // 使用动作模板生成说明
  const template = TOOL_ACTION_KEY_MAP[normalized]
  if (template) {
    return template(args)
  }

  // MCP 工具通用说明
  if (toolName.startsWith('mcp://')) {
    return { key: 'tool.action.mcp_generic', params: { name: normalized } }
  }

  // Skill 通用说明
  if (toolName.startsWith('skill://')) {
    return { key: 'tool.action.skill_generic', params: { name: normalized } }
  }

  // 通用 fallback
  return { key: 'tool.action.generic', params: { name: normalized } }
}