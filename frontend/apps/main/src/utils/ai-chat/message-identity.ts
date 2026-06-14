/**
 * DeerFlow 消息去重 Identity 函数
 *
 * 参考: frontend/src/core/messages/utils.ts messageIdentity()
 *
 * Identity 规则:
 * - tool message: 使用 tool_call_id
 * - assistant message: 使用 message.id
 * - user message: 使用 message.id + content hash (防止重复发送)
 */

import type { ChatMessage } from '@/types/ai-chat/message-group'

/**
 * 简单内容 hash（用于用户消息去重）
 *
 * 不需要加密安全，只需要快速区分不同内容
 */
function hashContent(content: string): string {
  // 使用前 50 字符 + 长度作为简单 hash
  return `${content.slice(0, 50)}:${content.length}`
}

/**
 * 消息唯一标识
 *
 * 用于 Set 去重和 key 生成
 *
 * @param msg - 消息对象
 * @returns 唯一标识字符串
 */
export function messageIdentity(msg: ChatMessage): string {
  // tool message: 使用 tool_call_id
  if (msg.type === 'tool' && msg.tool_call_id) {
    return `tool:${msg.tool_call_id}`
  }

  // user message: 使用 id + content hash
  if (msg.type === 'human' || msg.role === 'user') {
    const id = msg.id || 'unknown'
    const hash = hashContent(msg.content || '')
    return `user:${id}:${hash}`
  }

  // assistant message: 使用 message.id
  if (msg.type === 'ai' || msg.role === 'assistant') {
    return `assistant:${msg.id || 'unknown'}`
  }

  // fallback
  return `msg:${msg.id || 'unknown'}`
}

/**
 * 创建去重 Set
 *
 * @returns Set 实例
 */
export function createMessageIdentitySet(): Set<string> {
  return new Set<string>()
}

/**
 * 检查消息是否已存在
 *
 * @param seen - 已存在的 identity Set
 * @param msg - 待检查消息
 * @returns 是否已存在
 */
export function isMessageSeen(seen: Set<string>, msg: ChatMessage): boolean {
  const identity = messageIdentity(msg)
  return seen.has(identity)
}

/**
 * 标记消息已存在
 *
 * @param seen - identity Set
 * @param msg - 消息对象
 */
export function markMessageSeen(seen: Set<string>, msg: ChatMessage): void {
  const identity = messageIdentity(msg)
  seen.add(identity)
}

/**
 * 过滤重复消息
 *
 * @param messages - 消息列表
 * @returns 去重后的消息列表
 */
export function deduplicateMessages(messages: ChatMessage[]): ChatMessage[] {
  const seen = createMessageIdentitySet()
  return messages.filter((msg) => {
    const identity = messageIdentity(msg)
    if (seen.has(identity)) {
      return false
    }
    seen.add(identity)
    return true
  })
}