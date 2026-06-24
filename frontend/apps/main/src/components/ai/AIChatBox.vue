<script setup lang="ts">
import { onMounted, onUnmounted, watch, computed } from 'vue'
import { showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'
import { useArtifacts } from '@/composables/ai-chat/useArtifacts'
import { useAgentStore } from '@/stores/agent'
import { getThread, createThread } from '@/api/ai-chat'
import ChatHeader from '@/components/ai/ChatHeader.vue'
import WelcomePage from '@/components/ai/WelcomePage.vue'
import MessageList from '@/components/ai/MessageList.vue'
import InputBox from '@/components/ai-chat/InputBox.vue'
import SuggestionChips from '@/components/ai/SuggestionChips.vue'
import ArtifactPreviewPopup from '@/components/ai-chat/ArtifactPreviewPopup.vue'
import type { SubmitPayload, InputContext } from '@/types/ai-chat/input-mode'

const NUMINA_AGENT_NAME = 'numina'

const { t } = useI18n()

const store = useChatSessionStore()
const agentStore = useAgentStore()

// Active agent for ChatHeader
const activeAgent = computed(() => {
  // Default to numina agent
  return agentStore.systemAgents.find(a => a.agent_name === NUMINA_AGENT_NAME) || agentStore.systemAgents[0] || null
})

const chat = useThreadChat({
  onStreamEnd: scheduleTitleRefresh,
})
const {
  selectedArtifact,
  open: artifactPreviewOpen,
  select: selectArtifact,
  deselect: deselectArtifact,
} = useArtifacts()

/** Title generation is async on the backend — poll twice after stream ends */
const titleRefreshTimeouts = new Set<ReturnType<typeof setTimeout>>()

function scheduleTitleRefresh(threadId: string) {
  const doRefresh = async () => {
    // Guard: skip if user switched threads
    if (store.activeThreadId !== threadId) return
    try {
      const thread = await getThread(threadId)
      if (thread.title && store.activeThreadId === threadId) {
        // Update store sessions if this thread is tracked there
        const idx = store.sessions.findIndex(s => s.thread_id === threadId)
        if (idx !== -1) {
          store.sessions[idx] = { ...store.sessions[idx], title: thread.title }
        }
      }
    } catch {
      // Title may not be ready yet — ignore
    }
  }
  // First attempt after 3s, second after 8s (title gen can take a few seconds)
  const timeout1 = setTimeout(() => {
    titleRefreshTimeouts.delete(timeout1)
    doRefresh()
  }, 3000)
  titleRefreshTimeouts.add(timeout1)
  const timeout2 = setTimeout(() => {
    titleRefreshTimeouts.delete(timeout2)
    doRefresh()
  }, 8000)
  titleRefreshTimeouts.add(timeout2)
}

function cancelTitleRefresh() {
  titleRefreshTimeouts.forEach(id => clearTimeout(id))
  titleRefreshTimeouts.clear()
}

// Initialize from URL on mount
onMounted(() => {
  store.initializeFromUrl()
})

// Cleanup on unmount
onUnmounted(() => {
  cancelTitleRefresh()
})

// Watch for thread switches — load history
watch(
  () => store.activeThreadId,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      // Cancel pending title refreshes for old thread
      cancelTitleRefresh()
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

// Handle title update from ChatHeader
function handleTitleUpdated(threadId: string, newTitle: string) {
  const idx = store.sessions.findIndex(s => s.thread_id === threadId)
  if (idx !== -1) {
    store.sessions[idx] = { ...store.sessions[idx], title: newTitle }
  }
}

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

function handleStop() {
  chat.cancelStream()
}

async function handleRetry() {
  if (store.activeThreadId) {
    await chat.retry(store.activeThreadId)
  }
}

function handleContextChange(_context: InputContext) {
  // Handle context changes if needed
}

async function handleSuggestionClick(text: string) {
  if (!store.activeThreadId) return
  chat.suggestions.value = []
  await chat.sendMessage(text, undefined, store.activeThreadId)
}

const VALID_ARTIFACT_KINDS = ['data', 'link', 'image', 'file', 'other', 'report'] as const
type ArtifactKind = typeof VALID_ARTIFACT_KINDS[number]

function handleArtifactTap(artifact: { id: string; title: string; kind: string; url?: string; path?: string }) {
  // Validate kind before casting
  const kind: ArtifactKind = VALID_ARTIFACT_KINDS.includes(artifact.kind as ArtifactKind)
    ? artifact.kind as ArtifactKind
    : 'other'
  selectArtifact({ ...artifact, kind })
}

function handleNewChat() {
  store.clearActiveThread()
}
</script>

<template>
  <div class="ai-chat-box">
    <!-- Header bar -->
    <ChatHeader
      :active-thread-id="store.activeThreadId"
      :sessions="store.sessions"
      :token-usage-total="chat.tokenUsage.value?.total_tokens"
      :active-agent="activeAgent"
      @title-updated="handleTitleUpdated"
      @new-chat="handleNewChat"
    />

    <template v-if="store.isWelcomeMode">
      <!-- WelcomePage includes its own InputBox (DeerFlow pattern) -->
      <WelcomePage @start-chat="handleStartChat" />
    </template>
    <template v-else>
      <MessageList
        :messages="chat.messages.value"
        :is-streaming="chat.isLoading.value"
        :thread-id="store.activeThreadId || undefined"
        :planning-steps="chat.planningSteps.value"
        @retry="handleRetry"
        @stop="handleStopStream"
        @suggestion-click="handleSuggestionClick"
        @artifact-tap="handleArtifactTap"
      />
      <!-- Suggestion chips above input (from SSE custom events) -->
      <SuggestionChips
        v-if="!chat.isLoading.value && chat.suggestions.value.length > 0"
        :suggestions="chat.suggestions.value"
        @select="handleSuggestionClick"
      />
      <!-- InputBox only in chat mode (WelcomePage has its own in welcome mode) -->
      <InputBox
        :status="chat.isLoading.value ? 'streaming' : 'ready'"
        :is-welcome-mode="false"
        :thread-id="store.activeThreadId || undefined"
        @submit="handleSendMessage"
        @stop="handleStop"
        @context-change="handleContextChange"
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
  position: fixed;
  inset: 0;
  bottom: calc(50px + env(safe-area-inset-bottom));
  background: var(--van-background, #f7f8fa);
  z-index: 10;
}

/* Dark mode */
:global([data-theme='dark']) .ai-chat-box {
  background: var(--bg-primary);
}
</style>