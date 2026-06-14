/**
 * DeerFlow useMessageGroups Composable
 *
 * Vue reactive wrapper for getMessageGroups algorithm
 *
 * 参考: frontend/src/core/messages/utils.ts
 */

import { computed, type Ref, type ComputedRef } from 'vue'
import { getMessageGroups } from '@/utils/ai-chat/messageGroups'
import { deduplicateMessages } from '@/utils/ai-chat/message-identity'
import type { MessageGroup, ChatMessage } from '@/types/ai-chat/message-group'

/**
 * 消息分组 Composable
 *
 * 将扁平消息列表转换为 DeerFlow 6-type 分组结构
 * 自动去重 + 分组
 *
 * @param messages - 消息列表 ref
 * @returns 分组后的消息列表 computed ref
 */
export function useMessageGroups(messages: Ref<ChatMessage[]>): ComputedRef<MessageGroup[]> {
  return computed(() => {
    // 先去重
    const deduped = deduplicateMessages(messages.value)
    // 再分组
    return getMessageGroups(deduped)
  })
}

/**
 * 获取当前处理中的消息组
 *
 * 用于高亮正在处理的消息
 *
 * @param groups - 消息分组列表
 * @param isLoading - 是否正在加载
 * @returns 当前处理中的分组或 null
 */
export function getCurrentProcessingGroup(
  groups: MessageGroup[],
  isLoading: boolean,
): MessageGroup | null {
  if (!isLoading) return null

  // 找到最后一个 processing group
  for (let i = groups.length - 1; i >= 0; i--) {
    if (groups[i].type === 'assistant:processing') {
      return groups[i]
    }
  }

  return null
}

/**
 * 统计消息数量
 *
 * @param groups - 消息分组列表
 * @returns 统计信息
 */
export function getMessageStats(groups: MessageGroup[]): {
  humanCount: number
  assistantCount: number
  toolCount: number
  total: number
} {
  let humanCount = 0
  let assistantCount = 0
  let toolCount = 0

  for (const group of groups) {
    if (group.type === 'human') {
      humanCount++
    } else if (group.type === 'assistant') {
      assistantCount++
    } else if (group.type.startsWith('assistant:')) {
      // 子分组也计入 assistant
      assistantCount++
      // tool 消息统计
      toolCount += group.messages.filter(m => m.type === 'tool').length
    }
  }

  return {
    humanCount,
    assistantCount,
    toolCount,
    total: humanCount + assistantCount,
  }
}