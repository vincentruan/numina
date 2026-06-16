/**
 * DeerFlow Message Adapter
 *
 * 将 AIChatPage.vue 的 Message 类型转换为 DeerFlow ChatMessage 类型
 * 以便使用 getMessageGroups() 分组算法
 */

import type { ChatMessage, ToolCallSummary } from '@/types/ai-chat/message-group'

/**
 * AIChatPage.vue 内部 Message 类型定义（简化版）
 *
 * 完整定义在 AIChatPage.vue 第 475-505 行
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

export interface ProcessStep {
  type: 'reasoning' | 'tool_call' | 'subagent' | 'artifact' | 'progress'
  id: string
  content?: string
  name?: string
  displayName?: string
  icon?: string
  toolType?: string
  args?: Record<string, unknown>
  status?: 'pending' | 'running' | 'streaming' | 'done' | 'error'
  resultSummary?: string
  error?: string
  elapsedMs?: number
  progressMessage?: string
  // Subagent fields
  taskId?: string
  title?: string
  description?: string
  result?: string
}

export interface PlanStep {
  id: string
  label: string
  status: 'running' | 'done' | 'error'
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
    .map(step => ({
      id: step.id,
      name: step.name || 'unknown',
      displayName: step.displayName || step.name || 'unknown',
      args: step.args,
      result: step.resultSummary,
      status: step.status === 'done' ? 'success'
        : step.status === 'error' ? 'error'
        : 'pending',
      elapsedMs: step.elapsedMs,
    }))
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
        // 创建 tool result message
        result.push({
          id: `tool-result-${toolCall.id}`,
          type: 'tool',
          role: 'assistant', // tool messages technically have assistant role
          content: toolCall.resultSummary || '',
          tool_call_id: toolCall.id,
          name: toolCall.name || 'unknown',
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
export function extractLegacyFields(chatMsg: ChatMessage): LegacyMessage['_legacy'] | undefined {
  return chatMsg.additional_kwargs?.['_legacy'] as LegacyMessage['_legacy'] | undefined
}