<script setup lang="ts">
import InputBox from '@/components/ai-chat/InputBox.vue'
import type { SubmitPayload } from '@/types/ai-chat/input-mode'

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
