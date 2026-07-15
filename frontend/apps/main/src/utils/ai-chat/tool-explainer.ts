/**
 * DeerFlow 工具动作说明辅助函数
 *
 * 参考: frontend/src/core/tools/utils.ts explainLastToolCall()
 *
 * 从 AIMessage 的 tool_calls 中提取最后一个工具调用的说明
 */
import type { ChatMessage } from '@/types/ai-chat/message-group'
import { getToolDisplayNameKey } from './tool-icon-map'

/**
 * 提取最后一个工具调用的说明（返回 i18n key 和参数）
 *
 * 调用方需使用 t(key, params) 翻译
 *
 * @returns { key, params } 或 null
 */
export function explainLastToolCallKey(message: ChatMessage): { key: string; params?: Record<string, string> } | null {
  if (!message.tool_calls?.length) return null

  const lastToolCall = message.tool_calls[message.tool_calls.length - 1]
  const displayNameKey = getToolDisplayNameKey(lastToolCall.name)

  // 特殊处理：显示关键参数
  const args = lastToolCall.args as Record<string, unknown> | undefined

  if (lastToolCall.name === 'read_file' || lastToolCall.name === 'write_file') {
    const path = args?.path as string | undefined
    if (path) {
      return {
        key: `tool.action.${lastToolCall.name}_with_path`,
        params: { path },
      }
    }
  }

  if (lastToolCall.name === 'read_numina_report' || lastToolCall.name === 'write_numina_report') {
    const filename = args?.filename as string | undefined
    if (filename) {
      return {
        key: `tool.action.${lastToolCall.name}_with_filename`,
        params: { filename },
      }
    }
  }

  if (lastToolCall.name === 'bash') {
    const command = args?.command as string | undefined
    if (command) {
      return {
        key: 'tool.action.bash_with_command',
        params: { command: String(command).slice(0, 30) },
      }
    }
  }

  if (lastToolCall.name === 'web_search') {
    const query = args?.query as string | undefined
    if (query) {
      return {
        key: 'tool.action.web_search_with_query',
        params: { query: String(query).slice(0, 20) },
      }
    }
  }

  return { key: displayNameKey }
}