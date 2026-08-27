/**
 * DeerFlow getMessageGroups 算法
 *
 * 参考: frontend/src/core/messages/utils.ts getMessageGroups()
 *
 * 核心逻辑:
 * 1. 过滤 hide_from_ui 消息
 * 2. human → 新建 HumanMessageGroup
 * 3. tool → 合并入上一个 open processing group
 *    - clarification tool → 合入 + 新建 clarification group
 * 4. ai → 根据内容判断:
 *    - hasPresentFiles → present-files group
 *    - hasSubagent → subagent group
 *    - hasReasoning/hasToolCalls → processing group（合并连续的）
 *    - hasContent + !hasToolCalls → assistant group（正文气泡）
 */

import type {
  MessageGroup,
  AssistantPresentFilesGroup,
  AssistantSubagentGroup,
  AssistantClarificationGroup,
  ChatMessage,
  ToolCallSummary,
} from '@/types/ai-chat/message-group'
import { isHiddenFromUIMessage } from '@/types/ai-chat/message-group'
import {
  hasReasoning,
  hasContent,
  extractContentFromMessage,
} from './reasoning-filter'

/**
 * 检查是否有工具调用
 */
export function hasToolCalls(message: ChatMessage): boolean {
  return message.type === 'ai' && (message.tool_calls?.length ?? 0) > 0
}

/**
 * 检查是否为 present_files 工具
 */
export function hasPresentFiles(message: ChatMessage): boolean {
  return message.type === 'ai' && (message.tool_calls?.some(tc => tc.name === 'present_files') ?? false)
}

/**
 * 检查是否为 subagent (task tool)
 */
export function hasSubagent(message: ChatMessage): boolean {
  return (
    message.type === 'ai' &&
    (message.tool_calls?.some(tc => tc.name === 'task') || message.subagent !== undefined)
  )
}

/**
 * 检查是否为 clarification tool message
 */
export function isClarificationToolMessage(message: ChatMessage): boolean {
  return message.type === 'tool' && message.name === 'ask_clarification'
}

/**
 * 从消息提取工具调用列表
 */
export function extractToolCalls(message: ChatMessage): ToolCallSummary[] {
  if (message.type !== 'ai' || !message.tool_calls) {
    return []
  }

  return message.tool_calls.map(tc => ({
    id: tc.id,
    name: tc.name,
    displayName: tc.displayName || tc.name,
    displayKey: tc.displayKey,
    args: tc.args,
    result: tc.result,
    status: tc.status || 'pending',
    elapsedMs: tc.elapsedMs,
  }))
}

/**
 * 查找 tool call 的结果
 *
 * @param toolCallId - 工具调用 ID
 * @param messages - 消息列表（需包含 tool messages）
 * @returns 结果字符串或 undefined
 */
export function findToolCallResult(toolCallId: string, messages: ChatMessage[]): string | undefined {
  for (const message of messages) {
    if (message.type === 'tool' && message.tool_call_id === toolCallId) {
      return message.content
    }
  }
  return undefined
}

/**
 * DeerFlow getMessageGroups 算法实现
 *
 * 将扁平消息列表转换为 DeerFlow 6-type 分组结构
 *
 * @param messages - 扁平消息列表
 * @returns MessageGroup 分组列表
 */
