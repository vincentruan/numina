<script setup lang="ts">
import { onMounted, onUnmounted, watch, computed, ref } from 'vue'
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
import ErrorMessage from '@/components/ai-chat/ErrorMessage.vue'
import ArtifactPreviewPopup from '@/components/ai-chat/ArtifactPreviewPopup.vue'
import AIChatSkeleton from '@/components/ai/AIChatSkeleton.vue'
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
      // Skip empty titles and the raw [SKILL:chat] prompt wrapper (sync
      // after_model fallback) - wait for the LLM-generated title.
      if (!thread.title || thread.title.startsWith('[SKILL:')) return
      if (store.activeThreadId !== threadId) return
      const idx = store.sessions.findIndex(s => s.thread_id === threadId)
      if (idx !== -1) {
        store.sessions[idx] = { ...store.sessions[idx], title: thread.title }
      } else {
        // New thread not yet in sessions list (e.g. created from /ai page)
        store.sessions.unshift(thread)
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
  // Third attempt at 15s - safety margin for slow LLM title generation
  const timeout3 = setTimeout(() => {
    titleRefreshTimeouts.delete(timeout3)
    doRefresh()
  }, 15000)
  titleRefreshTimeouts.add(timeout3)
}

function cancelTitleRefresh() {
  titleRefreshTimeouts.forEach(id => clearTimeout(id))
  titleRefreshTimeouts.clear()
}

/** Ensure the active thread's metadata (especially title) is in store.sessions.
 *  On page refresh or route navigation, store.sessions is empty and loadHistory
 *  only fetches messages via client.threads.getState - the thread title would
 *  show "新对话" without this fetch. */
async function ensureThreadInSessions(threadId: string) {
  if (store.sessions.find(s => s.thread_id === threadId)) return
  try {
    const thread = await getThread(threadId)
    // Re-check: a concurrent scheduleTitleRefresh may have added it already
    if (!store.sessions.find(s => s.thread_id === threadId)) {
      store.sessions.unshift(thread)
    }
  } catch {
    // Non-critical: title stays as default until next refresh
  }
}

// Initial loading state for skeleton display (during thread creation + first send)
const initialLoading = ref(true)

// Inherited web search state: when the chat page is entered from the AI hub
// page, the hub's web search toggle is carried via pendingMessage.webSearch.
// Pass it to the chat InputBox as an explicit initial value so it inherits the
// user's choice instead of re-running the auto-default logic.
const chatWebSearch = ref<boolean | undefined>(undefined)

// Initialize from URL on mount and auto-send pending message if present
onMounted(async () => {
  // Ensure agent data is available for ChatHeader logo. Direct navigation to
  // /ai/chat (page refresh, direct URL, browser back) bypasses AIHubPage which
  // normally loads agents - without this, systemAgents stays empty and the
  // agent logo never renders. Non-blocking: logo appears once the API returns.
  if (agentStore.systemAgents.length === 0) {
    agentStore.loadAgents()
  }
  // Capture the store's active thread before initializeFromUrl possibly changes it.
  // If the ID is unchanged after init (e.g. returning from /ai/chat/history to
  // the same thread, or closing history back to /ai/chat), the activeThreadId
  // watcher below won't fire — but this fresh composable instance has empty
  // messages, so we must explicitly load history to avoid a blank page.
  const prevActiveId = store.activeThreadId
  store.initializeFromUrl()
  if (
    store.activeThreadId
    && store.activeThreadId === prevActiveId
    && !store.pendingMessage
  ) {
    // Existing thread: load history and hide skeleton immediately
    chat.loadHistory(store.activeThreadId)
    // Watcher won't fire (same ID) - fetch thread metadata here too.
    ensureThreadInSessions(store.activeThreadId)
    initialLoading.value = false
  }
  // Auto-send pending message from URL (passed from AIHubPage)
  if (store.pendingMessage) {
    const msg = store.pendingMessage
    store.pendingMessage = null // clear so it only fires once
    // Inherit the hub page's web search toggle into the chat InputBox
    if (msg.webSearch !== undefined) {
      chatWebSearch.value = msg.webSearch
    }
    await handleStartChat({ text: msg.text, mode: msg.deepThink ? 'thinking' : 'pro' })
    // handleStartChat completes after thread creation + send starts streaming
    // Skeleton will be hidden once streaming begins (isLoading becomes true)
  } else {
    // No pending message: hide skeleton immediately
    initialLoading.value = false
  }
})

