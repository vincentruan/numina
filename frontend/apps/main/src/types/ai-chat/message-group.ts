/**
 * DeerFlow MessageGroup discriminated union types
 *
 * 参考: frontend/src/core/messages/utils.ts
 *
 * DeerFlow 使用 6 种消息组类型来组织对话展示：
 * - human: 用户消息，右对齐气泡
 * - assistant: AI 最终回答，左对齐全宽
 * - assistant:processing: reasoning + tool calls + tool results
 * - assistant:clarification: "需要补充信息" 提示
 * - assistant:present-files: 文本 + artifact 文件列表
 * - assistant:subagent: 子智能体任务卡片
 */

/** 用户消息组 — 右对齐气泡 */
export interface HumanMessageGroup {
  type: 'human'
  id: string | undefined
  messages: ChatMessage[]
}

/** 智能体处理中 — reasoning + tool calls + tool results */
export interface AssistantProcessingGroup {
  type: 'assistant:processing'
  id: string | undefined
  messages: ChatMessage[]
}

/** 智能体最终回答 — markdown 渲染，复制/反馈 */
export interface AssistantMessageGroup {
  type: 'assistant'
  id: string | undefined
  messages: ChatMessage[]
}

/** 智能体展示文件 — 文本 + artifact 文件列表 */
export interface AssistantPresentFilesGroup {
  type: 'assistant:present-files'
  id: string | undefined
  messages: ChatMessage[]
}

/** Clarification request from DeerFlow ask_clarification tool (mirrored from useThreadChat). */
export interface ClarificationInterruptData {
  question: string
  options?: Array<{ id: string; label: string; value: string }>
  context?: string
  /** Derived from ``input_mode === 'choice_with_other'``. */
  choiceWithOther?: boolean
  input_mode?: 'free_text' | 'single_choice' | 'choice_with_other'
  /** DeerFlow ``request_id`` - used to match ``human_input_response``. */
  interrupt_id: string
  source?: string
}

/** 智能体请求补充信息 — "需要补充信息" 提示 */
export interface AssistantClarificationGroup {
  type: 'assistant:clarification'
  id: string | undefined
  messages: ChatMessage[]
  interruptData?: ClarificationInterruptData
  phase?: 'pending' | 'answered'
  answer?: string
}

/** 子智能体任务卡片 */
export interface AssistantSubagentGroup {
  type: 'assistant:subagent'
  id: string | undefined
  messages: ChatMessage[]
}

export type MessageGroup =
  | HumanMessageGroup
  | AssistantProcessingGroup
  | AssistantMessageGroup
  | AssistantPresentFilesGroup
  | AssistantClarificationGroup
  | AssistantSubagentGroup

/** Per-message token usage metadata (from SSE values events). */
export interface UsageMetadata {
  inputTokens: number
  outputTokens: number
}

/** Real-time planning step from SSE custom events. */
export interface PlanningStep {
  id: string
  toolName: string
  args: Record<string, unknown>
  status: 'pending' | 'running' | 'done' | 'error'
  timestamp: number
  /** 后端 resolve_tool_metadata 解析的可读名称(如"查询资产数据") */
  displayName?: string
  /** 后端 i18n key(如"toolName.getAssetsData")，前端 t() 翻译 */
  displayKey?: string
  /** 工具图标(emoji) */
  icon?: string
  /** 工具类型分类 */
  toolType?: string
}

/**
 * 消息类型 — 统一前端消息结构
 *
 * 参考 DeerFlow Message 类型，适配 Numina 后端事件
 */
export interface ChatMessage {
  id: string
  type: 'human' | 'ai' | 'tool'
  role: 'user' | 'assistant'
  content: string
  /** 推理内容（剥离后的安全摘要） */
  reasoning?: string | null
  /** 工具调用列表 */
  tool_calls?: ToolCallSummary[]
  /** 工具调用结果 */
  tool_call_id?: string
  /** 工具名称 */
  name?: string
  /** 显示时间 */
  displayTime: string
  /** 发送状态（仅 human） */
  sendStatus?: 'sending' | 'sent' | 'failed'
  /** 消息阶段（仅 AI） */
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  /** 建议（仅 AI） */
  suggestions?: string[]
  /** Artifact 列表 */
  artifacts?: Artifact[]
  /** 反馈状态 */
  feedback?: 1 | -1 | 0
  /** 附加参数（用于 hide_from_ui 等） */
  additional_kwargs?: Record<string, unknown>
  /** 子智能体信息 */
  subagent?: SubagentInfo
  /** Per-message token usage (from SSE values usage_metadata) */
  usageMetadata?: UsageMetadata
}

/** 工具调用摘要 */
export interface ToolCallSummary {
  id: string
  name: string
  displayName?: string
  /** 后端 i18n key(如"toolName.getAssetsData")，前端 t() 翻译 */
  displayKey?: string
  args?: Record<string, unknown>
  result?: unknown
  status?: 'pending' | 'running' | 'success' | 'error'
  elapsedMs?: number
  progressMessage?: string
}

/** Artifact 结构 */
export interface Artifact {
  id: string
  title: string
  kind: 'data' | 'link' | 'image' | 'file' | 'other' | 'report'
  url?: string
  path?: string
}

/** 子智能体信息 */
export interface SubagentInfo {
  taskId: string
  title?: string
  description?: string
  status: 'in_progress' | 'completed' | 'failed' | 'cancelled' | 'timed_out'
  progressMessage?: string
  result?: string
  error?: string
}

/**
 * DeerFlow 需要从 UI 隐藏的控制消息名称
 *
 * 参考: frontend/src/core/messages/utils.ts HIDDEN_CONTROL_MESSAGE_NAMES
 */
export const HIDDEN_CONTROL_MESSAGE_NAMES = new Set([
  'summary',              // 内部总结
  'loop_warning',         // 循环警告
  'todo_reminder',        // Todo 提醒
  'todo_completion_reminder', // Todo 完成提醒
])

/**
 * 判断消息是否应从 UI 隐藏
 *
 * 规则:
 * 1. additional_kwargs.hide_from_ui === true
 * 2. message.name 在 HIDDEN_CONTROL_MESSAGE_NAMES 中
 */
export function isHiddenFromUIMessage(message: ChatMessage): boolean {
  return (
    (message.additional_kwargs?.hide_from_ui as boolean) === true ||
    (typeof message.name === 'string' &&
      HIDDEN_CONTROL_MESSAGE_NAMES.has(message.name))
  )
}