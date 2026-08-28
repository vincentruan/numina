/**
 * DeerFlow getMessageGroups 算法
 *
 * 参考: frontend/src/core/messages/utils.ts getMessageGroups()
 *
 * 核心逻辑 (DeerFlow pattern — 互斥路由):
 * 1. 过滤 hide_from_ui 消息
 * 2. human → 新建 HumanMessageGroup
 * 3. tool → 合并入上一个 open processing group
 *    - clarification tool → 合入 + 新建 clarification group
 * 4. ai → 互斥路由（一条消息只进一个主组，从根源消除"思考"重复）:
 *    - hasPresentFiles → present-files group (+ processing if bundled)
 *    - hasSubagent → subagent group
 *    - becomesAssistantBubble → assistant group（DeerFlow #3868:
 *      reasoning 由 AssistantMessage 的 <Reasoning> 折叠框渲染，
 *      不再进入 processing 避免重复）
 *    - hasReasoning || hasToolCalls || isUnresolved → processing group
 *
 * DeerFlow #3868 修复要点:
 * - 有回答内容且无工具调用的消息成为 assistant 气泡，其 reasoning_content
 *   在气泡内的 <Reasoning> 折叠框中渲染。该消息不得进入 processing group，
 *   否则 ChainOfThought 会在气泡上方再渲染一次相同的推理内容。
 * - 流式中（isCurrentTurnLoading=true），content-only 消息暂时留在
 *   processing group（isUnresolvedAssistantText），避免 provider 后续追加
 *   tool_call 时视觉跳变（DeerFlow #4304）。
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
 * 将扁平消息列表转换为 DeerFlow 6-type 分组结构。
 * 采用互斥路由：一条消息只进入一个主组（processing 或 assistant），
 * 从根源消除"思考"折叠框重复显示的问题（DeerFlow #3868）。
 *
 * @param messages - 扁平消息列表
 * @param options.isCurrentTurnLoading - 当前轮次是否正在流式中（DeerFlow pattern:
 *   流式期间 content-only 消息留在 processing group，避免 tool call 到达时视觉跳变）
 * @returns MessageGroup 分组列表
 */
