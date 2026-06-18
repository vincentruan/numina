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
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import UserBubble from '@/components/chat/UserBubble.vue'
import AssistantMessage from '@/components/chat/AssistantMessage.vue'
import ChainOfThought from './ChainOfThought.vue'
import SubtaskCard from './SubtaskCard.vue'
import ArtifactFileList from './ArtifactFileList.vue'
import type {
  MessageGroup,
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
}>()

const emit = defineEmits<{
  retry: []
  copy: [content: string]
  feedback: [messageId: string, value: 1 | -1]
  suggestionClick: [text: string]
  artifactTap: [artifact: { id: string; title: string; kind: string; url?: string; path?: string }]
}>()

const { t } = useI18n()

// Configure marked
marked.use({ breaks: true })

// Human group: extract first message
const humanMessage = computed(() =>
  props.group.type === 'human' ? props.group.messages[0] : null
)

// Assistant group: extract first message
const assistantMessage = computed(() =>
  props.group.type === 'assistant' ? props.group.messages[0] : null
)

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
const assistantPlanSteps = computed((): PlanStep[] | undefined =>
  assistantLegacyFields.value?.planSteps
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

// Subagent group: extract task IDs
const subagentTaskIds = computed(() => {
  if (props.group.type !== 'assistant:subagent') return []
  return getSubagentTaskIds(props.group as AssistantSubagentGroup)
})

// Markdown rendering helper
function renderMarkdown(content: string): string {
  if (!content) return ''
  return DOMPurify.sanitize(marked.parse(content) as string)
}
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
    <AssistantMessage
      v-else-if="assistantMessage"
      :id="assistantMessage.id"
      :content="assistantMessage.content"
      :phase="assistantMessage.phase || 'done'"
      :process-steps="assistantProcessSteps"
      :plan-steps="assistantPlanSteps"
      :plan-source="assistantPlanSource"
      :process-elapsed-ms="assistantElapsedMs"
      :reasoning-start-time="assistantReasoningStartTime"
      :display-time="assistantMessage.displayTime"
      :suggestions="assistantMessage.suggestions"
      :feedback="assistantMessage.feedback"
      @retry="emit('retry')"
      @copy="emit('copy', assistantMessage.content)"
      @feedback="(v: 1 | -1) => emit('feedback', assistantMessage!.id, v)"
      @suggestion-click="emit('suggestionClick', $event)"
    />

    <!-- Processing: ChainOfThought -->
    <ChainOfThought
      v-else-if="processingGroup"
      :messages="processingGroup.messages"
      :is-loading="isLoading"
    />

    <!-- Clarification: Special card -->
    <div v-else-if="clarificationContent" class="clarification-card">
      <div class="clarification-header">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        <span class="clarification-title">{{ t('aiChat.needClarification') }}</span>
      </div>
      <!-- eslint-disable vue/no-v-html -- sanitized markdown -->
      <div class="clarification-content" v-html="renderMarkdown(clarificationContent)" />
      <!-- eslint-enable vue/no-v-html -->
    </div>

    <!-- Present-files: Content + File list -->
    <div v-else-if="presentFilesData" class="present-files-group">
      <!-- eslint-disable vue/no-v-html -- sanitized markdown -->
      <div
        v-if="presentFilesData.content"
        class="present-files-text"
        v-html="renderMarkdown(presentFilesData.content)"
      />
      <!-- eslint-enable vue/no-v-html -->
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

/* Clarification card */
.clarification-card {
  padding: 16px;
  background: rgba(129, 140, 248, 0.12);
  border: 1px solid rgba(129, 140, 248, 0.2);
  border-radius: 12px;
}

.clarification-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  color: var(--van-primary-color);
}

.clarification-title {
  font-size: 14px;
  font-weight: 600;
}

.clarification-content {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
}

.clarification-content :deep(p) {
  margin: 0 0 8px;
}

.clarification-content :deep(p:last-child) {
  margin-bottom: 0;
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

/* Light theme */
@media (prefers-color-scheme: light) {
  :global(.theme-light) .clarification-card {
    background: rgba(129, 140, 248, 0.08);
  }

  :global(.theme-light) .file-card {
    background: var(--card-bg);
    border-color: rgba(0, 0, 0, 0.06);
  }

  :global(.theme-light) .file-card:hover {
    background: rgba(0, 0, 0, 0.02);
  }
}
</style>