/**
 * DeerFlow AI Chat Utils
 *
 * 统一导出 ai-chat 相关工具函数
 */

// Tool icon mapping
export {
  TOOL_ICON_MAP,
  TOOL_DISPLAY_NAME_KEY_MAP,
  TOOL_ACTION_KEY_MAP,
  getToolIcon,
  getToolDisplayNameKey,
  explainToolCallKey,
} from './tool-icon-map'

// Message identity and deduplication
export {
  messageIdentity,
  createMessageIdentitySet,
  isMessageSeen,
  markMessageSeen,
  deduplicateMessages,
} from './message-identity'

// Reasoning filter and content extraction
export {
  splitInlineReasoning,
  extractReasoningContentFromMessage,
  extractContentFromMessage,
  hasReasoning,
  hasContent,
} from './reasoning-filter'

// Message grouping algorithm
export {
  getMessageGroups,
  hasToolCalls,
  hasPresentFiles,
  hasSubagent,
  isClarificationToolMessage,
  extractToolCalls,
  findToolCallResult,
  extractPresentFilesFromGroup,
  getSubagentCount,
  getSubagentTaskIds,
} from './messageGroups'

// Message adapter (Legacy → DeerFlow)
export {
  toDeerFlowChatMessage,
  toDeerFlowChatMessages,
  extractLegacyFields,
  type LegacyMessage,
  type ToolTimelineItem,
  type ProcessStep,
  type PlanStep,
} from './messageAdapter'