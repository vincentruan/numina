/**
 * DeerFlow Input Mode Types
 *
 * 参考: frontend/src/components/workspace/input-box.tsx InputMode
 */

/**
 * DeerFlow 执行模式类型
 *
 * 四种模式:
 * - Flash: minimal, 快速响应
 * - Thinking: low, 启用思考链
 * - Pro: medium, 计划模式
 * - Ultra: high, 子代理协作
 */
export type InputMode = 'flash' | 'thinking' | 'pro' | 'ultra'

/**
 * 执行模式配置
 */
export interface InputModeConfig {
  mode: InputMode
  thinking_enabled: boolean
  is_plan_mode: boolean
  subagent_enabled: boolean
  reasoning_effort: 'minimal' | 'low' | 'medium' | 'high'
  icon: string
  label: string
  description: string
}

/**
 * 发送 Payload 结构
 *
 * DeerFlow 参考: input-box.tsx SubmitPayload
 */
export interface SubmitPayload {
  text: string
  files?: FileInMessage[]
  model_name: string
  mode: InputMode
  thinking_enabled: boolean
  is_plan_mode: boolean
  subagent_enabled: boolean
  reasoning_effort: 'minimal' | 'low' | 'medium' | 'high'
  thread_id?: string
  websearch_enabled?: boolean
}

/**
 * 输入框上下文
 *
 * 用于跟踪当前模型和模式选择
 */
export interface InputContext {
  model_name: string
  mode: InputMode
  reasoning_effort: 'minimal' | 'low' | 'medium' | 'high'
}

/**
 * 附件文件信息
 */
export interface FileInMessage {
  path: string
  filename: string
  mime_type?: string
}