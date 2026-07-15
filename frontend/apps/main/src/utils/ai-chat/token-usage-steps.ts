/**
 * Token usage debug steps - DeerFlow parity.
 *
 * 参考: deer-flow-reference/frontend/src/core/messages/usage-model.ts buildTokenDebugSteps()
 *
 * For each AI message, derives a labeled "debug step" describing what consumed
 * tokens for that message - e.g. "搜索：xxx", "读取文件", "最终回复", "思考".
 * The step carries the message's usage_metadata so the UI can show per-step
 * token attribution in `debug` mode.
 *
 * Numina's backend sends `token_usage_attribution` in `additional_kwargs`
 * (via DeerFlow's TokenUsageMiddleware). When available, we use the rich
 * attribution data; otherwise we fall back to deriving labels from `tool_calls`.
 */
import type { ChatMessage, UsageMetadata } from '@/types/ai-chat/message-group'
import { explainToolCallKey } from '@/utils/ai-chat/tool-icon-map'

export interface TokenDebugStep {
  id: string
  messageId: string
  /** Primary label, e.g. "最终回复" or "步骤总计" (when multiple actions) */
  label: string
  /** Secondary action labels when multiple tools share attribution */
  secondaryLabels: string[]
  /** Token usage for this step (null if message has no usage_metadata) */
  usage: { inputTokens: number; outputTokens: number; totalTokens: number } | null
  /** True when multiple actions contributed to this step's token cost */
  sharedAttribution: boolean
}

/**
 * Token usage attribution from backend (DeerFlow TokenUsageMiddleware).
 * Stored in AIMessage.additional_kwargs["token_usage_attribution"].
 */
interface TokenUsageAttribution {
  version: number
  kind: 'thinking' | 'final_answer' | 'tool_batch' | 'todo_update' | 'subagent_dispatch'
  shared_attribution: boolean
  tool_call_ids: string[]
  actions: Array<{
    kind: string
    tool_name?: string
    tool_call_id?: string
    description?: string
    content?: string
    query?: string
    subagent_type?: string
  }>
}

/**
 * Extract token_usage_attribution from message's additional_kwargs.
 * Returns null if not present or invalid.
 */
function getTokenUsageAttribution(message: ChatMessage): TokenUsageAttribution | null {
  if (message.type !== 'ai') return null
  const ak = message.additional_kwargs
  if (!ak || typeof ak !== 'object') return null
  const attr = ak.token_usage_attribution
  if (!attr || typeof attr !== 'object') return null
  const obj = attr as Record<string, unknown>
  if (typeof obj.version !== 'number') return null
  if (!Array.isArray(obj.actions)) return null
  return obj as unknown as TokenUsageAttribution
}

/**
 * Build a human-readable label from an attribution action.
 * Mirrors DeerFlow's action label generation.
 */
function actionToLabel(
  action: TokenUsageAttribution['actions'][number],
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  switch (action.kind) {
    case 'subagent':
      return action.description || t('aiChat.tokenUsageSubagentTask')
    case 'search':
      return action.query
        ? t('aiChat.tokenUsageSearchAction', { query: action.query })
        : t('aiChat.tokenUsageSearchGeneric')
    case 'tool':
      if (action.tool_name && action.description) {
        return action.description
      }
      if (action.tool_name) {
        const { key, params } = explainToolCallKey(action.tool_name, {})
        return params ? t(key, params) : t(key)
      }
      return t('aiChat.tokenUsageToolAction')
    case 'todo_start':
    case 'todo_complete':
    case 'todo_update':
    case 'todo_remove':
      return action.content || t('aiChat.tokenUsageTodoAction')
    default:
      return action.description || t('aiChat.tokenUsageToolAction')
  }
}

/** Build already-translated action labels for a single AI message's tool calls. */
function buildToolCallLabels(
  message: ChatMessage,
  t: (key: string, params?: Record<string, unknown>) => string,
): string[] {
  const labels: string[] = []
  for (const tc of message.tool_calls ?? []) {
    if (!tc.name) continue
    // explainToolCallKey returns { key, params } for i18n - translates to a
    // human description like "搜索：xxx" / "读取家庭概览" / "执行命令".
    const { key, params } = explainToolCallKey(tc.name, tc.args)
    labels.push(t(key, params))
  }
  return labels
}

/**
 * Build a debug step for a single AI message.
 *
 * Used by the inline TokenUsage renderer (debug mode) - each message's inline
 * instance only needs its own step, not the full list.
 *
 * @param message - A single AI message (must have usageMetadata for a meaningful step)
 * @param t - i18n translation function
 */
