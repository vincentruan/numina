<script setup lang="ts">
import { onMounted, onUnmounted, watch, computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { showFailToast, showSuccessToast, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useChatSessionStore } from '@/stores/chatSession'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'
import { useArtifacts } from '@/composables/ai-chat/useArtifacts'
import { useAgentStore } from '@/stores/agent'
import { useFamilyStore } from '@/stores/family'
import { getThread, createThread, branchThreadFromTurn } from '@/api/ai-chat'
import type { WorkspaceCloneMode } from '@/api/ai-chat'
import { accumulateUsage } from '@/utils/ai-chat/token-usage-steps'
import ChatHeader from '@/components/ai/ChatHeader.vue'
import WelcomePage from '@/components/ai/WelcomePage.vue'
import MessageList from '@/components/ai/MessageList.vue'
import InputBox from '@/components/ai-chat/InputBox.vue'
import SuggestionChips from '@/components/ai/SuggestionChips.vue'
import ErrorMessage from '@/components/ai-chat/ErrorMessage.vue'
import ArtifactPreviewPopup from '@/components/ai-chat/ArtifactPreviewPopup.vue'
import AIChatSkeleton from '@/components/ai/AIChatSkeleton.vue'
import TodoListBar from '@/components/ai-chat/TodoListBar.vue'
import GoalStatusBar from '@/components/ai-chat/GoalStatusBar.vue'
import ChatHistoryPage from '@/pages/ChatHistoryPage.vue'
import { useThreadTodos } from '@/composables/ai-chat/useThreadTodos'
import { useActiveGoal } from '@/composables/ai-chat/useActiveGoal'
import { parseGoalCommand } from '@/composables/ai-chat/useThreadChat'
import { INPUT_MODE_CONFIGS } from '@/composables/ai-chat/useTenantAiResources'
import { useAiContext } from '@/composables/useAiContext'
import type { SubmitPayload, InputContext } from '@/types/ai-chat/input-mode'
import { usePageLoading } from '@/composables/usePageLoading'

interface ChatAttachment {
  type: 'file' | 'image'
  name: string
  path?: string
}

const NUMINA_AGENT_NAME = 'numina'
const DEFAULT_MODEL = 'default'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

const store = useChatSessionStore()
const agentStore = useAgentStore()
const familyStore = useFamilyStore()
// A1b (Plan B T6): passive '问 AI' buttons send ?source=&id= to /ai/chat;
// loadContext fetches the entity context to inject as the first user turn.
const { loadContext, contextLabel, clearContext } = useAiContext()
const { increment, decrement } = usePageLoading()

// ── Chat attachments ──
const chatAttachments = ref<ChatAttachment[]>([])

function onAddAttachment(attachment: ChatAttachment) {
  chatAttachments.value.push(attachment)
}

function onRemoveAttachment(index: number) {
  chatAttachments.value.splice(index, 1)
}

// Active agent for ChatHeader
const activeAgent = computed(() => {
  // Default to numina agent
  return agentStore.systemAgents.find(a => a.agent_name === NUMINA_AGENT_NAME) || agentStore.systemAgents[0] || null
})

const chat = useThreadChat()
const {
  selectedArtifact,
  open: artifactPreviewOpen,
  select: selectArtifact,
  deselect: deselectArtifact,
} = useArtifacts()

// U7 (D5 TodoList): derive read-only todo display state from the live todos ref
// owned by useThreadChat. Rendered above InputBox when the agent has todos.
const { todos: todoItems, hasTodos } = useThreadTodos(chat.todos)

// U5 (D1 /goal): reconcile the optimistic /goal-command override with the
// server goal (streamed from checkpoint channel_values["goal"] via useThreadChat
// .serverGoal). GoalStatusBar renders above InputBox (co-located with
// TodoListBar) when hasGoal is true. setLocalGoal applies the optimistic
// override immediately on a successful /goal set so the bar shows before the
// run starts; the override yields to server state once a values chunk carries
// the goal field (use-active-goal.ts:40-44).
const activeThreadIdRef = computed(() => store.activeThreadId ?? null)
const { activeGoal, hasGoal, setLocalGoal } = useActiveGoal(activeThreadIdRef, chat.serverGoal)

/**
 * Realtime token usage computed from SSE values events.
 * accumulateUsage deduplicates by message id and sums input/output tokens
 * across all AI messages. This is the primary data source for the header
 * TokenUsage display - more realtime than the backend /token-usage API
 * (which requires checkpointer write to complete first).
 */
const realtimeTokenUsage = computed(() => {
  const usage = accumulateUsage(chat.messages.value)
  if (!usage) return null
  return {
    inputTokens: usage.inputTokens,
    outputTokens: usage.outputTokens,
    totalTokens: usage.totalTokens,
  }
})

/** Ensure the active thread's metadata (especially title) is in store.sessions.
 *  On page refresh or route navigation, store.sessions is empty and loadHistory
 *  only fetches messages via client.threads.getState - the thread title would
 *  show "新对话" without this fetch. */
async function ensureThreadInSessions(threadId: string) {
  if (store.sessions.find(s => s.thread_id === threadId)) return
  try {
    const thread = await getThread(threadId)
    // Re-check: a concurrent values event may have added it already
    if (!store.sessions.find(s => s.thread_id === threadId)) {
      store.sessions.unshift(thread)
    }
  } catch {
    // Non-critical: title stays as default until next refresh
  }
}

// Initial loading state for skeleton display (during thread creation + first send)
const initialLoading = ref(true)

// History overlay visibility — shown as a modal overlay inside AIChatBox so the
// chat stream is NOT interrupted when the user browses history.
const showHistory = ref(false)

function onOpenHistory() {
  showHistory.value = true
}

function onCloseHistory() {
  showHistory.value = false
}

function onSelectHistoryThread(threadId: string) {
  showHistory.value = false
  // If switching to a different thread while streaming, cancel the current stream first
  if (chat.isLoading.value && store.activeThreadId !== threadId) {
    chat.cancelStream()
  }
  store.setActiveThread(threadId)
}

// Draft text recovered into the welcome InputBox after a failed auto-send /
// submit. AIChatBox passes it to WelcomePage's InputBox as modelValue so the
// user's original text is not lost when handleStartChat throws (e.g. backend
// /api/threads error, network failure). Cleared once a send succeeds.
const draftText = ref<string | undefined>(undefined)

// Inherited web search state: when the chat page is entered from the AI hub
// page, the hub's web search toggle is carried via pendingMessage.webSearch.
// Pass it to the chat InputBox as an explicit initial value so it inherits the
// user's choice instead of re-running the auto-default logic.
const chatWebSearch = ref<boolean | undefined>(undefined)

// Initialize from URL on mount and auto-send pending message if present
onMounted(async () => {
  increment()
  try {
    // Ensure agent data is available for ChatHeader logo. Direct navigation to
    // /ai/chat (page refresh, direct URL, browser back) bypasses AIHubPage which
    // normally loads agents - without this, systemAgents stays empty and the
    // agent logo never renders. Non-blocking: logo appears once the API returns.
    if (agentStore.systemAgents.length === 0) {
      agentStore.loadAgents()
    }
    // Capture the store's active thread before initializeFromUrl possibly changes it.
    // If the ID is unchanged after init (e.g. closing the history overlay back to
    // the same thread), the activeThreadId watcher below won't fire — but this fresh
    // composable instance has empty messages, so we must explicitly load history to
    // avoid a blank page.
    const prevActiveId = store.activeThreadId
    store.initializeFromUrl()
    // A1b (Plan B T6): if a passive button sent ?source=&id=, fetch the entity
    // context and inject it as the first user turn. This is a DIFFERENT query
    // param from the pendingMessage 'q' path below; if A1b yields a message we
    // send it and skip the pendingMessage block (no double-send). Guard the
    // await on the source param so the no-context path stays synchronous (no
    // extra microtask that would delay initialLoading=false past one tick).
    // Only trigger for valid A1b entity sources — 'system_default' (from
    // AIHubPage's handleNuminaConsult) is NOT an A1b source and must not
    // call /ai/context (which would 400 and toast "上下文加载失败").
    const A1B_SOURCES = new Set(['liability_detail', 'wish_detail', 'liability_strategy', 'wish_advice'])
    if (route.query.source && A1B_SOURCES.has(route.query.source as string)) {
      const a1bContext = await loadContext()
      if (a1bContext) {
        if (!familyStore.family) {
          try {
            await familyStore.fetchFamily()
          } catch {
            // fetchFamily failure is non-fatal — handleStartChat surfaces a toast.
          }
        }
        const mode: 'flash' | 'thinking' | 'pro' | 'ultra' = 'pro'
        const modeConfig = INPUT_MODE_CONFIGS[mode]
        await handleStartChat({
          text: a1bContext,
          model_name: DEFAULT_MODEL,
          mode,
          thinking_enabled: modeConfig.thinking_enabled,
          is_plan_mode: modeConfig.is_plan_mode,
          subagent_enabled: modeConfig.subagent_enabled,
          reasoning_effort: modeConfig.reasoning_effort,
        })
        return
      }
    }
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
      // NOTE: do NOT clear pendingMessage here. It is cleared only after the
      // send actually connects (handleStartChat success path). Clearing early
      // meant that if handleStartChat threw (family race, /api/threads error,
      // network) the message was gone for good — a cold reload would not
      // re-send it. Deferring keeps it available for a re-mount retry, and
      // draftText (fix #2) restores the visible input for an immediate retry.
      // Inherit the hub page's web search toggle into the chat InputBox
      if (msg.webSearch !== undefined) {
        chatWebSearch.value = msg.webSearch
      }
      // Wait for family data before auto-sending. createThread →
      // getAgentHeaders() (api/ai-chat.ts) needs familyStore.family?.id (or
      // authStore.user.family_id, restored by App.vue's fetchMe()). App.vue /
      // MainLayout fire fetchFamily() on mount but do not await it, so on first
      // entry to /ai/chat the family id can still be unset when handleStartChat
      // runs — which threw "Family not loaded" and dropped the user's text.
      // Awaiting here closes that race for the auto-send path.
      if (!familyStore.family) {
        try {
          await familyStore.fetchFamily()
        } catch {
          // fetchFamily failure is non-fatal here — handleStartChat will surface
          // a send-failed toast and draftText recovery kicks in below.
        }
      }
      // Construct complete SubmitPayload with mode config values
      const mode: 'flash' | 'thinking' | 'pro' | 'ultra' = msg.deepThink ? 'thinking' : 'pro'
      const modeConfig = INPUT_MODE_CONFIGS[mode]
      await handleStartChat({
        text: msg.text,
        model_name: DEFAULT_MODEL,
        mode,
        thinking_enabled: modeConfig.thinking_enabled,
        is_plan_mode: modeConfig.is_plan_mode,
        subagent_enabled: modeConfig.subagent_enabled,
        reasoning_effort: modeConfig.reasoning_effort,
        websearch_enabled: msg.webSearch,
      }, msg.source)
      // handleStartChat completes after thread creation + send starts streaming
      // Skeleton will be hidden once streaming begins (isLoading becomes true)
    } else {
      // No pending message: hide skeleton immediately
      initialLoading.value = false
    }
  } finally {
    decrement()
  }
})

