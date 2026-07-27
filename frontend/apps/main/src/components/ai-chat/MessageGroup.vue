<script setup lang="ts">
/**
 * DeerFlow MessageGroup 组件
 *
 * 参考: frontend/src/components/workspace/messages/message-group.tsx
 *
 * 职责:
 * - 根据 group type 路由到对应子组件
 * - human → UserBubble
 * - assistant → AssistantMessage
 * - assistant:processing → ChainOfThought
 * - assistant:clarification → ClarificationCard
 * - assistant:present-files → ArtifactFileList
 * - assistant:subagent → SubtaskCard
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import UserBubble from '@/components/chat/UserBubble.vue'
import AssistantMessage from '@/components/chat/AssistantMessage.vue'
import ChainOfThought from './ChainOfThought.vue'
import TokenUsage from './TokenUsage.vue'
import MarkdownContent from './MarkdownContent.vue'
import SubtaskCard from './SubtaskCard.vue'
import ArtifactFileList from './ArtifactFileList.vue'
import HumanInputCard from './HumanInputCard.vue'
import type {
  MessageGroup,
  ChatMessage,
  AssistantProcessingGroup,
  AssistantClarificationGroup,
  AssistantPresentFilesGroup,
  AssistantSubagentGroup,
} from '@/types/ai-chat/message-group'
import {
  extractContentFromMessage,
  extractPresentFilesFromGroup,
  getSubagentTaskIds,
  extractLegacyFields,
} from '@/utils/ai-chat'
import type { ProcessStep, PlanStep } from '@/types/agent-stream'

const props = defineProps<{
  group: MessageGroup
  isLoading?: boolean
  threadId?: string
  isLastAssistant?: boolean
  canBranch?: boolean
  branchingMessageId?: string | null
  answeredInterruptIds?: Set<string>
  /** Previous group's planSteps - used to detect redundant completion summaries */
  prevGroupPlanSteps?: PlanStep[]
}>()

const emit = defineEmits<{
  retry: []
  copy: [content: string]
  feedback: [messageId: string, value: 1 | -1]
  suggestionClick: [text: string]
  artifactTap: [artifact: { id: string; title: string; kind: string; url?: string; path?: string }]
  branch: [messageId: string, messageIds: string[]]
  clarificationSubmit: [payload: { threadId: string; interruptId: string; answer: string }]
}>()

const { t } = useI18n()

// Human group: extract first message
const humanMessage = computed(() =>
  props.group.type === 'human' ? props.group.messages[0] : null
)

// Assistant group: extract first message
const assistantMessage = computed(() =>
  props.group.type === 'assistant' ? props.group.messages[0] : null
)

// Assistant group: extract content with thinking tags stripped.
// Without this, <think>...</think> tags from the backend (llm.py) leak into
// MarkdownContent and render as regular body text — the user sees the raw
// thinking content mixed into the AI response. extractContentFromMessage
// calls splitInlineReasoning which strips fully-closed and unclosed
// <think> / halle_think_start tags, matching DeerFlow's approach where
// reasoning is rendered in a separate muted collapsible section.
const assistantCleanContent = computed(() => {
  if (!assistantMessage.value) return ''
  return extractContentFromMessage(assistantMessage.value)
})

// Assistant group: extract legacy fields for processSteps, etc.
const assistantLegacyFields = computed(() => {
  if (!assistantMessage.value) return null
  return extractLegacyFields(assistantMessage.value)
})

// Assistant group: extract processSteps for reasoning/tool rendering
const assistantProcessSteps = computed((): ProcessStep[] | undefined =>
  assistantLegacyFields.value?.processSteps
)

// Assistant group: extract planSteps for TodoList rendering
// Falls back to prevGroupPlanSteps for detecting redundant completion summaries
const assistantPlanSteps = computed((): PlanStep[] | undefined =>
  assistantLegacyFields.value?.planSteps || props.prevGroupPlanSteps
)

// Assistant group: extract planSource
const assistantPlanSource = computed((): 'explicit' | 'inferred' | null | undefined =>
  assistantLegacyFields.value?.planSource
)

// Assistant group: extract process elapsed time
const assistantElapsedMs = computed((): number | undefined =>
  assistantLegacyFields.value?.processElapsedMs
)

// Assistant group: extract reasoning start time
const assistantReasoningStartTime = computed((): number | null | undefined =>
  assistantLegacyFields.value?.reasoningStartTime
)

