<script setup lang="ts">
/**
 * ChatMessage — Unified message container following DeerFlow pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/messages/message-list-item.tsx
 *
 * Key patterns:
 * - User messages: right-aligned, narrow bubble (w-fit), max-width 70%
 * - Assistant messages: left-aligned, full width (w-full), collapsible sections
 * - Proper role-based styling without nested complexity
 */
import type { ProcessStep, PlanStep } from '@/types/agent-stream'
import UserBubble from './UserBubble.vue'
import AssistantMessage from './AssistantMessage.vue'

interface Props {
  id: string
  role: 'user' | 'assistant'
  content: string
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  // Assistant-specific props
  processSteps?: ProcessStep[]
  planSteps?: PlanStep[]
  planSource?: 'explicit' | 'inferred' | null
  processElapsedMs?: number
  reasoningStartTime?: number | null
  renderedContent?: string
  suggestions?: string[]
  feedback?: 1 | -1 | 0
  displayTime: string
  sendStatus?: 'sending' | 'sent' | 'failed'
  artifacts?: Array<{ id: string; title: string; kind: string; url?: string; path?: string }>
  // User edit props
  isEditing?: boolean
  editInput?: string
}

const _props = defineProps<Props>()

// Events for user interactions
const emit = defineEmits<{
  retry: []
  copy: [content: string]
  edit: []
  feedback: [messageId: string, value: 1 | -1]
  suggestionClick: [text: string]
  artifactTap: [artifact: { id: string; title: string; kind: string; url?: string; path?: string }]
  // Edit events
  sendEdit: []
  cancelEdit: []
  'update:editInput': [value: string]
}>()
</script>

<template>
  <!-- DeerFlow pattern: message-row with role class determines alignment -->
  <div class="message-row" :class="role">
    <!-- User: narrow bubble, right-aligned -->
    <UserBubble
      v-if="role === 'user'"
      :content="content"
      :display-time="displayTime"
      :send-status="sendStatus"
      :is-editing="isEditing"
      :edit-input="editInput"
      @copy="emit('copy', content)"
      @edit="emit('edit')"
      @retry="emit('retry')"
      @send-edit="emit('sendEdit')"
      @cancel-edit="emit('cancelEdit')"
      @update:edit-input="emit('update:editInput', $event)"
    />

    <!-- Assistant: full-width message container -->
    <AssistantMessage
      v-else
      :id="id"
      :content="content"
      :phase="phase"
      :process-steps="processSteps"
      :plan-steps="planSteps"
      :plan-source="planSource"
      :process-elapsed-ms="processElapsedMs"
      :reasoning-start-time="reasoningStartTime"
      :rendered-content="renderedContent"
      :suggestions="suggestions"
      :feedback="feedback"
      :display-time="displayTime"
      :artifacts="artifacts"
      @retry="emit('retry')"
      @copy="emit('copy', content)"
      @feedback="(v) => emit('feedback', id, v)"
      @suggestion-click="emit('suggestionClick', $event)"
      @artifact-tap="emit('artifactTap', $event)"
    />
  </div>
</template>

<style scoped>
/* DeerFlow pattern: role-based alignment */
.message-row {
  display: flex;
  width: 100%;
  padding: 0 12px;
  margin-bottom: 12px;
}

.message-row.user {
  justify-content: flex-end; /* Right-aligned for user */
}

.message-row.assistant {
  justify-content: flex-start; /* Left-aligned for assistant */
}
</style>