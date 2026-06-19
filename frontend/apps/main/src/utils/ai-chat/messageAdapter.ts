/**
 * DeerFlow Message Adapter
 *
 * 将 ChatMessage 类型转换为 DeerFlow ChatMessage 类型
 * 以便使用 getMessageGroups() 分组算法
 */

import type { ChatMessage, ToolCallSummary } from '@/types/ai-chat/message-group'
import type { ProcessStep, PlanStep } from '@/types/agent-stream'

// Re-export types from agent-stream for backward compatibility
export type { ProcessStep, PlanStep }

/**
 * Message 类型定义（简化版）
 */
export interface LegacyMessage {
  id: string
  role: 'user' | 'assistant'
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  sendStatus?: 'sending' | 'sent' | 'failed'
  content: string
  renderedContent?: string
  created_at: string
  displayTime: string
  feedback?: 1 | -1 | 0
  // Deep think fields
  thinkContent?: string
  thinkOpen?: boolean
  thinkDone?: boolean
  thinkSeconds?: number
  reasoningStartTime?: number | null
  thinkManuallyToggled?: boolean
  toolTimeline?: ToolTimelineItem[]
  // Process steps
  processStatus?: 'running' | 'done' | 'error' | 'interrupted'
  processElapsedMs?: number
  processSteps?: ProcessStep[]
  // Plan progress
  planSteps?: PlanStep[]
  planSource?: 'explicit' | 'inferred' | null
  // Process expanded toggle
  processExpanded?: boolean
  // Follow-up suggestions
  suggestions?: string[]
}

export interface ToolTimelineItem {
  id: string
  name: string
  displayName: string
  icon: string
  argumentsText: string
  result?: {
    success?: boolean
    summary?: string
    data?: unknown
    error?: string
    execution_time_ms?: number
  }
}

/**
 * 将 Legacy Message 的 toolTimeline 转换为 DeerFlow ToolCallSummary
 */
function mapToolTimelineToToolCalls(msg: LegacyMessage): ToolCallSummary[] {
  if (!msg.toolTimeline) return []

  return msg.toolTimeline.map(tool => ({
    id: tool.id,
    name: tool.name,
    displayName: tool.displayName || tool.name,
    args: parseToolArgs(tool.argumentsText),
    result: tool.result?.data,
    status: tool.result
      ? (tool.result.success ? 'success' : 'error')
      : 'pending',
    elapsedMs: tool.result?.execution_time_ms,
  }))
}

/**
 * 将 Legacy Message 的 processSteps 转换为 DeerFlow ToolCallSummary
 */
function mapProcessStepsToToolCalls(msg: LegacyMessage): ToolCallSummary[] {
  if (!msg.processSteps) return []

  return msg.processSteps
    .filter(step => step.type === 'tool_call')
    .map(step => {
      // Type assertion after filtering - step is now tool_call type
      const toolStep = step as Extract<ProcessStep, { type: 'tool_call' }>
      return {
        id: toolStep.id,
        name: toolStep.name || 'unknown',
        displayName: toolStep.displayName || toolStep.name || 'unknown',
        args: toolStep.args,
        result: toolStep.resultSummary,
        status: toolStep.status === 'done' ? 'success'
          : toolStep.status === 'error' ? 'error'
          : 'pending',
        elapsedMs: toolStep.elapsedMs,
      }
    })
}

/**
 * 解析工具参数 JSON
 */
function parseToolArgs(argsText?: string): Record<string, unknown> {
  if (!argsText) return {}
  try {
    return JSON.parse(argsText)
  } catch {
    return { text: argsText }
  }
}

/**
 * 将 Legacy Message 转换为 DeerFlow ChatMessage
 *
 * 映射规则:
 * - role: 'user' → type: 'human', role: 'user'
 * - role: 'assistant' → type: 'ai', role: 'assistant'
 * - thinkContent → reasoning
 * - toolTimeline/processSteps → tool_calls
 * - suggestions → suggestions
 */