// Cleanup on unmount
onUnmounted(() => {
  // #8: cancel any in-flight stream + retry loop so the for-await and retry
  // timers don't keep mutating refs / firing network requests for up to 120s
  // after navigation away from the chat page.
  chat.cancelStream()
  cancelTitleRefresh()
})

// When handleStartChat creates a new thread and calls setActiveThread, the
// activeThreadId watcher below fires loadHistory → cancelStream. If this runs
// after sendMessage has started its stream, cancelStream aborts the in-flight
// run (userCancelled=true → silent break, no retry) and the thread is left as
// an empty shell — the blank-page bug. Set this flag before setActiveThread so
// the watcher skips exactly one loadHistory for the thread we are about to
// stream into; sendMessage already manages that thread's messages.
const skipNextHistoryLoadFor = ref<string | null>(null)

// Watch for thread switches — load history
watch(
  () => store.activeThreadId,
  async (newId, oldId) => {
    if (newId && newId !== oldId) {
      if (skipNextHistoryLoadFor.value === newId) {
        skipNextHistoryLoadFor.value = null
        return
      }
      // Cancel pending title refreshes for old thread
      cancelTitleRefresh()
      // Load messages and thread metadata in parallel - loadHistory only
      // fetches checkpoint messages, ensureThreadInSessions fetches the title.
      await Promise.all([
        chat.loadHistory(newId),
        ensureThreadInSessions(newId),
      ])
    }
  }
)

// Persistent error bar message (shown after retries exhausted, cleared on new message)
const errorBarMessage = ref<string | null>(null)

// Handle errors from chat
watch(
  () => chat.error.value,
  (err) => {
    if (err) {
      showFailToast(err)
      errorBarMessage.value = t('aiChat.connectionBrokenRetry')
    } else {
      errorBarMessage.value = null
    }
  }
)

// Clear error bar when a new message is sent successfully
watch(
  () => chat.isLoading.value,
  (loading, prevLoading) => {
    if (prevLoading && !loading && !chat.error.value) {
      errorBarMessage.value = null
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
    // Mark this thread so the activeThreadId watcher skips loadHistory for it
    // — sendMessage below will stream into it, and a concurrent loadHistory
    // would cancelStream-abort the run (see skipNextHistoryLoadFor comment).
    skipNextHistoryLoadFor.value = thread.thread_id
    store.setActiveThread(thread.thread_id)
    // Add to sessions so ChatHeader can display the title once generated
    if (!store.sessions.find(s => s.thread_id === thread.thread_id)) {
      store.sessions.unshift(thread)
    }
    // Hide skeleton once thread is created - streaming will show actual content
    initialLoading.value = false
    await chat.sendMessage(payload.text, payload.mode, thread.thread_id, {
      thinking_enabled: payload.thinking_enabled,
      is_plan_mode: payload.is_plan_mode,
      subagent_enabled: payload.subagent_enabled,
      reasoning_effort: payload.reasoning_effort,
    })
  } catch {
    skipNextHistoryLoadFor.value = null
    initialLoading.value = false
    showFailToast(t('aiChat.sendFailed'))
  }
}

async function handleSendMessage(payload: SubmitPayload) {
  if (!store.activeThreadId) return
  await chat.sendMessage(payload.text, payload.mode, store.activeThreadId, {
    thinking_enabled: payload.thinking_enabled,
    is_plan_mode: payload.is_plan_mode,
    subagent_enabled: payload.subagent_enabled,
    reasoning_effort: payload.reasoning_effort,
  })
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
  if (!store.activeThreadId || chat.isLoading.value) return
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
    <!-- Skeleton for initial loading (thread creation + first message) -->
    <AIChatSkeleton v-if="initialLoading" />

    <!-- Actual Content -->
    <template v-else>
      <!-- Header bar -->
      <ChatHeader
        :active-thread-id="store.activeThreadId"
        :sessions="store.sessions"
        :token-usage-total="chat.tokenUsage.value?.total_tokens"
        :is-streaming="chat.isLoading.value"
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
      <!-- Connection error bar (after SSE retry exhaustion) -->
      <ErrorMessage
        v-if="errorBarMessage"
        :message="errorBarMessage"
        :show-retry="true"
        @retry="handleRetry"
      />
      <!-- InputBox only in chat mode (WelcomePage has its own in welcome mode) -->
      <InputBox
        :status="chat.isLoading.value ? 'streaming' : 'ready'"
        :is-welcome-mode="false"
        :thread-id="store.activeThreadId || undefined"
        :web-search="chatWebSearch"
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
    </template>
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