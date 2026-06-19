<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { showToast } from 'vant'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'
import { createThread } from '@/api/ai-chat'
import WelcomePage from '@/components/ai/WelcomePage.vue'
import MessageList from '@/components/ai/MessageList.vue'
import SessionSidebar from '@/components/ai/SessionSidebar.vue'
import InputBox from '@/components/ai-chat/InputBox.vue'
import { useI18n } from 'vue-i18n'

const store = useChatSessionStore()
const chat = useThreadChat()
const { t } = useI18n()

// Initialize from URL on mount
onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const threadId = params.get('thread_id')
  if (threadId) {
    store.setActiveThread(threadId)
    chat.loadHistory(threadId)
  }
})

// Watch for thread switches — load history
watch(
  () => store.activeThreadId,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      await chat.loadHistory(newId)
    }
  }
)

// Handle errors from chat
watch(
  () => chat.error.value,
  (err) => {
    if (err) {
      showToast({ message: err })
    }
  }
)

async function handleStartChat(text: string) {
  try {
    const thread = await createThread()
    store.setActiveThread(thread.thread_id)
    await chat.sendMessage(text, { mode: 'flash' }, thread.thread_id)
  } catch {
    showToast({ message: t('ai.chat.errors.sendFailed') })
  }
}

async function handleSendMessage(text: string) {
  if (!store.activeThreadId) return
  await chat.sendMessage(text, { mode: 'flash' }, store.activeThreadId)
}

function handleStopStream() {
  chat.cancelStream()
}

async function handleRetry() {
  if (store.activeThreadId) {
    await chat.retry(store.activeThreadId)
  }
}

function handleSelectThread(threadId: string) {
  store.setActiveThread(threadId)
  chat.loadHistory(threadId)
}
</script>

<template>
  <div class="ai-chat-box">
    <SessionSidebar @select-thread="handleSelectThread" />

    <template v-if="store.isWelcomeMode">
      <WelcomePage @start-chat="handleStartChat" />
    </template>
    <template v-else>
      <MessageList
        :messages="chat.messages.value"
        :is-loading="chat.isLoading.value"
        @retry="handleRetry"
        @stop="handleStopStream"
      />
      <InputBox
        :disabled="chat.isLoading.value"
        @submit="handleSendMessage"
      />
    </template>
  </div>
</template>

<style scoped>
.ai-chat-box {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}
</style>