// Processing group: extract tool calls
const processingGroup = computed(() =>
  props.group.type === 'assistant:processing'
    ? (props.group as AssistantProcessingGroup)
    : null
)

// Clarification group: extract content
const clarificationContent = computed(() => {
  if (props.group.type !== 'assistant:clarification') return null
  const msg = (props.group as AssistantClarificationGroup).messages[0]
  return extractContentFromMessage(msg)
})

// Clarification group: extract interruptData for HumanInputCard
const clarificationInterruptData = computed(() => {
  if (props.group.type !== 'assistant:clarification') return null
  return (props.group as AssistantClarificationGroup).interruptData ?? null
})

// Clarification status: derived from answeredInterruptIds (computed by
// useThreadChat from human_input_response messages) or group.phase. The card
// stays 'pending' while the answer is in-flight (sendMessage's isLoading guard
// prevents double-submit); it transitions to 'answered' once the response
// message lands in the thread.
const clarificationStatus = computed((): 'pending' | 'submitting' | 'answered' => {
  if (props.group.type !== 'assistant:clarification') return 'pending'
  const interruptId = (props.group as AssistantClarificationGroup).interruptData?.interrupt_id
  if (interruptId && props.answeredInterruptIds?.has(interruptId)) return 'answered'
  if (props.group.phase === 'answered') return 'answered'
  return 'pending'
})

// Branch: extract all assistant message IDs from the group
const assistantMessageIds = computed((): string[] => {
  if (props.group.type !== 'assistant') return []
  return props.group.messages
    .filter(msg => msg.role === 'assistant' && msg.id)
    .map(msg => msg.id!)
})

// Branch: check if this specific message is currently branching
const isBranching = computed(() => {
  if (!props.branchingMessageId || !assistantMessage.value) return false
  return props.branchingMessageId === assistantMessage.value.id
})

// Handle branch button click
function handleBranch() {
  if (!assistantMessage.value?.id) return
  emit('branch', assistantMessage.value.id, assistantMessageIds.value)
}

// Handle clarification answer submission
function handleClarificationSubmit(group: MessageGroup, answer: string) {
  if (group.type !== 'assistant:clarification') return
  const interruptId = group.interruptData?.interrupt_id
  const threadId = props.threadId
  if (!interruptId || !threadId) return
  // Emit to parent (AIChatBox) which calls submitClarification (sends a new
  // HumanMessage with human_input_response - DeerFlow pattern, not a resume)
  emit('clarificationSubmit', { threadId, interruptId, answer })
}

// Present-files group: extract files
const presentFilesData = computed(() => {
  if (props.group.type !== 'assistant:present-files') return null
  const group = props.group as AssistantPresentFilesGroup
  const msg = group.messages[0]
  return {
    content: extractContentFromMessage(msg),
    files: extractPresentFilesFromGroup(group),
  }
})

// Assistant group: extract all AI messages for group-level token usage rendering
const assistantMessages = computed((): ChatMessage[] => {
  if (props.group.type !== 'assistant') return []
  return props.group.messages.filter(m => m.type === 'ai')
})

/** Whether any AI message in this group has usage data (for TokenUsage visibility) */
const groupHasAiUsage = computed(() =>
  assistantMessages.value.some(m => m.type === 'ai' && m.usageMetadata)
)

// Subagent group: extract task IDs
const subagentTaskIds = computed(() => {
  if (props.group.type !== 'assistant:subagent') return []
  return getSubagentTaskIds(props.group as AssistantSubagentGroup)
})

</script>

