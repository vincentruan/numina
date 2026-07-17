<script setup lang="ts">
import InputBox from '@/components/ai-chat/InputBox.vue'
import type { SubmitPayload } from '@/types/ai-chat/input-mode'

// Draft text to pre-fill the input with (e.g. recovered after a failed
// auto-send from the AI hub). Empty/undefined leaves the input blank.
defineProps<{ modelValue?: string }>()
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
