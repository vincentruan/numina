<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'
import { useArtifacts } from '@/composables/ai-chat/useArtifacts'
import { getThread, createThread } from '@/api/ai-chat'
import WelcomePage from '@/components/ai/WelcomePage.vue'
import MessageList from '@/components/ai/MessageList.vue'
import SessionSidebar from '@/components/ai/SessionSidebar.vue'
import InputBox from '@/components/ai-chat/InputBox.vue'
import TokenUsage from '@/components/ai-chat/TokenUsage.vue'
import ArtifactPreviewPopup from '@/components/ai-chat/ArtifactPreviewPopup.vue'
import type { SubmitPayload, InputContext } from '@/types/ai-chat/input-mode'

const store = useChatSessionStore()
const sidebarRef = ref<InstanceType<typeof SessionSidebar> | null>(null)

const chat = useThreadChat({
  onStreamEnd: scheduleTitleRefresh,
})
const {
  selectedArtifact,
  open: artifactPreviewOpen,
  select: selectArtifact,
  deselect: deselectArtifact,
} = useArtifacts()
const { t } = useI18n()

/** Title generation is async on the backend — poll twice after stream ends */
function scheduleTitleRefresh(threadId: string) {
  const doRefresh = async () => {
    try {
      const thread = await getThread(threadId)
      if (thread.title) {
        // Update store sessions if this thread is tracked there
        const idx = store.sessions.findIndex(s => s.thread_id === threadId)
        if (idx !== -1) {
          store.sessions[idx] = { ...store.sessions[idx], title: thread.title }
        }
        // Refresh sidebar thread list
        sidebarRef.value?.refreshSidebar()
      }
    } catch {
      // Title may not be ready yet — ignore
    }
  }
  // First attempt after 3s, second after 8s (title gen can take a few seconds)
  setTimeout(doRefresh, 3000)
  setTimeout(doRefresh, 8000)
}

// Initialize from URL on mount
onMounted(() => {
  store.initializeFromUrl()
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
      showFailToast(err)
    }
  }
)

async function handleStartChat(payload: SubmitPayload) {
  try {
    const thread = await createThread()
    store.setActiveThread(thread.thread_id)
    await chat.sendMessage(payload.text, payload.mode, thread.thread_id)
  } catch {
    showFailToast(t('aiChat.sendFailed'))
  }
}

async function handleSendMessage(payload: SubmitPayload) {
  if (!store.activeThreadId) return
  await chat.sendMessage(payload.text, payload.mode, store.activeThreadId)
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

// Handler for InputBox events
function handleStop() {
  chat.cancelStream()
}

function handleContextChange(_context: InputContext) {
  // Handle context changes if needed
}

function handleAgentChange(_agentId: string) {
  // Handle agent changes if needed
}

async function handleSuggestionClick(text: string) {
  if (!store.activeThreadId) return
  await chat.sendMessage(text, undefined, store.activeThreadId)
}

function handleArtifactTap(artifact: { id: string; title: string; kind: string; url?: string; path?: string }) {
  selectArtifact({ ...artifact, kind: artifact.kind as 'data' | 'link' | 'image' | 'file' | 'other' | 'report' })
}
</script>

<template>
  <div class="ai-chat-box">
    <SessionSidebar ref="sidebarRef" @select-thread="handleSelectThread" />

    <template v-if="store.isWelcomeMode">
      <!-- WelcomePage includes its own InputBox (DeerFlow pattern) -->
      <WelcomePage @start-chat="handleStartChat" />
    </template>
    <template v-else>
      <!-- Token usage bar -->
      <div v-if="store.activeThreadId" class="chat-header-bar">
        <TokenUsage
          :thread-id="store.activeThreadId"
          :refresh-trigger="chat.tokenUsage.value?.total_tokens"
        />
      </div>
      <MessageList
        :messages="chat.messages.value"
        :is-streaming="chat.isLoading.value"
        :thread-id="store.activeThreadId || undefined"
        @retry="handleRetry"
        @stop="handleStopStream"
        @suggestion-click="handleSuggestionClick"
        @artifact-tap="handleArtifactTap"
      />
      <!-- InputBox only in chat mode (WelcomePage has its own in welcome mode) -->
      <InputBox
        :status="chat.isLoading.value ? 'streaming' : 'ready'"
        :is-welcome-mode="false"
        :thread-id="store.activeThreadId || undefined"
        @submit="handleSendMessage"
        @stop="handleStop"
        @context-change="handleContextChange"
        @agent-change="handleAgentChange"
      />
    </template>

    <!-- Artifact preview popup -->
    <ArtifactPreviewPopup
      :show="artifactPreviewOpen"
      :artifact="selectedArtifact"
      :session-id="store.activeThreadId || ''"
      @update:show="(v: boolean) => v ? undefined : deselectArtifact()"
    />
  </div>
</template>

<style scoped>
.ai-chat-box {
  display: flex;
  flex-direction: column;
  height: 100%;
  position: relative;
}

.chat-header-bar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  padding: 4px 12px;
  border-bottom: 1px solid var(--van-border-color, rgba(0,0,0,0.06));
  min-height: 32px;
}
</style>