<template>
  <div class="message-group" :class="`group--${group.type}`">
    <!-- Human: UserBubble -->
    <UserBubble
      v-if="humanMessage"
      :content="humanMessage.content"
      :display-time="humanMessage.displayTime"
      :send-status="humanMessage.sendStatus"
      @copy="emit('copy', humanMessage.content)"
    />

    <!-- Assistant: AssistantMessage -->
    <template v-else-if="assistantMessage">
      <!-- Tool calls render in the assistant:processing group (ChainOfThought)
           driven by the live messages array, matching DeerFlow. No separate
           real-time planning panel - it duplicated tool calls and its per-step
           status never updated from tool results (stuck "调用中"). -->
      <AssistantMessage
        :id="assistantMessage.id"
        :content="assistantCleanContent"
        :phase="assistantMessage.phase || 'done'"
        :process-steps="assistantProcessSteps"
        :plan-steps="assistantPlanSteps"
        :plan-source="assistantPlanSource"
        :process-elapsed-ms="assistantElapsedMs"
        :reasoning-start-time="assistantReasoningStartTime"
        :display-time="assistantMessage.displayTime"
        :suggestions="assistantMessage.suggestions"
        :feedback="assistantMessage.feedback"
        :can-branch="canBranch && !isLoading"
        :is-branching="isBranching"
        @retry="emit('retry')"
        @copy="emit('copy', assistantCleanContent)"
        @feedback="(v: 1 | -1) => emit('feedback', assistantMessage!.id, v)"
        @suggestion-click="emit('suggestionClick', $event)"
        @branch="handleBranch"
      />
      <!-- Per-turn token usage (DeerFlow pattern: rendered at group level, not
           per-message). Aggregates usage across all AI messages in the group
           for per_turn mode; builds debug cards for all messages in debug mode.
           Visibility is controlled by the global token-usage preset inside
           TokenUsage (off/per_turn/debug). -->
      <TokenUsage
        v-if="assistantMessage.type === 'ai' && groupHasAiUsage"
        mode="inline"
        :thread-id="threadId || null"
        :usage-metadata="assistantMessage.usageMetadata"
        :is-streaming="isLoading && isLastAssistant"
        :messages="assistantMessages"
      />
    </template>

    <!-- Processing: ChainOfThought -->
    <ChainOfThought
      v-else-if="processingGroup"
      :messages="processingGroup.messages"
      :is-loading="isLoading"
      @artifact-select="(filepath: string) => emit('artifactTap', { id: filepath, title: filepath, kind: 'file', path: filepath })"
    />

    <!-- Clarification: interactive HumanInputCard -->
    <HumanInputCard
      v-else-if="group.type === 'assistant:clarification'"
      :question="clarificationInterruptData?.question || clarificationContent || ''"
      :options="clarificationInterruptData?.options"
      :context="clarificationInterruptData?.context"
      :choice-with-other="clarificationInterruptData?.choiceWithOther"
      :status="clarificationStatus"
      :answer="group.answer"
      :thread-id="threadId || ''"
      :interrupt-id="clarificationInterruptData?.interrupt_id || ''"
      @submit="handleClarificationSubmit(group, $event)"
    />

    <!-- Present-files: Content + File list -->
    <div v-else-if="presentFilesData" class="present-files-group">
      <MarkdownContent
        v-if="presentFilesData.content"
        class="present-files-text"
        :content="presentFilesData.content"
      />
      <ArtifactFileList
        v-if="presentFilesData.files && presentFilesData.files.length > 0"
        :artifacts="presentFilesData.files"
        :session-id="threadId || ''"
        @select="(artifact: { id: string; title: string; kind?: string; url?: string; path?: string }) => emit('artifactTap', { id: artifact.id, title: artifact.title, kind: artifact.kind || 'other', url: artifact.url, path: artifact.path })"
      />
    </div>

    <!-- Subagent: Task cards -->
    <div v-else-if="subagentTaskIds.length > 0" class="subagent-group">
      <div class="subagent-header">
        {{ t('aiChat.subagentTasks', { count: subagentTaskIds.length }) }}
      </div>
      <SubtaskCard
        v-for="taskId in subagentTaskIds"
        :key="taskId"
        :task-id="taskId"
        :is-loading="isLoading"
      />
    </div>
  </div>
</template>

<style scoped>
.message-group {
  width: 100%;
  margin-bottom: 12px;
}

/* Present-files group */
.present-files-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.present-files-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
}

.present-files-text :deep(p) {
  margin: 0;
}

/* Subagent group */
.subagent-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.subagent-header {
  font-size: 13px;
  font-weight: 500;
  color: #22c55e;
  padding-top: 8px;
}

/* Light theme - wrap FULL selector in :global() so it matches the scoped
 * element; data-theme attr (not OS preference) is the source of truth. */
:global([data-theme='light'] .file-card) {
  background: var(--card-bg);
  border-color: rgba(0, 0, 0, 0.06);
}

:global([data-theme='light'] .file-card:hover) {
  background: rgba(0, 0, 0, 0.02);
}
</style>