export function getMessageGroups(messages: ChatMessage[]): MessageGroup[] {
  if (messages.length === 0) return []

  const groups: MessageGroup[] = []
  // Track AI message IDs whose reasoning was already shown in a processing
  // group. When the same message also creates an assistant group (content only),
  // strip reasoning from the copy to prevent duplicate "思考" boxes — the
  // processing group's ChainOfThought already renders the reasoning toggle.
  const reasoningShownInProcessing = new Set<string>()

  /**
   * Return a shallow copy of `message` with all reasoning sources stripped.
   *
   * `extractContentAndReasoning` (MessageGroup.vue) checks three sources in
   * priority order: additional_kwargs.reasoning_content, content-array thinking
   * blocks, and string-content think tags. Clearing all three ensures the
   * assistant group's AssistantMessage won't re-render the reasoning that the
   * processing group's ChainOfThought already displayed.
   */
  function stripReasoningFromMessage(msg: ChatMessage): ChatMessage {
    const next: ChatMessage = { ...msg }
    // Strip reasoning from additional_kwargs (priority-1 source for extractContentAndReasoning)
    if (next.additional_kwargs) {
      const { reasoning_content, reasoningStartTime, reasoningEndTime, reasoning_elapsed_ms, ...rest } = next.additional_kwargs
      void reasoning_content; void reasoningStartTime; void reasoningEndTime; void reasoning_elapsed_ms
      next.additional_kwargs = rest
    }
    // Strip think tags from string content (priority-3 source for extractContentAndReasoning)
    if (typeof next.content === 'string') {
      next.content = next.content
        .replace(/<think>[\s\S]*?<\/think>/g, '')
        .replace(/halle_think_start[\s\S]*?halle_think_end/g, '')
        .trim()
    }
    return next
  }

  /**
   * 返回最后一个可接收 tool message 的 group
   * (即非 human/assistant/clarification 的 processing group)
   */
  function lastOpenGroup(): MessageGroup | null {
    const last = groups[groups.length - 1]
    if (
      last &&
      last.type !== 'human' &&
      last.type !== 'assistant' &&
      last.type !== 'assistant:clarification'
    ) {
      return last
    }
    return null
  }

  for (const message of messages) {
    // Step 1: 过滤隐藏消息
    if (isHiddenFromUIMessage(message)) continue

    // Step 2: human → 新建 group
    if (message.type === 'human' || message.role === 'user') {
      groups.push({
        type: 'human',
        id: message.id,
        messages: [message],
      })
      continue
    }

    // Step 3: tool message 处理
    if (message.type === 'tool') {
      if (isClarificationToolMessage(message)) {
        // 合入前一个 processing group（保持 tool-call 关联）
        const open = lastOpenGroup()
        if (open) {
          open.messages.push(message)
        }
        // 同时新建 clarification group 用于醒目展示
        // 从 additional_kwargs.interruptData 提取结构化数据供 HumanInputCard 使用
        const interruptData = message.additional_kwargs?.interruptData as AssistantClarificationGroup['interruptData']
        groups.push({
          type: 'assistant:clarification',
          id: message.id,
          messages: [message],
          ...(interruptData ? { interruptData } : {}),
        })
      } else {
        // 普通 tool → 合入前一个 processing group
        const open = lastOpenGroup()
        if (open) {
          open.messages.push(message)
        } else {
          // 异常：tool message 没有前序 processing group
          // 创建一个新的 processing group
          groups.push({
            type: 'assistant:processing',
            id: message.id,
            messages: [message],
          })
        }
      }
      continue
    }

    // Step 4: ai message 处理
    if (message.type === 'ai' || message.role === 'assistant') {
      // 4a: present_files → 独立 group
      if (hasPresentFiles(message)) {
        // When present_files is bundled with other tool calls (e.g. write_file),
        // create a filtered copy for the present-files group to avoid duplicating
        // the write_file step in ChainOfThought. Also strip reasoning to prevent
        // the "思考" section from appearing in both groups.
        const nonPresentFilesToolCalls = message.tool_calls?.filter(
          tc => tc.name !== 'present_files',
        )
        const hasOtherToolCalls = (nonPresentFilesToolCalls?.length ?? 0) > 0

        if (hasOtherToolCalls) {
          // present_files bundled with other tool calls: create a filtered copy
          // for the present-files group (strip reasoning + present_files from
          // tool_calls) so ChainOfThought only renders the non-present-files steps.
          const presentFilesCopy: ChatMessage = {
            ...stripReasoningFromMessage(message),
            tool_calls: [
              ...message.tool_calls!.filter(tc => tc.name === 'present_files'),
            ],
          }
          groups.push({
            type: 'assistant:present-files',
            id: message.id,
            messages: [presentFilesCopy],
          })

          // Processing group gets the full message so ChainOfThought renders
          // the write_file step + reasoning. present_files is filtered out to
          // avoid a redundant step card (the report card renders separately via
          // the present-files group's ArtifactFileList).
          const processingCopy: ChatMessage = {
            ...message,
            tool_calls: nonPresentFilesToolCalls,
          }
          const lastGroup = groups[groups.length - 1]
          if (lastGroup?.type !== 'assistant:processing') {
            groups.push({
              type: 'assistant:processing',
              id: message.id,
              messages: [processingCopy],
            })
          } else {
            lastGroup.messages.push(processingCopy)
          }
          if (hasReasoning(message) && message.id) {
            reasoningShownInProcessing.add(message.id)
          }
        } else {
          // present_files only — no other tool calls
          groups.push({
            type: 'assistant:present-files',
            id: message.id,
            messages: [message],
          })
        }
      }
      // 4b: subagent (task tool) → 独立 group
      else if (hasSubagent(message)) {
        groups.push({
          type: 'assistant:subagent',
          id: message.id,
          messages: [message],
        })
      }
      // 4c: reasoning 或 tool_calls → processing group
      else if (hasReasoning(message) || hasToolCalls(message)) {
        const lastGroup = groups[groups.length - 1]
        // 合并连续的 processing messages
        if (lastGroup?.type !== 'assistant:processing') {
          groups.push({
            type: 'assistant:processing',
            id: message.id,
            messages: [message],
          })
        } else {
          lastGroup.messages.push(message)
        }
        // Track: this AI message's reasoning will be shown by ChainOfThought
        if (hasReasoning(message) && message.id) {
          reasoningShownInProcessing.add(message.id)
        }
      }

      // 4d: 有正文内容 -> assistant group（正文气泡）
      // 注意：不是 else-if，一个 message 可能同时进入 processing + assistant
      // （有 reasoning/tool_calls + content 的情况）。tool_calls 的可视化在
      // processing group (ChainOfThought) 渲染。
      //
      // 当 AI 消息同时携带 tool_calls 与 content 时（如”让我为您查询家庭资产
      // 负债的最新情况”+ get_assets），content 是工具调用前的过渡说明文本，
      // 不是最终回答。若为它单独创建 assistant 气泡，会显示为”下一轮对话”，
      // 破坏当前轮次的视觉连贯性（DeerFlow 将过渡文本归入 ChainOfThought 块）。
      // 因此：有 tool_calls 时不创建 assistant 气泡，过渡文本由 ChainOfThought
      // 的 leadingContent 渲染为处理块的一部分。
      // ask_clarification 的澄清正文由 tool 结果消息进入 assistant:clarification
      // group 展示，不依赖此处。
      if (hasContent(message) && !hasToolCalls(message)) {
        // DeerFlow 模式：当 todos 已完成时，跳过冗余的完成总结消息。
        // Numina agent 在 write_todos 完成后会生成一条额外的 AI 总结消息
        // （如”已完成！所有 5 个待办事项均已标记为完成。”），但 DeerFlow
        // 不显示这种冗余消息——todo 列表本身就是最终输出。
        //
        // 检测条件：
        // 1. 前一个 group 是 assistant:processing
        // 2. 该 processing group 包含 write_todos 工具调用
        // 3. 当前消息内容很短（< 100 字符）且包含完成类关键词
        const lastGroup = groups[groups.length - 1]
        if (lastGroup?.type === 'assistant:processing') {
          const hasWriteTodos = lastGroup.messages.some(
            m => m.type === 'ai' && m.tool_calls?.some(tc => tc.name === 'write_todos'),
          )

          if (hasWriteTodos) {
            const content = extractContentFromMessage(message)
            const isShortCompletion = content.length > 0 && content.length < 100 &&
              (content.includes('完成') || content.includes('已完成') ||
               content.includes('标记为完成') || content.includes('全部完成'))

            if (isShortCompletion) {
              // 跳过创建 assistant group，避免冗余的完成总结
              continue
            }
          }
        }

        groups.push({
          type: 'assistant',
          id: message.id,
          // If this message's reasoning was already shown in a preceding
          // processing group (ChainOfThought), strip reasoning from the copy
          // so AssistantMessage doesn't re-render a duplicate "思考" toggle.
          messages: [
            message.id && reasoningShownInProcessing.has(message.id)
              ? stripReasoningFromMessage(message)
              : message,
          ],
        })
      }
    }
  }

  return groups
}