export function buildTokenDebugStep(
  message: ChatMessage,
  t: (key: string, params?: Record<string, unknown>) => string,
): TokenDebugStep | null {
  if (message.type !== 'ai') return null

  const usage = extractUsage(message)

  // Try to use token_usage_attribution from backend (DeerFlow pattern)
  const attribution = getTokenUsageAttribution(message)

  if (attribution && attribution.actions.length > 0) {
    // Use rich attribution data from backend
    const labels = attribution.actions.map(action => actionToLabel(action, t))
    const sharedAttribution = attribution.shared_attribution || labels.length > 1

    return {
      id: message.id || `token-step-${message.id}`,
      messageId: message.id || `token-step-${message.id}`,
      label: sharedAttribution
        ? t('aiChat.tokenUsageStepTotal')
        : labels[0]!,
      secondaryLabels: sharedAttribution ? labels : [],
      usage,
      sharedAttribution,
    }
  }

  // Fallback: derive labels from tool_calls (legacy path)
  const actionLabels = buildToolCallLabels(message, t)

  if (actionLabels.length === 0) {
    const hasContent = !!message.content?.trim()
    actionLabels.push(
      hasContent ? t('aiChat.tokenUsageFinalAnswer') : t('aiChat.tokenUsageThinking'),
    )
  }

  const sharedAttribution = actionLabels.length > 1
  return {
    id: message.id || `token-step-${message.id}`,
    messageId: message.id || `token-step-${message.id}`,
    label: sharedAttribution
      ? t('aiChat.tokenUsageStepTotal')
      : actionLabels[0]!,
    secondaryLabels: sharedAttribution ? actionLabels : [],
    usage,
    sharedAttribution,
  }
}

/**
 * Build debug steps for a list of messages (one step per AI message with usage).
 *
 * @param messages - All messages in the thread (only AI messages produce steps)
 * @param t - i18n translation function
 */
export function buildTokenDebugSteps(
  messages: ChatMessage[],
  t: (key: string, params?: Record<string, unknown>) => string,
): TokenDebugStep[] {
  const steps: TokenDebugStep[] = []

  for (const [index, message] of messages.entries()) {
    if (message.type !== 'ai') continue
    const step = buildTokenDebugStep(message, t)
    if (step) {
      // Preserve index-based fallback id for messages without ids
      if (!message.id) step.id = `token-step-${index}`
      steps.push(step)
    }
  }

  return steps
}

/**
 * Extract usage_metadata from a ChatMessage into a flat token-usage object.
 * Returns null if the message has no usage_metadata.
 */
function extractUsage(
  message: ChatMessage,
): { inputTokens: number; outputTokens: number; totalTokens: number } | null {
  const meta: UsageMetadata | undefined = message.usageMetadata
  if (!meta) return null
  const inputTokens = meta.inputTokens ?? 0
  const outputTokens = meta.outputTokens ?? 0
  return {
    inputTokens,
    outputTokens,
    totalTokens: inputTokens + outputTokens,
  }
}

/**
 * Accumulate token usage across a list of messages, deduplicating by message id.
 *
 * 参考: deer-flow-reference/frontend/src/core/messages/usage.ts accumulateUsage()
 *
 * UI rendering may place the same AI message in more than one group (e.g. a
 * message with both reasoning and final answer). Token usage is attached to
 * the message itself, so a message id should only contribute once to any
 * aggregate.
 */
export function accumulateUsage(
  messages: ChatMessage[],
): { inputTokens: number; outputTokens: number; totalTokens: number } | null {
  const cumulative = { inputTokens: 0, outputTokens: 0, totalTokens: 0 }
  let hasUsage = false
  const countedIds = new Set<string>()

  for (const message of messages) {
    if (message.type !== 'ai') continue
    const usage = extractUsage(message)
    if (!usage) continue

    if (message.id) {
      if (countedIds.has(message.id)) continue
      countedIds.add(message.id)
    }

    hasUsage = true
    cumulative.inputTokens += usage.inputTokens
    cumulative.outputTokens += usage.outputTokens
    cumulative.totalTokens += usage.totalTokens
  }

  return hasUsage ? cumulative : null
}

/**
 * Format a token count for display: 1234 -> "1,234", 12345 -> "12.3K".
 *
 * 参考: deer-flow-reference/frontend/src/core/messages/usage.ts formatTokenCount()
 * DeerFlow switches to "K" at 10_000; Numina's pre-existing inline renderer
 * switched at 1_000. We adopt DeerFlow's threshold for the new header dropdown
 * to match its visual density (numbers under 10K are readable as-is).
 */
export function formatTokenCount(count: number): string {
  if (count < 10_000) return count.toLocaleString()
  return `${(count / 1000).toFixed(1)}K`
}