export function toDeerFlowChatMessage(msg: LegacyMessage): ChatMessage {
  // 提取 tool_calls（优先 processSteps，fallback 到 toolTimeline）
  const toolCalls = msg.processSteps
    ? mapProcessStepsToToolCalls(msg)
    : mapToolTimelineToToolCalls(msg)

  // 提取 reasoning 内容
  const reasoning = msg.thinkContent || null

  // 构建 DeerFlow ChatMessage
  return {
    id: msg.id,
    // DeerFlow type: 'human' | 'ai' | 'tool'
    type: msg.role === 'user' ? 'human' : 'ai',
    // DeerFlow role: 'user' | 'assistant'
    role: msg.role,
    // 正文内容（使用 renderedContent 或原始 content）
    content: msg.renderedContent || msg.content,
    // 推理内容
    reasoning,
    // 工具调用
    tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
    // 显示时间
    displayTime: msg.displayTime,
    // 发送状态（仅 human）
    sendStatus: msg.sendStatus,
    // 消息阶段（仅 AI）
    phase: msg.phase,
    // 建议（仅 AI）
    suggestions: msg.suggestions,
    // 反馈状态
    feedback: msg.feedback,
    // 附加参数
    additional_kwargs: {
      // 保留原始字段供组件使用
      _legacy: {
        created_at: msg.created_at,
        thinkOpen: msg.thinkOpen,
        thinkDone: msg.thinkDone,
        thinkSeconds: msg.thinkSeconds,
        reasoningStartTime: msg.reasoningStartTime,
        thinkManuallyToggled: msg.thinkManuallyToggled,
        processStatus: msg.processStatus,
        processElapsedMs: msg.processElapsedMs,
        processSteps: msg.processSteps,
        planSteps: msg.planSteps,
        planSource: msg.planSource,
        processExpanded: msg.processExpanded,
      },
    },
  }
}

/**
 * 批量转换 Legacy Messages 为 DeerFlow ChatMessages
 *
 * 关键: 对于每个已完成的 tool_call，生成独立的 tool result message
 * 以便 messageGroups.ts 检测 ask_clarification 等 tool result 触发的分组
 */
export function toDeerFlowChatMessages(messages: LegacyMessage[]): ChatMessage[] {
  const result: ChatMessage[] = []

  for (const msg of messages) {
    // 1. 先生成主消息 (human 或 ai)
    const chatMsg = toDeerFlowChatMessage(msg)
    result.push(chatMsg)

    // 2. 如果是 AI 消息且有已完成的 tool_calls，生成独立的 tool result messages
    //    这是 DeerFlow messageGroups 检测 ask_clarification 的关键条件:
    //    message.type === 'tool' && message.name === 'ask_clarification'
    if (msg.role === 'assistant' && msg.processSteps) {
      const completedToolCalls = msg.processSteps.filter(
        step => step.type === 'tool_call' && step.status === 'done'
      )

      for (const toolCall of completedToolCalls) {
        // Type assertion after filtering
        const toolStep = toolCall as Extract<ProcessStep, { type: 'tool_call' }>
        // 创建 tool result message
        result.push({
          id: `tool-result-${toolStep.id}`,
          type: 'tool',
          role: 'assistant', // tool messages technically have assistant role
          content: toolStep.resultSummary || '',
          tool_call_id: toolStep.id,
          name: toolStep.name || 'unknown',
          displayTime: msg.displayTime,
        })
      }
    }
  }

  return result
}

/**
 * 从 DeerFlow ChatMessage 提取原始 Legacy 字段
 *
 * 用于在组件中访问 processSteps 等字段
 */
export function extractLegacyFields(chatMsg: ChatMessage): { processSteps?: ProcessStep[]; planSteps?: PlanStep[]; planSource?: 'explicit' | 'inferred' | null; processElapsedMs?: number; reasoningStartTime?: number | null } | undefined {
  const legacy = chatMsg.additional_kwargs?.['_legacy'] as Record<string, unknown> | undefined
  if (!legacy) return undefined
  return {
    processSteps: legacy.processSteps as ProcessStep[] | undefined,
    planSteps: legacy.planSteps as PlanStep[] | undefined,
    planSource: legacy.planSource as 'explicit' | 'inferred' | null | undefined,
    processElapsedMs: legacy.processElapsedMs as number | undefined,
    reasoningStartTime: legacy.reasoningStartTime as number | null | undefined,
  }
}