// Cleanup on unmount
onUnmounted(() => {
  // #8: cancel any in-flight stream + retry loop so the for-await and retry
  // timers don't keep mutating refs / firing network requests for up to 120s
  // after navigation away from the chat page.
  chat.cancelStream()
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

async function handleStartChat(payload: SubmitPayload, source?: string) {
  try {
    const thread = await createThread(source)
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
      websearch_enabled: payload.websearch_enabled,
    }, source)
    // Send started successfully — clear the one-shot pending message (so a
    // re-mount does not re-send) and any recovered draft so it doesn't linger
    // in the (now-hidden) welcome InputBox on a later new-chat.
    store.pendingMessage = null
    draftText.value = undefined
  } catch {
    skipNextHistoryLoadFor.value = null
    initialLoading.value = false
    showFailToast(t('aiChat.sendFailed'))
    // Recover the user's text only when we never left welcome mode — i.e.
    // createThread failed before setActiveThread ran. In that case
    // activeThreadId is still null and the welcome InputBox is mounted, so
    // seeding draftText (bound as its modelValue) restores the typed text for
    // the user to retry. If sendMessage failed after thread creation, the user
    // is already in chat mode with the message as an optimistic bubble and a
    // retry button (useThreadChat marks the last AI message error) — re-seeding
    // draftText there would create a stray duplicate in the hidden welcome box.
    if (!store.activeThreadId) {
      draftText.value = payload.text
    }
  }
}