export function getMessageGroups(
  messages: ChatMessage[],
  { isCurrentTurnLoading = false }: { isCurrentTurnLoading?: boolean } = {},
): MessageGroup[] {
  if (messages.length === 0) return []

  const groups: MessageGroup[] = []

  // 找到当前轮次的起始 human 消息索引（DeerFlow pattern: 用于判断 content-only
  // 消息是否为"unresolved"——流式中 provider 可能后续追加 tool_calls）
  let currentTurnStartIndex = -1
  if (isCurrentTurnLoading) {
    for (let index = messages.length - 1; index >= 0; index--) {
      const message = messages[index]
      if ((message.type === 'human' || message.role === 'user') && !isHiddenFromUIMessage(message)) {
        currentTurnStartIndex = index
        break
      }
    }
  }

  /**
   * Return a shallow copy of `message` with all reasoning sources stripped.
   *
   * 仅用于 present_files 捆绑场景：当 present_files 与其他工具调用同时出现时，
   * present-files group 的副本需要剥离 reasoning，避免与 processing group 的
   * ChainOfThought 重复渲染"思考"折叠框。
   *
   * 主路由不再需要此函数——互斥路由保证 reasoning 只在一个组中渲染。
   */
  function stripReasoningFromMessage(msg: ChatMessage): ChatMessage {
    const next: ChatMessage = { ...msg }
    next.reasoning = null
    if (next.additional_kwargs) {
      const { reasoning_content, reasoningStartTime, reasoningEndTime, reasoning_elapsed_ms, ...rest } = next.additional_kwargs
      void reasoning_content; void reasoningStartTime; void reasoningEndTime; void reasoning_elapsed_ms
      next.additional_kwargs = rest
    }
    const content = next.content as string | unknown[] | null | undefined
    if (Array.isArray(content)) {
      next.content = content.filter(
        part => !(part && typeof part === 'object' && (part as { type?: string }).type === 'thinking')
      ).join('\n') as unknown as string
    } else if (typeof content === 'string') {
      next.content = content
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

  for (const [messageIndex, message] of messages.entries()) {
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
      // DeerFlow #3868: 互斥路由 — 消息要么进 processing，要么进 assistant，不两者兼得。
      //
      // A message with answer content and no tool calls becomes its own
      // assistant bubble below, which already renders the message's
      // reasoning_content inside the bubble's <Reasoning> collapsible. Such a
      // message must NOT also feed the processing group, or the ChainOfThought
      // panel above the bubble paints the identical reasoning a second time
      // (#3868). Intermediate reasoning (no content) and tool-calling steps
      // still belong in the processing group.
      //
      // A content-only message is not necessarily the final answer while its
      // turn is still streaming: providers can append tool-call chunks to the
      // same message later. Keep that unresolved message in the processing
      // group so its visible text does not jump from an assistant bubble into
      // the steps panel when the tool call arrives (#4304).
      const isUnresolvedAssistantText =
        currentTurnStartIndex >= 0 &&
        messageIndex > currentTurnStartIndex &&
        hasContent(message) &&
        !hasToolCalls(message)
      const becomesAssistantBubble =
        hasContent(message) &&
        !hasToolCalls(message) &&
        !isUnresolvedAssistantText

      // 4a: present_files → 独立 group
      if (hasPresentFiles(message)) {
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

          // Processing group gets the non-present_files tool calls + reasoning.
          // present_files is filtered out to avoid a redundant step card.
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
        } else {
          // present_files only — no other tool calls
          groups.push({
            type: 'assistant:present-files',
            id: message.id,
            messages: [message],
          })
        }

        // DeerFlow pattern: present_files 消息由 present-files group 处理，
        // 不参与互斥路由的 processing/assistant 分流。
        // 但如果有回答内容且无其他工具调用，仍需创建 assistant 气泡以展示 reasoning
        // （DeerFlow: becomesAssistantBubble 检查 !hasToolCalls，present_files-only
        // 消息的 hasToolCalls 可能为 true，需额外检查）。
        if (
          becomesAssistantBubble &&
          !(nonPresentFilesToolCalls?.length ?? 0)
        ) {
          groups.push({ id: message.id, type: 'assistant', messages: [message] })
        }
        continue
      }

      // 4b: subagent (task tool) → 独立 group
      if (hasSubagent(message)) {
        groups.push({
          type: 'assistant:subagent',
          id: message.id,
          messages: [message],
        })
        continue
      }

      // 4c: DeerFlow 互斥路由 — processing vs assistant
      // !becomesAssistantBubble 门控防止 reasoning+content 消息同时进入两个组
      if (
        !becomesAssistantBubble &&
        (hasReasoning(message) || hasToolCalls(message) || isUnresolvedAssistantText)
      ) {
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
        continue
      }

      // 4d: becomesAssistantBubble → assistant group（正文气泡）
      // reasoning 由 AssistantMessage 的 <Reasoning> 折叠框渲染，
      // 不进入 processing group，从根源避免重复（DeerFlow #3868）。
      //
      // 当 AI 消息同时携带 tool_calls 与 content 时，content 是工具调用前的
      // 过渡说明文本。若为它单独创建 assistant 气泡，会显示为"下一轮对话"，
      // 破坏当前轮次的视觉连贯性。因此：有 tool_calls 时不创建 assistant 气泡
      // （becomesAssistantBubble 已含 !hasToolCalls 条件）。
      if (becomesAssistantBubble) {
        // DeerFlow 模式：当 todos 已完成时，跳过冗余的完成总结消息。
        // Numina agent 在 write_todos 完成后会生成一条额外的 AI 总结消息
        // （如"已完成！所有 5 个待办事项均已标记为完成。"），但 DeerFlow
        // 不显示这种冗余消息——todo 列表本身就是最终输出。
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
              continue
            }
          }
        }

        groups.push({ id: message.id, type: 'assistant', messages: [message] })
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
