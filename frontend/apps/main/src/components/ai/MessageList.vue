<script setup lang="ts">
import { nextTick, ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MessageGroup from '@/components/ai-chat/MessageGroup.vue'
import type { ChatMessage } from '@/types/ai-chat/message-group'
import { useMessageGroups } from '@/composables/ai-chat/useMessageGroups'

const props = defineProps<{
  messages: ChatMessage[]
  isStreaming: boolean
  threadId?: string
}>()

const emit = defineEmits<{
  retry: []
  stop: []
  suggestionClick: [text: string]
  artifactTap: [artifact: { id: string; title: string; kind: string; url?: string; path?: string }]
}>()

const { t } = useI18n()

const scrollRef = ref<HTMLElement | null>(null)

// Group messages for display (dedupe + group into DeerFlow 6-type structure)
const messageGroups = useMessageGroups(toRef(props, 'messages'))

// Auto-scroll to bottom on new messages
watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  }
)
</script>

<template>
  <div ref="scrollRef" class="message-list">
    <div v-if="messages.length === 0" class="message-list-empty">
      <p>{{ t('aiChat.startConversation') }}</p>
    </div>
    <div v-else class="message-list-content">
      <MessageGroup
        v-for="(group, index) in messageGroups"
        :key="group.id ?? index"
        :group="group"
        :thread-id="threadId"
        @suggestion-click="(text: string) => emit('suggestionClick', text)"
        @artifact-tap="(artifact: { id: string; title: string; kind: string; url?: string; path?: string }) => emit('artifactTap', artifact)"
      />
    </div>
    <div v-if="isStreaming" class="message-list-streaming-indicator">
      <van-loading type="spinner" />
    </div>
    <div v-if="!isStreaming && messages.length > 0" class="message-list-actions">
      <van-button
        size="small"
        plain
        @click="emit('retry')"
      >
        {{ t('aiChat.retry') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: 140px; /* Space for the floating bottom input box */
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message-list-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--van-text-color-3, #999);
  font-size: 14px;
}

.message-list-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-list-streaming-indicator {
  display: flex;
  justify-content: center;
  padding: 8px;
}

.message-list-actions {
  display: flex;
  justify-content: center;
  padding: 8px;
}
</style>
