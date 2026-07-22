<script setup lang="ts">
import InputBox from '@/components/ai-chat/InputBox.vue'
import type { SubmitPayload } from '@/types/ai-chat/input-mode'

// Draft text to pre-fill the input with (e.g. recovered after a failed
// auto-send from the AI hub). Empty/undefined leaves the input blank.
defineProps<{
  modelValue?: string
  agentId?: string
  agents?: Array<{ id: string; display_name: string; agent_name?: string; icon?: string; color?: string | null; description?: string | null }>
  agentIcon?: string
  agentLabel?: string
  /** When true, agent icon shows info popup instead of triggering selection */
  readonly?: boolean
}>()
defineEmits<{
  startChat: [payload: SubmitPayload]
}>()
</script>

<template>
  <div class="welcome-page">
    <!-- InputBox handles hero + examples + input in welcome mode (DeerFlow pattern) -->
    <InputBox
      status="ready"
      is-welcome-mode
      :model-value="modelValue"
      :agent-id="agentId"
      :agents="agents"
      :agent-icon="agentIcon"
      :agent-label="agentLabel"
      :readonly="readonly"
      @submit="$emit('startChat', $event)"
    />
  </div>
</template>

<style scoped>
.welcome-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 16px;
}
</style>