/**
 * 从 present-files group 提取文件列表
 */
export function extractPresentFilesFromGroup(group: AssistantPresentFilesGroup): ChatMessage['artifacts'] {
  const message = group.messages[0]
  if (!message) return []

  // 从 tool_calls 提取 present_files 的参数
  const presentFilesCall = message.tool_calls?.find(tc => tc.name === 'present_files')
  if (presentFilesCall?.args) {
    // Guard JSON.parse: malformed args (truncated SSE, partial stream) must not
    // crash the Vue render. Fall through to the artifacts fallback below.
    let args: Record<string, unknown> | null
    try {
      args = typeof presentFilesCall.args === 'string'
        ? JSON.parse(presentFilesCall.args) as Record<string, unknown>
        : presentFilesCall.args as Record<string, unknown>
    } catch {
      args = null
    }
    if (args) {
      // DeerFlow present_files tool uses "filepaths" (string[])
      if (Array.isArray(args.filepaths)) {
        return args.filepaths.map((fp: string) => ({
          path: fp,
          id: fp,
          title: fp,
          kind: 'report' as const,
        }))
      }
      // Legacy / alternate shape: "files" (Artifact[])
      if (Array.isArray(args.files)) {
        return args.files as ChatMessage['artifacts']
      }
    }
  }

  // fallback: 从 artifacts 提取
  return message.artifacts || []
}

/**
 * 从 subagent group 提取子任务数量
 */
export function getSubagentCount(group: AssistantSubagentGroup): number {
  return group.messages.filter(m => m.subagent || m.tool_calls?.some(tc => tc.name === 'task')).length
}

/**
 * 从 subagent group 提取任务 ID 列表
 */
export function getSubagentTaskIds(group: AssistantSubagentGroup): string[] {
  const taskIds: string[] = []

  for (const message of group.messages) {
    // 从 subagent 字段提取
    if (message.subagent?.taskId) {
      taskIds.push(message.subagent.taskId)
    }
    // 从 task tool_calls 提取
    for (const tc of message.tool_calls || []) {
      if (tc.name === 'task' && tc.id) {
        taskIds.push(tc.id)
      }
    }
  }

  return taskIds
}