async function handleSendMessage(payload: SubmitPayload) {
  if (!store.activeThreadId) return
  // U5 (D1 /goal): intercept the /goal slash command. U1's slash palette fills
  // `/goal ` for palette selection (apply returns handled=false), so a typed
  // `/goal <condition>` arrives here verbatim on submit — parse it and route to
  // the three-state branch (set / status / clear). Only `set` starts a run, and
  // only when the PUT succeeded (input-box.tsx:947-963): the objective is then
  // submitted as the next user task. Status/clear never start a run.
  const goalCommand = parseGoalCommand(payload.text)
  if (goalCommand) {
    const saved = await chat.handleGoalCommand(
      store.activeThreadId,
      goalCommand,
      (goal) => setLocalGoal(goal ?? null),
    )
    if (saved && goalCommand.kind === 'set') {
      await chat.sendMessage(payload.text, payload.mode, store.activeThreadId, {
        thinking_enabled: payload.thinking_enabled,
        is_plan_mode: payload.is_plan_mode,
        subagent_enabled: payload.subagent_enabled,
        reasoning_effort: payload.reasoning_effort,
        websearch_enabled: payload.websearch_enabled,
      })
    }
    return
  }
  // U6: intercept the /compact slash command. U1's slash palette resolves
  // /compact via onSubmit('/compact') (apply returns handled=true), so the
  // text arrives here verbatim — do NOT send it to the agent as a user
  // message; instead trigger the compact flow on the current thread.
  if (payload.text.trim() === '/compact') {
    await chat.handleCompact(store.activeThreadId)
    return
  }
  await chat.sendMessage(payload.text, payload.mode, store.activeThreadId, {
    thinking_enabled: payload.thinking_enabled,
    is_plan_mode: payload.is_plan_mode,
    subagent_enabled: payload.subagent_enabled,
    reasoning_effort: payload.reasoning_effort,
    websearch_enabled: payload.websearch_enabled,
  }, undefined, undefined, payload.files)
  // Clear attachments after successful send
  chatAttachments.value = []
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

async function handleFeedback(messageId: string, value: 1 | -1) {
  if (!store.activeThreadId) return
  await chat.submitFeedback(store.activeThreadId, messageId, value)
}

function handleContextChange(_context: InputContext) {
  // Handle context changes if needed
}

async function handleSuggestionClick(text: string) {
  if (!store.activeThreadId || chat.isLoading.value) return
  chat.suggestions.value = []
  // Also clear per-message suggestions on the last AI message so the inline
  // chips don't remain visible after the user has clicked one and a new
  // round starts. Without this, the old suggestion chips stay rendered
  // inside the previous AI message bubble.
  const lastAiIdx = chat.messages.value.findLastIndex(m => m.type === 'ai')
  if (lastAiIdx >= 0) {
    const msg = chat.messages.value[lastAiIdx]
    if (msg.suggestions) {
      chat.messages.value = [
        ...chat.messages.value.slice(0, lastAiIdx),
        { ...msg, suggestions: undefined },
        ...chat.messages.value.slice(lastAiIdx + 1),
      ]
    }
  }
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
  chat.clearMessages()
  store.clearActiveThread()
  // Clear any recovered draft so a previous failed send's text doesn't
  // reappear in the fresh welcome InputBox.
  draftText.value = undefined
}

// Branch conversation state and handler
const branchingMessageId = ref<string | null>(null)
const canBranch = computed(() => !!store.activeThreadId && !chat.isLoading.value)

async function handleBranch(messageId: string, messageIds: string[]) {
  if (!store.activeThreadId || branchingMessageId.value) return

  branchingMessageId.value = messageId
  try {
    const response = await branchThreadFromTurn(store.activeThreadId, {
      messageId,
      messageIds,
    })
    showSuccessToast(t('aiChat.branchSuccess'))
    // U5: when the sandbox artifact clone did not fully succeed, surface a
    // non-blocking warning so the user knows why some files (e.g. reports)
    // may be missing in the branch. The branch itself is still created.
    const cloneWarnKey = branchCloneWarnKey(response.workspace_clone_mode)
    if (cloneWarnKey) {
      // Vant 4 ToastType is text|loading|success|fail — 'warning' is invalid
      // and renders no icon. Use icon: 'warning-o' per frontend/CLAUDE.md
      // §Key Invariants (cf. ChangePasswordPage.vue).
      showToast({ message: t(cloneWarnKey), icon: 'warning-o' })
    }
    // Navigate to the new branch thread
    router.push({ name: 'AIChat', query: { thread_id: response.thread_id } })
  } catch (error) {
    const message = error instanceof Error ? error.message : t('aiChat.branchFailed')
    showFailToast(message)
  } finally {
    branchingMessageId.value = null
  }
}

/**
 * U5: map workspace_clone_mode to an i18n warning key, or undefined for success.
 * The mode is typed as WorkspaceCloneMode so an unhandled new value is a
 * compile-time break, not a silent fall-through to the success branch.
 */
function branchCloneWarnKey(mode?: WorkspaceCloneMode): string | undefined {
  switch (mode) {
    case 'skipped_historical_turn': return 'aiChat.branchCloneSkippedHistorical'
    case 'not_found': return 'aiChat.branchCloneNotFound'
    case 'failed': return 'aiChat.branchCloneFailed'
    default: return undefined
  }
}

/**
 * Handle clarification submit from HumanInputCard.
 * Sends the answer as a new HumanMessage with human_input_response (DeerFlow
 * ClarificationMiddleware pattern) - NOT a resume endpoint.
 */
async function handleClarificationSubmit(payload: { threadId: string; interruptId: string; answer: string }) {
  await chat.submitClarification(payload.threadId, payload.interruptId, payload.answer)
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
        :realtime-token-usage="realtimeTokenUsage"
        :is-streaming="chat.isLoading.value"
        @title-updated="handleTitleUpdated"
        @new-chat="handleNewChat"
        @history="onOpenHistory"
      />

      <template v-if="store.isWelcomeMode">
        <!-- WelcomePage includes its own InputBox (DeerFlow pattern) -->
        <WelcomePage
          :model-value="draftText"
          :agent-id="activeAgent?.id"
          :agents="activeAgent ? [{ id: activeAgent.id, display_name: activeAgent.display_name, agent_name: activeAgent.agent_name, icon: activeAgent.icon, color: activeAgent.color, description: activeAgent.description }] : []"
          :agent-icon="activeAgent?.icon"
          :agent-label="activeAgent?.display_name"
          readonly
          @start-chat="handleStartChat"
        />
      </template>
      <template v-else>
        <MessageList
          :messages="chat.visibleMessages.value"
          :is-streaming="chat.isLoading.value"
          :thread-id="store.activeThreadId || undefined"
          :can-branch="canBranch"
          :branching-message-id="branchingMessageId"
          :answered-interrupt-ids="chat.answeredInterruptIds.value"
          @retry="handleRetry"
          @stop="handleStopStream"
          @suggestion-click="handleSuggestionClick"
          @artifact-tap="handleArtifactTap"
          @branch="handleBranch"
          @clarification-submit="handleClarificationSubmit"
          @feedback="handleFeedback"
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
      <!-- A1b (Plan B T6): removable tag showing injected entity context -->
      <div v-if="contextLabel" class="context-tag">
        <span>{{ contextLabel }}</span>
        <van-icon name="cross" @click="clearContext" />
      </div>
      <!-- InputBox only in chat mode (WelcomePage has its own in welcome mode) -->
      <!-- U7 (D5 TodoList): read-only todo list above InputBox when the agent
           has written todos via write_todos (plan_mode). Co-located with the
           U5 GoalStatusBar position. -->
      <TodoListBar v-if="hasTodos" :todos="todoItems" />
      <!-- U5 (D1 /goal): active-goal status bar above InputBox. Renders the
           optimistic override (immediate, on /goal set) reconciled with the
           server goal streamed from the checkpoint. The continuation chip
           `续跑中 N/8` shows only when continuation_count > 0 (U4 auto-run). -->
      <GoalStatusBar v-if="hasGoal && activeGoal" :goal="activeGoal" />
      <InputBox
        :status="chat.isLoading.value ? 'streaming' : 'ready'"
        :is-welcome-mode="false"
        :thread-id="store.activeThreadId || undefined"
        :web-search="chatWebSearch"
        :agent-id="activeAgent?.id"
        :agents="activeAgent ? [{ id: activeAgent.id, display_name: activeAgent.display_name, agent_name: activeAgent.agent_name, icon: activeAgent.icon, color: activeAgent.color, description: activeAgent.description }] : []"
        :agent-icon="activeAgent?.icon"
        :agent-label="activeAgent?.display_name"
        :attachments="chatAttachments"
        @submit="handleSendMessage"
        @stop="handleStop"
        @context-change="handleContextChange"
        @add-attachment="onAddAttachment"
        @remove-attachment="onRemoveAttachment"
      />
    </template>

    <!-- History overlay (modal, does not interrupt streaming) -->
    <ChatHistoryPage
      v-if="showHistory"
      :overlay="true"
      @close="onCloseHistory"
      @select-thread="onSelectHistoryThread"
    />

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

/* A1b (Plan B T6): injected-entity-context removable tag */
.context-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 4px 12px;
  padding: 4px 10px;
  background: var(--color-primary-soft, rgba(99, 102, 241, 0.1));
  color: var(--color-primary, #6366f1);
  border-radius: 12px;
  font-size: 12px;
  width: fit-content;
}
.context-tag .van-icon {
  cursor: pointer;
  font-size: 14px;
}
</style>