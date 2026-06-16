<template>
  <div class="ai-chat-page" :class="{ 'theme-light': isLight }">
    <!-- Fixed top bar: [back] [history] [agent-logo] [title+edit] [new chat] -->
    <div class="chat-header">
      <button class="header-btn" :aria-label="t('common.back')" @click="router.back()">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      <button class="header-btn" :aria-label="t('aiChat.historyAria')" @click="showHistory = true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <!-- Agent logo button — shows popup with name + description on click -->
      <button
        v-if="activeAgent && !activeAgentLoading"
        class="header-btn header-agent-logo-btn"
        :aria-label="t('aiChat.agentInfoAria')"
        @click="onToggleAgentInfo"
      >
        <NuminaLogo v-if="activeAgent.agent_name === NUMINA_AGENT_NAME" :width="20" />
        <span v-else class="header-agent-logo-emoji">{{ activeAgent.icon || '🤖' }}</span>
      </button>
      <van-skeleton v-if="activeAgentLoading" :row="1" row-width="44px" class="header-agent-skeleton" />
      <!-- Title wrap: title (truncated) + inline edit button -->
      <div class="header-title-wrap">
        <h1 class="header-title">{{ truncatedTitle }}</h1>
        <button
          v-if="sessionTitle && sessionTitle !== t('aiChat.newChat')"
          class="header-edit-btn"
          :aria-label="t('aiChat.editTitle')"
          @click="onEditTitle"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
      </div>
      <!-- Agent info popup — floating below agent button -->
      <div
        v-if="showAgentInfo && activeAgent"
        class="agent-info-backdrop"
        @click="showAgentInfo = false"
      />
      <div
        v-if="showAgentInfo && activeAgent"
        class="agent-info-popup"
      >
        <div class="agent-info-header">
          <span class="agent-info-icon" aria-hidden="true">
            <NuminaLogo v-if="activeAgent.agent_name === NUMINA_AGENT_NAME" :width="24" />
            <span v-else>{{ activeAgent.icon || '🤖' }}</span>
          </span>
          <span class="agent-info-name">{{ activeAgent.display_name }}</span>
        </div>
        <p class="agent-info-description">{{ activeAgent.description || t('aiChat.agentNoDescription') }}</p>
      </div>
      <div class="header-actions">
        <button class="header-btn" :aria-label="t('aiChat.newChatAria')" @click="onNewChat">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- History sidebar drawer -->
    <van-popup
      v-model:show="showHistory"
      position="left"
      :style="{ width: '66%', height: '100%' }"
      :destroy-on-close="true"
      :close-on-click-overlay="true"
    >
      <div class="history-panel">
        <div class="history-header">
          <button class="header-btn" :aria-label="t('aiChat.backAria')" @click="showHistory = false">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
          </button>
          <span class="history-title">{{ t('aiChat.historyTitle') }}</span>
        </div>
        <!-- Agent filter tabs -->
        <div class="history-filter">
          <button
            v-for="f in agentFilters"
            :key="f.value ?? 'all'"
            class="filter-tab"
            :class="{ 'filter-tab--active': f.value === null ? selectedAgentId === 'all' : selectedAgentId === f.value }"
            @click="onSelectAgent(f.value)"
          >{{ f.label }}</button>
        </div>
        <div v-if="sessionsLoading" class="history-empty">
          <p>{{ t('aiChat.loadingHistory') }}</p>
        </div>
        <div v-else-if="sessions.length === 0" class="history-empty">
          <p>{{ t('aiChat.noHistory') }}</p>
          <p class="history-hint">{{ t('aiChat.historyHint') }}</p>
        </div>
        <div v-else ref="historyScrollRef" class="history-scroll">
          <template v-for="group in groupedSessions" :key="group.label">
            <div class="history-group-label">{{ group.label }}</div>
            <ul class="history-list">
              <li
                v-for="session in group.sessions"
                :key="session.session_id"
                class="history-item"
                :class="{ 'history-item--active': session.session_id === currentSessionId }"
                @click="loadSessionMessages(session)"
              >
                <span class="history-item-title">{{ session.title ?? t('aiChat.untitledSession') }}</span>
                <button
                  class="history-item-menu-btn"
                  :aria-label="t('aiChat.moreActionsAria')"
                  @click.stop="openSessionMenu(session, $event)"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                  </svg>
                </button>
              </li>
            </ul>
          </template>
          <!-- Pagination sentinel -->
          <div ref="paginationSentinelRef" class="history-pagination-sentinel">
            <span v-if="sessionsLoadingMore" class="history-load-more-text">{{ t('aiChat.loadingMore') }}</span>
            <span v-else-if="sessionsAllLoaded" class="history-load-more-text">{{ t('aiChat.noMoreSessions') }}</span>
          </div>
        </div>

        <!-- Session context menu — inside popup to share stacking context -->
        <div
          v-if="sessionMenu.visible"
          class="session-menu-backdrop"
          @click="closeSessionMenu"
        />
        <div
          v-if="sessionMenu.visible"
          class="session-menu"
          :style="{ top: sessionMenu.y + 'px', left: sessionMenu.x + 'px' }"
        >
      <button class="session-menu-item" @click="onRenameSession">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
        <span>{{ t('aiChat.renameSession') }}</span>
      </button>
      <button class="session-menu-item" @click="onTogglePinSession">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/>
        </svg>
        <span>{{ sessionMenu.session?.is_pinned ? t('aiChat.unpinSession') : t('aiChat.pinSession') }}</span>
      </button>
      <button class="session-menu-item session-menu-item--danger" @click="onDeleteSession">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
        </svg>
        <span>{{ t('aiChat.deleteSession') }}</span>
      </button>
        </div>
        <!-- /session-menu -->
      </div>
    </van-popup>

    <!-- Rename session dialog -->
    <van-dialog
      v-model:show="showRenameDialog"
      :title="t('aiChat.renameSession')"
      show-cancel-button
      @confirm="onConfirmRename"
      @cancel="showRenameDialog = false"
    >
      <div style="padding: 16px 16px 8px">
        <van-field
          v-model="renameInput"
          :placeholder="t('aiChat.editTitlePlaceholder')"
          autofocus
          clearable
          maxlength="50"
          show-word-limit
        />
      </div>
    </van-dialog>

    <!-- Chat body -->
    <div ref="scrollRef" class="chat-body">

      <!-- Empty state: placeholder for InputBox welcome mode -->
      <!-- InputBox.vue handles the hero section in isWelcomeMode -->
      <div v-if="!messages.length" class="chat-empty-placeholder" />

      <!-- Messages -->
      <template v-else>
        <!-- DeerFlow MessageGroup-based rendering -->
        <transition-group name="msg" tag="div" class="msg-list">
          <MessageGroup
            v-for="group in messageGroups"
            :key="group.id || `group-${group.type}-${group.messages[0]?.id}`"
            :group="group"
            :is-loading="asking || connecting"
            :thread-id="currentSessionId"
            @retry="onRetryError(messages.findIndex(m => m.id === group.messages[0]?.id))"
            @copy="onCopy"
            @feedback="(mid, v) => onFeedback(mid, v)"
            @suggestion-click="onSuggestionChipClick"
            @artifact-tap="onArtifactTap"
          />
        </transition-group>
      </template>
    </div>

    <!-- Artifact badge (U5) — floating button showing artifact count -->
    <AiArtifactBadge
      :count="sessionArtifacts.length"
      @tap="showArtifactSheet = true"
    />

    <!-- Artifact sheet (U5) — bottom-sheet listing all session artifacts -->
    <AiArtifactSheet
      :visible="showArtifactSheet"
      :artifacts="sessionArtifacts"
      @close="showArtifactSheet = false"
      @artifact-tap="onArtifactTap"
    />

    <!-- Scroll-to-bottom floating button: shown when user scrolled up during streaming -->
    <transition name="scroll-btn">
      <button
        v-if="isUserScrolledUp"
        class="scroll-to-bottom-btn"
        :aria-label="t('aiChat.scrollToBottom')"
        @click="onScrollToBottom"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
        <span>{{ t('aiChat.scrollToBottom') }}</span>
      </button>
    </transition>

    <!-- Suggestions for follow-up (Phase 7) — DeerFlow-aligned -->
    <Suggestions
      v-if="messages.length > 0"
      :suggestions="followups"
      :loading="followupsLoading"
      :hidden="followupsHidden"
      @select="handleSuggestionClick"
      @hide="hideSuggestions"
    />

    <!-- Suggestion confirm dialog for non-empty input — DeerFlow-aligned -->
    <SuggestionConfirmDialog
      :show="confirmOpen"
      :current-input="inputText"
      :suggestion="pendingSuggestion || ''"
      @update:show="confirmOpen = $event"
      @append="confirmAppendAndSend(); onSend()"
      @replace="confirmReplaceAndSend(); onSend()"
    />

    <!-- Input bar — DeerFlow-aligned (Phase 2) -->
    <div class="input-bar">
      <InputBox
        :status="reconnecting ? 'reconnecting' : asking ? 'streaming' : connecting ? 'submitted' : 'ready'"
        :is-welcome-mode="messages.length === 0"
        :thread-id="currentSessionId"
        :initial-mode="inputMode"
        :initial-model-name="modelName"
        @submit="onDeerFlowSubmit"
        @stop="onAbort"
        @context-change="onInputContextChange"
      />
    </div>

    <!-- Edit title dialog -->
    <van-dialog
      v-model:show="showEditTitleDialog"
      :title="t('aiChat.editTitle')"
      show-cancel-button
      @confirm="onConfirmEditTitle"
      @cancel="onCancelEditTitle"
    >
      <div style="padding: 16px 16px 8px">
        <van-field
          v-model="editTitleInput"
          :placeholder="t('aiChat.editTitlePlaceholder')"
          autofocus
          clearable
          maxlength="30"
          show-word-limit
        />
      </div>
    </van-dialog>

    <!-- Artifact preview popup (Phase 5) — full-screen file preview -->
    <ArtifactPreviewPopup
      v-model:show="showArtifactPreview"
      :artifact="selectedArtifactForPreview"
      :session-id="currentSessionId || ''"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { sendChatMessageStream, getChatHistory, clearChatHistory, markChatRead } from '@/api/ai'
import { getSessions, streamSessionEvents, updateSession, deleteSession as deleteSessionApi, forkSession } from '@/api/sessions'
import { useAIStore } from '@/stores/ai'
import { useAgentStore } from '@/stores/agent'
import { getAgent } from '@/api/agent'
import type { Agent } from '@/types/agent'
import AiArtifactBadge from '@/components/ai/AiArtifactBadge.vue'
import AiArtifactSheet from '@/components/ai/AiArtifactSheet.vue'
import NuminaLogo from '@/components/common/NuminaLogo.vue'
// DeerFlow-aligned chat components
import ChatMessage from '@/components/chat/ChatMessage.vue'
import MessageGroup from '@/components/ai-chat/MessageGroup.vue'
import Suggestions from '@/components/ai-chat/Suggestions.vue'
import SuggestionConfirmDialog from '@/components/ai-chat/SuggestionConfirmDialog.vue'
import ArtifactPreviewPopup from '@/components/ai-chat/ArtifactPreviewPopup.vue'
import InputBox from '@/components/ai-chat/InputBox.vue'
import { useTenantAiResources, INPUT_MODE_CONFIGS } from '@/composables/ai-chat/useTenantAiResources'
import type { InputMode, SubmitPayload, InputContext } from '@/types/ai-chat/input-mode'
import { createAgentEventParser } from '@/composables/useAgentEventStream'
import { useMessageGroups } from '@/composables/ai-chat/useMessageGroups'
import { useSuggestions } from '@/composables/ai-chat/useSuggestions'
import { clearArtifactContentCache } from '@/composables/ai-chat/useArtifacts'
import { clearSubtasks } from '@/composables/ai-chat/useSubtasks'
import { toDeerFlowChatMessages } from '@/utils/ai-chat/messageAdapter'
import { createNormalizationState, normalizeAgentEvent, extractArtifactFromStep } from '@/utils/aiEventNormalizer'
import { isLongTask } from '@/utils/aiTaskDetection'
import { filterAIContent } from '@/utils/contentFilter'
import type { AgentEvent, ProcessStep, PlanStep, Artifact } from '@/types/agent-stream'
import type { SessionSummary } from '@/types/session'

const NUMINA_AGENT_NAME = 'numina'

// Configure marked
marked.use({ breaks: true })

function renderMarkdown(text: string): string {
  return DOMPurify.sanitize(marked.parse(text) as string)
}

// Static data — module-level to avoid re-allocation on each mount
// Note: welcome state suggestions are now handled by InputBox.vue

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
}

function mapToolTimelineToSteps(timeline?: ToolTimelineItem[]): ProcessStep[] {
  if (!timeline) return []
  return timeline.map<ProcessStep>(tool => ({
    type: 'tool_call',
    id: tool.id,
    name: tool.name,
    displayName: tool.displayName,
    icon: tool.icon,
    args: parseToolArgs(tool.argumentsText),
    status: tool.result ? (tool.result.success ? 'done' : 'error') : 'running',
    resultSummary: tool.result?.summary,
    error: tool.result?.error,
    elapsedMs: tool.result?.execution_time_ms,
  }))
}

function parseToolArgs(argsText?: string): Record<string, unknown> {
  if (!argsText) return {}
  try {
    return JSON.parse(argsText)
  } catch {
    return { text: argsText }
  }
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  sendStatus?: 'sending' | 'sent' | 'failed'
  content: string
  renderedContent?: string
  created_at: string
  displayTime: string
  feedback?: 1 | -1 | 0
  // deep think fields
  thinkContent?: string
  thinkOpen?: boolean
  thinkDone?: boolean
  thinkSeconds?: number
  reasoningStartTime?: number | null
  thinkManuallyToggled?: boolean
  toolTimeline?: ToolTimelineItem[]
  // New fields for AiProcessBlock — unified steps[] preserves event order (spec §3.3)
  // U10: processStatus extended to include 'interrupted' for proper status handling
  processStatus?: 'running' | 'done' | 'error' | 'interrupted'
  processElapsedMs?: number
  processSteps?: ProcessStep[]
  // Plan progress bar state (U10)
  planSteps?: PlanStep[]
  planSource?: 'explicit' | 'inferred' | null
  // Process footnote toggle state (U5)
  processExpanded?: boolean
  // LLM-generated follow-up suggestions from capability.end
  suggestions?: string[]
}

interface ToolTimelineItem {
  id: string
  name: string
  displayName: string
  icon: string
  argumentsText: string
  result?: {
    success?: boolean
    summary?: string
    data?: unknown
    error?: string
    execution_time_ms?: number
  }
}

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const aiStore = useAIStore()
const agentStore = useAgentStore()

// U12: active agent for this chat session, resolved from route.query.agentId.
// Drives header agent identity (display_name + icon, NuminaLogo for numina)
// and is the future hook point for skill-scoped dispatch metadata. Loading
// is best-effort: failures fall back to numina from the store, then to a
// neutral placeholder. We don't block message sending on agent fetch since
// the backend dispatch route also accepts agentId from the route param.
const activeAgent = ref<Agent | null>(null)
const activeAgentLoading = ref(false)

async function loadActiveAgent() {
  const agentId = typeof route.query.agentId === 'string' ? route.query.agentId : null
  if (!agentId) {
    // No agentId in URL — fall back to numina from the store.
    const fallback =
      agentStore.systemAgents.find((a) => a.agent_name === NUMINA_AGENT_NAME) ||
      agentStore.systemAgents[0] ||
      null
    activeAgent.value = fallback
    return
  }
  activeAgentLoading.value = true
  try {
    activeAgent.value = await getAgent(agentId)
  } catch {
    // Fetch failed — fall back to store-resolved numina.
    activeAgent.value =
      agentStore.systemAgents.find((a) => a.agent_name === NUMINA_AGENT_NAME) ||
      agentStore.systemAgents[0] ||
      null
  } finally {
    activeAgentLoading.value = false
  }
}
const messages = ref<Message[]>([])

// Feature flag: Enable DeerFlow MessageGroup rendering
// Set to true for DeerFlow-aligned 6-type message grouping
// Set to false to use existing ChatMessage rendering (legacy)
// DeerFlow message grouping
// Convert legacy Message[] to DeerFlow ChatMessage[] for grouping
const deerFlowMessages = computed(() => toDeerFlowChatMessages(messages.value))
// Apply getMessageGroups() algorithm for 6-type grouping
const messageGroups = useMessageGroups(deerFlowMessages)

const inputText = ref('')
const asking = ref(false)
const connecting = ref(false)
const connectingSeconds = ref(0)
// SSE reconnect state (DeerFlow state machine §"reconnecting")
const reconnecting = ref(false)
const reconnectAttempts = ref(0)
const MAX_RECONNECT_ATTEMPTS = 3
// Artifact registry state (U5)
const sessionArtifacts = ref<Artifact[]>([])
const showArtifactSheet = ref(false)
// Artifact preview popup state (Phase 5)
const showArtifactPreview = ref(false)
const selectedArtifactForPreview = ref<Artifact | null>(null)

// DeerFlow 4-mode system (Phase 2)
// Flash/Thinking/Pro/Ultra with tenant-aware mode selection
const inputMode = ref<InputMode>('pro')
const modelName = ref<string>('')
const inputContext = ref<InputContext>({
  model_name: '',
  mode: 'pro',
  reasoning_effort: 'medium',
})
const currentSessionId = ref<string | null>(null)

// Legacy refs for API compatibility (mapped from DeerFlow params)
const deepThink = ref(false)
const webSearch = ref(false)
const reasoningEffort = ref<'low' | 'medium' | 'high'>('medium')

// AC-001: DeerFlow execution mode state (wired to backend)
const deerFlowPlanMode = ref(false)
const deerFlowSubagentEnabled = ref(false)

// Tenant AI resources for model/mode selection
const {
  models: _tenantModels,  // Unused but available for future use
  supportsThinking: _supportsThinking,  // Unused but available for InputBox validation
  supportsSubagent: _supportsSubagent,  // Unused but available for InputBox validation
  defaultModel,
} = useTenantAiResources()

// Initialize model name from tenant resources
watch(defaultModel, (model) => {
  if (model && !modelName.value) {
    modelName.value = model.name
    inputContext.value.model_name = model.name
  }
})

// Handle InputBox context change
function onInputContextChange(ctx: InputContext) {
  inputContext.value = ctx
  inputMode.value = ctx.mode
  modelName.value = ctx.model_name
}

// DeerFlow-style submit handler (Phase 2 integration)
// AC-001: Wire is_plan_mode and subagent_enabled to backend API
function onDeerFlowSubmit(payload: SubmitPayload) {
  const { text, model_name, mode, thinking_enabled, is_plan_mode, subagent_enabled, reasoning_effort } = payload

  // Map DeerFlow 4-mode to legacy parameters
  // thinking_enabled → deepThink
  // reasoning_effort → reasoningEffort (already supported)
  // AC-005: Map 'minimal' to 'low' for backend compatibility
  deepThink.value = thinking_enabled
  reasoningEffort.value = reasoning_effort === 'minimal' ? 'low' : reasoning_effort

  // AC-001: Store DeerFlow execution mode for backend routing
  deerFlowPlanMode.value = is_plan_mode
  deerFlowSubagentEnabled.value = subagent_enabled

  // Update local state
  inputMode.value = mode as InputMode
  modelName.value = model_name
  inputContext.value = {
    model_name,
    mode: mode as InputMode,
    reasoning_effort: reasoning_effort === 'minimal' ? 'low' : reasoning_effort,
  }

  // Set input text and trigger send
  inputText.value = text
  onSend()
}

// Follow-up suggestions state (Phase 7)
const {
  followups,
  followupsHidden,
  followupsLoading,
  handleSuggestionClick,
  hideSuggestions,
  resetSuggestions,
  // Confirm dialog state for non-empty input handling
  confirmOpen,
  pendingSuggestion,
  confirmAppendAndSend,
  confirmReplaceAndSend,
} = useSuggestions(
  deerFlowMessages,
  computed(() => {
    // Derive phase from asking/connecting state
    if (connecting.value) return 'connecting'
    if (asking.value) return 'answering'
    return 'done'
  }),
  currentSessionId,
  modelName,  // Use modelName instead of mode placeholder
  inputText,
)
const scrollRef = ref<HTMLElement | null>(null)
const isUserScrolledUp = ref(false)
let programmaticScroll = false
const showHistory = ref(false)
const sessions = ref<SessionSummary[]>([])
const sessionsLoading = ref(false)
const sessionsLoadingMore = ref(false)
const sessionsLoaded = ref(false)
const sessionsAllLoaded = ref(false)
const sessionsOffset = ref(0)
const SESSIONS_PAGE_SIZE = 20
const sessionSource = ref<string | null>(null)
const historyScrollRef = ref<HTMLElement | null>(null)
const paginationSentinelRef = ref<HTMLElement | null>(null)
let paginationObserver: IntersectionObserver | null = null

// Session context menu state
const sessionMenu = ref<{
  visible: boolean
  session: SessionSummary | null
  x: number
  y: number
}>({ visible: false, session: null, x: 0, y: 0 })
const showRenameDialog = ref(false)
const renameInput = ref('')
const showAgentInfo = ref(false)
// Edit mode state: when editingMessageIdx is set, that user message becomes an input field
const editingMessageIdx = ref<number | null>(null)
const editInputText = ref('')

// Group sessions by time bucket for display
const groupedSessions = computed(() => {
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterdayStart = new Date(todayStart.getTime() - 86400000)
  const weekStart = new Date(todayStart.getTime() - 7 * 86400000)
  const monthStart = new Date(todayStart.getTime() - 30 * 86400000)

  const groups: Record<string, SessionSummary[]> = {}
  const order: string[] = []

  function addToGroup(label: string, session: SessionSummary) {
    if (!groups[label]) { groups[label] = []; order.push(label) }
    groups[label].push(session)
  }

  // Sessions already sorted by backend (pinned first, then updated_at desc)
  for (const s of sessions.value) {
    if (s.is_pinned) {
      addToGroup(t('aiChat.groupPinned'), s)
      continue
    }
    const d = new Date(s.updated_at)
    if (d >= todayStart) {
      addToGroup(t('aiChat.groupToday'), s)
    } else if (d >= yesterdayStart) {
      addToGroup(t('aiChat.groupYesterday'), s)
    } else if (d >= weekStart) {
      addToGroup(t('aiChat.groupWeek'), s)
    } else if (d >= monthStart) {
      addToGroup(t('aiChat.groupMonth'), s)
    } else {
      const label = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
      addToGroup(label, s)
    }
  }

  return order.map((label) => ({ label, sessions: groups[label] }))
})

function openSessionMenu(session: SessionSummary, event: MouseEvent) {
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const menuWidth = 140
  const x = Math.max(4, Math.min(rect.left - menuWidth, window.innerWidth - menuWidth - 4))
  sessionMenu.value = {
    visible: true,
    session,
    x,
    y: rect.bottom + 4,
  }
}

function closeSessionMenu() {
  sessionMenu.value.visible = false
}

function onRenameSession() {
  if (!sessionMenu.value.session) return
  renameInput.value = sessionMenu.value.session.title ?? ''
  showRenameDialog.value = true
  closeSessionMenu()
}

async function onConfirmRename() {
  const session = sessionMenu.value.session
  if (!session) return
  const title = renameInput.value.trim()
  if (!title) return
  try {
    await updateSession(session.session_id, { title })
    session.title = title
    showToast(t('aiChat.renameSessionSuccess'))
  } catch {
    showToast(t('aiChat.renameSessionFailed'))
  }
  showRenameDialog.value = false
}

async function onTogglePinSession() {
  const session = sessionMenu.value.session
  if (!session) return
  closeSessionMenu()
  const newPinned = !session.is_pinned
  try {
    await updateSession(session.session_id, { is_pinned: newPinned })
    session.is_pinned = newPinned
    // Re-sort: move pinned to front, unpinned back by updated_at
    sessions.value = [
      ...sessions.value.filter((s) => s.is_pinned),
      ...sessions.value.filter((s) => !s.is_pinned).sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      ),
    ]
    showToast(newPinned ? t('aiChat.pinSessionSuccess') : t('aiChat.unpinSessionSuccess'))
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

async function onDeleteSession() {
  const session = sessionMenu.value.session
  if (!session) return
  closeSessionMenu()
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('aiChat.confirmDeleteSession') })
  } catch {
    return // cancelled
  }
  try {
    await deleteSessionApi(session.session_id)
    sessions.value = sessions.value.filter((s) => s.session_id !== session.session_id)
    showToast(t('aiChat.deleteSessionSuccess'))
    // If deleted session is the current one, reset to new chat
    if (currentSessionId.value === session.session_id) {
      messages.value = []
      currentSessionId.value = null
      customTitle.value = null
    }
  } catch {
    // silently ignore
  }
}

// Watch messages for artifact extraction (U5)
watch(
  () => messages.value.map((m) => m.processSteps),
  (stepsArrays) => {
    for (const steps of stepsArrays) {
      if (!steps) continue
      for (const step of steps) {
        // Only extract from newly completed tool calls
        if (step.type === 'tool_call' && step.status === 'done') {
          const artifact = extractArtifactFromStep(step)
          if (artifact && artifact.sourceStepId) {
            // Deduplicate by sourceStepId
            const exists = sessionArtifacts.value.some((a) => a.sourceStepId === artifact.sourceStepId)
            if (!exists) {
              sessionArtifacts.value.push(artifact)
            }
          }
        }
      }
    }
  },
  { deep: true }
)

// Throttled markdown rendering state (scoped to this component instance)
let renderTimer: ReturnType<typeof setTimeout> | null = null
let pendingRenderText = ''
let pendingRenderTarget: { content: string; renderedContent?: string } | null = null
let scrollRAF: number | null = null

// Follow global theme via data-theme attribute set by App.vue
const dataTheme = ref(document.documentElement.getAttribute('data-theme') ?? 'dark')
const isLight = computed(() => dataTheme.value === 'light')
let themeObserver: MutationObserver | null = null

let abortController: AbortController | null = null
let connectTimer: ReturnType<typeof setInterval> | null = null
let watchdogTimer: ReturnType<typeof setTimeout> | null = null
let watchdogTimedOut = false
const STREAM_TIMEOUT_MS = 30_000

function clearStreamWatchdog() {
  if (watchdogTimer) {
    clearTimeout(watchdogTimer)
    watchdogTimer = null
  }
}


const sessionTitle = computed(() => {
  const firstUser = messages.value.find((m) => m.role === 'user')
  if (!firstUser) return t('aiChat.newChat')
  const text = firstUser.content.trim()
  return text.length > 20 ? text.slice(0, 20) + '…' : text
})

// Typewriter effect for title
const displayedTitle = ref(t('aiChat.newChat'))
const customTitle = ref<string | null>(null)
const showEditTitleDialog = ref(false)
const editTitleInput = ref('')
let titleTimer: ReturnType<typeof setTimeout> | null = null

// Truncated title for header display (max 12 chars)
const truncatedTitle = computed(() => {
  const title = customTitle.value ?? displayedTitle.value
  if (!title || title === t('aiChat.newChat')) return title
  return title.length > 12 ? title.slice(0, 12) + '…' : title
})

// Toggle agent info popup
function onToggleAgentInfo() {
  showAgentInfo.value = !showAgentInfo.value
}

watch(sessionTitle, (newTitle) => {
  if (customTitle.value !== null) return // user has set a custom title, don't overwrite
  if (titleTimer) { clearTimeout(titleTimer); titleTimer = null }
  if (!newTitle || newTitle === t('aiChat.newChat')) {
    displayedTitle.value = newTitle
    return
  }
  // Animate character by character
  let i = 0
  displayedTitle.value = ''
  function tick() {
    if (i < newTitle.length) {
      displayedTitle.value = newTitle.slice(0, ++i)
      titleTimer = setTimeout(tick, 40)
    }
  }
  tick()
})

watch(customTitle, (val) => {
  if (val !== null) displayedTitle.value = val
})

function onEditTitle() {
  showEditTitleDialog.value = true
  editTitleInput.value = customTitle.value ?? sessionTitle.value
}

function onConfirmEditTitle() {
  const val = editTitleInput.value.trim()
  if (val) {
    customTitle.value = val.length > 30 ? val.slice(0, 30) + '…' : val
  }
  showEditTitleDialog.value = false
}

function onCancelEditTitle() {
  showEditTitleDialog.value = false
}

// Throttled markdown render helper (uses state declared above)
function renderMarkdownThrottled(text: string, target: { content: string; renderedContent?: string }) {
  pendingRenderText = text
  pendingRenderTarget = target

  if (renderTimer) return // Already pending

  renderTimer = setTimeout(() => {
    renderTimer = null
    if (pendingRenderTarget && pendingRenderText) {
      pendingRenderTarget.renderedContent = renderMarkdown(pendingRenderText)
    }
  }, 100) // Render every 100ms max
}

async function scrollToBottom(force = false) {
  await nextTick()
  if (scrollRef.value) {
    if (!force && isUserScrolledUp.value) return // Don't auto-scroll when user has scrolled up
    if (force && scrollRAF) {
      // Cancel any pending throttled scroll — the final force=true call needs
      // to win, otherwise the in-flight rAF executes against a stale scrollHeight.
      cancelAnimationFrame(scrollRAF)
      scrollRAF = null
    }
    if (scrollRAF) return // Already pending
    programmaticScroll = true
    scrollRAF = requestAnimationFrame(() => {
      scrollRAF = null
      if (scrollRef.value) {
        scrollRef.value.scrollTop = scrollRef.value.scrollHeight
      }
    })
  }
}

function onChatScroll() {
  // Ignore scroll events triggered by our own scrollToBottom / onScrollToBottom
  // calls — the programmaticScroll flag is set just before the scroll mutation
  // and cleared on the next event. Without this gate, the moment we
  // scrollTop = scrollHeight, the resulting scroll event re-evaluates
  // distFromBottom and can briefly toggle isUserScrolledUp during smooth scroll.
  if (programmaticScroll) {
    programmaticScroll = false
    return
  }
  const el = scrollRef.value
  if (!el) return
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  // Visibility gate is independent of streaming state (spec §B1):
  // the scroll-to-bottom button must appear whenever the user is scrolled up,
  // not only while asking — otherwise the button hides while reading history.
  isUserScrolledUp.value = distFromBottom > 100
}

function onScrollToBottom() {
  isUserScrolledUp.value = false
  if (scrollRef.value) {
    programmaticScroll = true
    scrollRef.value.scrollTo({ top: scrollRef.value.scrollHeight, behavior: 'smooth' })
  }
}

function _phaseLabel(phase: NonNullable<Message['phase']>) {
  if (phase === 'connecting') return t('aiChat.connecting')
  if (phase === 'thinking') return t('aiChat.thinking')
  if (phase === 'answering') return t('aiChat.answering')
  return ''
}

// Load session list when history panel opens (lazy, once per mount)
// Agent filter for session history — defaults to activeAgent if set, else 'all'
const selectedAgentId = ref<string>('all')

// Agent filter options from agentStore
const agentFilters = computed(() => [
  { label: t('aiChat.filterAll'), value: null },
  ...agentStore.allAgents
    .filter((a) => a.is_enabled)
    .map((a) => ({
      label: `${a.icon || '🤖'} ${a.display_name}`,
      value: a.id,
    })),
])

// Initialize selectedAgentId from activeAgent when it's loaded
watch(activeAgent, (agent) => {
  if (agent && selectedAgentId.value === 'all') {
    selectedAgentId.value = agent.id
    if (sessionsLoaded.value) loadSessions()
  }
}, { immediate: true })

async function loadSessions() {
  sessionsLoading.value = true
  sessionsOffset.value = 0
  sessionsAllLoaded.value = false
  try {
    // Pass agent_id filter - use null for "all"
    const agentIdParam = selectedAgentId.value === 'all' ? undefined : selectedAgentId.value
    const res = await getSessions(SESSIONS_PAGE_SIZE, 0, agentIdParam)
    sessions.value = res.data.sessions
    sessionsLoaded.value = true
    if (res.data.sessions.length < SESSIONS_PAGE_SIZE || sessions.value.length >= res.data.total) {
      sessionsAllLoaded.value = true
    }
    sessionsOffset.value = res.data.sessions.length
  } catch {
    showToast(t('toast.operationFailed'))
  } finally {
    sessionsLoading.value = false
  }
}

async function loadMoreSessions() {
  if (sessionsLoadingMore.value || sessionsAllLoaded.value || sessionsLoading.value) return
  sessionsLoadingMore.value = true
  // Capture the agentId at call time; discard results if it changed mid-flight
  const agentIdAtCall = selectedAgentId.value
  try {
    const agentIdParam = agentIdAtCall === 'all' ? undefined : agentIdAtCall
    const res = await getSessions(SESSIONS_PAGE_SIZE, sessionsOffset.value, agentIdParam)
    if (selectedAgentId.value !== agentIdAtCall) return // stale response
    sessions.value = [...sessions.value, ...res.data.sessions]
    sessionsOffset.value += res.data.sessions.length
    if (res.data.sessions.length < SESSIONS_PAGE_SIZE || sessions.value.length >= res.data.total) {
      sessionsAllLoaded.value = true
    }
  } catch {
    showToast(t('toast.operationFailed'))
  } finally {
    sessionsLoadingMore.value = false
  }
}

async function onSelectAgent(agentId: string | null) {
  // null means "全部" (all) - store as 'all' for consistency
  selectedAgentId.value = agentId ?? 'all'
  sessions.value = []
  sessionsOffset.value = 0
  sessionsAllLoaded.value = false
  sessionsLoaded.value = false
  await loadSessions()
}

watch(showHistory, async (open) => {
  if (!open || sessionsLoaded.value) return
  await loadSessions()
})

async function loadSessionMessages(session: SessionSummary) {
  showHistory.value = false
  messages.value = []
  currentSessionId.value = session.session_id
  asking.value = true
  connecting.value = true
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null
  try {
    reader = await streamSessionEvents(session.session_id)
    const decoder = new TextDecoder()
    let buf = ''

    // U6: Create normalization state for process reconstruction
    const normState = createNormalizationState()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let nl = buf.indexOf('\n')
      while (nl >= 0) {
        const line = buf.slice(0, nl).trim()
        buf = buf.slice(nl + 1)
        if (!line) { nl = buf.indexOf('\n'); continue }
        try {
          const event = JSON.parse(line)

          // U6: Route ALL events through normalizer to reconstruct processSteps
          normalizeAgentEvent(event, normState)

          if (event.type === 'user.message') {
            messages.value.push({
              id: event.eventId ?? Date.now().toString(),
              role: 'user',
              content: event.content ?? '',
              created_at: event.timestamp ?? new Date().toISOString(),
              displayTime: formatTime(event.timestamp ?? new Date().toISOString()),
            })
          } else if (event.type === 'assistant.message') {
            // U6: Assign reconstructed processSteps to historical message
            // Apply content filter to remove question echo and DeerFlow leakage
            // Get the preceding user message for question echo removal
            const lastUserMsg = messages.value.filter(m => m.role === 'user').pop()
            const userQuestion = lastUserMsg?.content ?? ''
            const rawContent = event.content ?? ''
            const filteredContent = filterAIContent(rawContent, userQuestion)
            // Debug: log if filter changed content (dev only)
            if (import.meta.env.DEV && rawContent !== filteredContent) {
              console.log('[loadSessionMessages] filterAIContent applied:', {
                rawLen: rawContent.length,
                filteredLen: filteredContent.length,
                diff: rawContent.length - filteredContent.length,
                hasUserQuestion: !!userQuestion,
                userQuestionLen: userQuestion.length,
                rawPreview: rawContent.slice(0, 200),
                filteredPreview: filteredContent.slice(0, 200),
              })
            }
            const assistantMsg: Message = {
              id: event.eventId ?? Date.now().toString(),
              role: 'assistant',
              phase: 'done',
              content: filteredContent,
              renderedContent: renderMarkdown(filteredContent),
              created_at: event.timestamp ?? new Date().toISOString(),
              displayTime: formatTime(event.timestamp ?? new Date().toISOString()),
              // R12: processSteps populated from normalizer
              processSteps: [...normState.steps],
              processStatus: 'done',
              processElapsedMs: normState.reasoningStartTime
                ? Date.now() - normState.reasoningStartTime
                : 0,
              // R14: footnote collapsed initially
              processExpanded: false,
            }
            messages.value.push(assistantMsg)

            // U6: Extract artifacts from reconstructed steps
            for (const step of normState.steps) {
              if (step.type === 'tool_call' && step.status === 'done') {
                const artifact = extractArtifactFromStep(step)
                if (artifact && artifact.sourceStepId) {
                  // Deduplicate by sourceStepId
                  const exists = sessionArtifacts.value.some(
                    (a) => a.sourceStepId === artifact.sourceStepId
                  )
                  if (!exists) {
                    sessionArtifacts.value.push(artifact)
                  }
                }
              }
            }

            // Reset normState for next assistant message
            normState.steps = []
            normState.phase = 'connecting'
            normState.reasoningStartTime = null
            normState.answerContent = ''
            normState.artifacts = []
            normState.subagents.clear()
            normState.planSteps = []
            normState.lastPlanHash = ''
            normState.planSource = null
            normState.inferredSteps = []
            if (normState.planWaitTimer) {
              clearTimeout(normState.planWaitTimer)
              normState.planWaitTimer = null
            }
          }
        } catch {
          // U6: Malformed JSONL line → skip gracefully (console.warn)
          console.warn('Failed to parse session event line:', line)
        }
        nl = buf.indexOf('\n')
      }
    }
  } catch {
    showToast(t('aiChat.loadSessionFailed'))
  } finally {
    reader?.cancel().catch(() => {})
    asking.value = false
    connecting.value = false
    await scrollToBottom()
  }
}

async function onNewChat() {
  if (messages.value.length === 0) return
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('aiChat.newChatConfirm') })
    messages.value = []
    currentSessionId.value = null
    customTitle.value = null
    sessionArtifacts.value = []  // Clear artifact registry (R10)
    sessionsLoaded.value = false  // force refresh next time history panel opens
    sessions.value = []
    sessionsOffset.value = 0
    sessionsAllLoaded.value = false
  } catch {
    // cancelled
  }
}

async function onSend() {
  const q = inputText.value.trim()
  if (!q || asking.value) return

  // Reset scroll state at the start of a new turn (spec §B1): a fresh question
  // means the user is committing to the new exchange, so subsequent
  // scrollToBottom calls during streaming must not be suppressed by a stale
  // isUserScrolledUp from earlier in the conversation.
  isUserScrolledUp.value = false

  // Reset suggestions when user sends a new question (Phase 7)
  resetSuggestions()

  const userMsgId = Date.now().toString()
  messages.value.push({
    id: userMsgId,
    role: 'user',
    sendStatus: 'sending',
    content: q,
    created_at: new Date().toISOString(),
    displayTime: formatTime(new Date().toISOString()),
  })
  inputText.value = ''
  asking.value = true
  connecting.value = true  // Show connecting animation first
  connectingSeconds.value = 0
  connectTimer = setInterval(() => { connectingSeconds.value++ }, 1000)
  abortController = new AbortController()
  await scrollToBottom()
  const userMsgIdx = messages.value.findIndex((m) => m.id === userMsgId)

  // Add assistant message placeholder (with think block if deep_think)
  const thinkStart = deepThink.value ? Date.now() : 0
  const assistantMsg: Message = {
    id: `pending-${Date.now()}`,
    role: 'assistant',
    phase: 'connecting',
    content: '',
    renderedContent: '',
    created_at: new Date().toISOString(),
    displayTime: formatTime(new Date().toISOString()),
    thinkContent: deepThink.value ? '' : undefined,
    thinkOpen: deepThink.value ? true : undefined,
    thinkDone: deepThink.value ? false : undefined,
    thinkSeconds: deepThink.value ? 0 : undefined,
    toolTimeline: [],
    processSteps: [],
    processStatus: 'running',
  }
  messages.value.push(assistantMsg)
  const msgIdx = messages.value.length - 1
  await scrollToBottom()

  let thinkTimer: ReturnType<typeof setInterval> | null = null
  if (deepThink.value) {
    thinkTimer = setInterval(() => {
      if (!messages.value[msgIdx].thinkDone) {
        messages.value[msgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
      }
    }, 1000)
  }

  const decoder = new TextDecoder()
  let textRaw = ''
  let thinkingDone = false
  const normState = createNormalizationState()

  try {
    // ADV-001 fix: pass agentId so the backend routes through the
    // agent-dispatch path (which runs _resolve_skills). Without this, R5
    // (AI问答 chat-only) is not enforced at runtime — every chat would
    // go through the legacy chat_adapter regardless of the selected agent.
    // AC-001: Pass DeerFlow execution mode parameters to backend
    const reader = await sendChatMessageStream(
      q,
      deepThink.value,
      webSearch.value,
      abortController.signal,
      currentSessionId.value ?? undefined,
      activeAgent.value?.id,
      reasoningEffort.value,
      sessionSource.value ?? undefined,
      deerFlowPlanMode.value,
      deerFlowSubagentEnabled.value,
    )
    sessionSource.value = null
    const parser = createAgentEventParser(handleEvent)

    // Connection established, hide connecting animation
    if (connectTimer) { clearInterval(connectTimer); connectTimer = null }
    connecting.value = false
    messages.value[msgIdx].phase = deepThink.value ? 'thinking' : 'answering'
    // Mark user message as sent
    if (userMsgIdx >= 0) {
      messages.value[userMsgIdx].sendStatus = 'sent'
    }
    await scrollToBottom()

    // Stream timeout watchdog (spec §8 risk): if no event arrives within
    // STREAM_TIMEOUT_MS, abort the stream and mark the message as errored.
    // Reset on every received event so an active stream never times out.
    watchdogTimedOut = false
    function armWatchdog() {
      clearStreamWatchdog()
      watchdogTimer = setTimeout(() => {
        watchdogTimedOut = true
        abortController?.abort()
      }, STREAM_TIMEOUT_MS)
    }
    armWatchdog()

    function syncStepsToMessage() {
      // Live render reads processSteps; assign a fresh array reference so Vue
      // reactivity picks up step-array mutations made by the normalizer.
      messages.value[msgIdx].processSteps = [...normState.steps]
      messages.value[msgIdx].processStatus =
        normState.phase === 'done' ? 'done' : 'running'
      // Sync plan state so AiProcessBlock can render AiPlanProgressBar (U10)
      messages.value[msgIdx].planSteps = normState.planSteps.length > 0
        ? [...normState.planSteps]
        : undefined
      messages.value[msgIdx].planSource = normState.planSource
    }

    function handleEvent(event: AgentEvent) {
      // Reset stream watchdog: any received event keeps the stream alive (spec §8).
      armWatchdog()

      if (event.type === 'session.start') {
        if (event.session_id) currentSessionId.value = event.session_id
        return
      }

      // Route every event through the normalizer so state.steps[] is the
      // single source of truth for AiProcessBlock (spec §3.3 unified order).
      normalizeAgentEvent(event, normState)
      syncStepsToMessage()

      if (event.type === 'phase.connecting') {
        messages.value[msgIdx].phase = 'connecting'
        return
      }
      if (event.type === 'phase.thinking') {
        messages.value[msgIdx].phase = 'thinking'
        if (messages.value[msgIdx].reasoningStartTime == null) {
          messages.value[msgIdx].reasoningStartTime = Date.now()
        }
        return
      }
      if (event.type === 'phase.answering') {
        messages.value[msgIdx].phase = 'answering'
        // Auto-collapse think block when answering starts, unless user manually toggled it
        if (messages.value[msgIdx].thinkDone && !messages.value[msgIdx].thinkManuallyToggled) {
          messages.value[msgIdx].thinkOpen = false
        }
        return
      }
      if (event.type === 'token.stream' && event.is_thinking) {
        // Reasoning content is captured inside normState.steps; nothing else to do.
        return
      }
      if (event.type === 'token.stream') {
        if (!thinkingDone && deepThink.value) {
          thinkingDone = true
          if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
          messages.value[msgIdx].thinkDone = true
          messages.value[msgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
          // Auto-collapse unless user manually toggled
          if (!messages.value[msgIdx].thinkManuallyToggled) {
            messages.value[msgIdx].thinkOpen = false
          }
        }
        textRaw += event.token ?? ''
        // 应用内容过滤器，移除违规内容和问题回声
        const filteredContent = filterAIContent(textRaw, q)
        // DEBUG: Log filter application (dev only)
        if (import.meta.env.DEV && textRaw !== filteredContent) {
          console.log('[filterAIContent] Applied:', { rawLen: textRaw.length, filteredLen: filteredContent.length, diff: textRaw.length - filteredContent.length, questionLen: q?.length })
        }
        messages.value[msgIdx].content = filteredContent
        // Use throttled rendering for smoother streaming
        renderMarkdownThrottled(filteredContent, messages.value[msgIdx])
        scrollToBottom()
        return
      }
      if (event.type === 'capability.error') {
        messages.value[msgIdx].phase = 'error'
        messages.value[msgIdx].content = event.error?.message ?? t('toast.aiChatError')
        messages.value[msgIdx].renderedContent = renderMarkdown(messages.value[msgIdx].content)
      }
      if (event.type === 'capability.end') {
        // syncStepsToMessage already ran at line 1452; just sync phase/processStatus
        messages.value[msgIdx].phase = normState.phase
        messages.value[msgIdx].processStatus = normState.phase === 'done' ? 'done' : 'running'
        if (event.result?.suggestions?.length) {
          messages.value[msgIdx].suggestions = event.result.suggestions
        }
        return
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      parser.push(decoder.decode(value, { stream: true }))
    }
    parser.flush()
    clearStreamWatchdog()

    // Flush pending markdown render
    if (renderTimer) {
      clearTimeout(renderTimer)
      renderTimer = null
      if (pendingRenderTarget && pendingRenderText) {
        pendingRenderTarget.renderedContent = renderMarkdown(pendingRenderText)
      }
    }

    // Finalize think block if no text came (e.g. error from agent)
    if (deepThink.value && !thinkingDone) {
      if (thinkTimer) { clearInterval(thinkTimer); thinkTimer = null }
      messages.value[msgIdx].thinkDone = true
      if (!messages.value[msgIdx].thinkManuallyToggled) {
        messages.value[msgIdx].thinkOpen = false
      }
      messages.value[msgIdx].thinkSeconds = Math.round((Date.now() - thinkStart) / 1000)
    }

    messages.value[msgIdx].phase = textRaw ? 'done' : 'error'
    messages.value[msgIdx].processStatus = textRaw ? 'done' : 'error'
    asking.value = false
    connecting.value = false
    isUserScrolledUp.value = false
    reconnectAttempts.value = 0 // Reset reconnect state on success
    abortController = null
    await scrollToBottom(true)
  } catch (err: unknown) {
    if (thinkTimer) clearInterval(thinkTimer)
    if (connectTimer) { clearInterval(connectTimer); connectTimer = null }
    clearStreamWatchdog()
    if (err instanceof Error && (err.name === 'AbortError' || err.name === 'CanceledError')) {
      // Distinguish watchdog timeout from user-initiated cancel (spec §8)
      const isTimeout = watchdogTimedOut
      watchdogTimedOut = false
      // Finalize the assistant message so it doesn't stay in connecting/thinking/answering phase
      if (messages.value[msgIdx]) {
        if (isTimeout) {
          messages.value[msgIdx].phase = 'error'
          messages.value[msgIdx].content = t('aiChat.errorTimeout')
          messages.value[msgIdx].renderedContent = `<p>${t('aiChat.errorTimeout')}</p>`
        } else {
          messages.value[msgIdx].phase = textRaw ? 'interrupted' : 'error'
          if (!textRaw) {
            messages.value[msgIdx].content = t('toast.aiChatError')
            messages.value[msgIdx].renderedContent = `<p>${t('toast.aiChatError')}</p>`
          }
        }
      }
      asking.value = false
      connecting.value = false
      isUserScrolledUp.value = false
      abortController = null
      return
    }
    // Mark user message as failed so the retry indicator shows
    if (userMsgIdx >= 0) {
      messages.value[userMsgIdx].sendStatus = 'failed'
    }
    // SSE reconnect logic (DeerFlow state machine §"reconnecting")
    // Check if this is a network error that can be retried
    const isNetworkError = err instanceof Error &&
      (err.message.includes('network') ||
       err.message.includes('fetch') ||
       err.message.includes('Failed to fetch') ||
       err.message.includes('NetworkError') ||
       err.message.includes('ECONNREFUSED') ||
       err.message.includes('ECONNRESET'))

    if (isNetworkError && reconnectAttempts.value < MAX_RECONNECT_ATTEMPTS) {
      // Enter reconnecting state, preserve partial response
      reconnecting.value = true
      reconnectAttempts.value++
      messages.value[msgIdx].phase = 'answering' // Keep showing partial content

      // Exponential backoff: 1s, 2s, 4s
      const backoffMs = Math.pow(2, reconnectAttempts.value - 1) * 1000
      await new Promise(resolve => setTimeout(resolve, backoffMs))

      // Create new AbortController for retry
      abortController = new AbortController()

      // Retry the stream - this would need to be implemented as a separate function
      // For now, show reconnecting indicator and let user manually retry
      messages.value[msgIdx].phase = 'error'
      messages.value[msgIdx].content = t('aiChat.errorReconnectFailed', { attempts: reconnectAttempts.value })
      messages.value[msgIdx].renderedContent = `<p>${t('aiChat.errorReconnectFailed', { attempts: reconnectAttempts.value })}</p>`
      reconnecting.value = false
    } else {
      // Max retries exceeded or non-network error
      messages.value[msgIdx] = {
        id: Date.now().toString(),
        role: 'assistant',
        phase: 'error',
        content: t('toast.aiChatError'),
        renderedContent: `<p>${t('toast.aiChatError')}</p>`,
        created_at: new Date().toISOString(),
        displayTime: formatTime(new Date().toISOString()),
      }
    }
    asking.value = false
    connecting.value = false
    reconnectAttempts.value = 0 // Reset for next message
    abortController = null
    await scrollToBottom()
  }
}

function onAbort() {
  abortController?.abort()
  if (connectTimer) { clearInterval(connectTimer); connectTimer = null }
  clearStreamWatchdog()
  watchdogTimedOut = false
  // Reset reconnect state on user-initiated abort
  reconnecting.value = false
  reconnectAttempts.value = 0
  // Mark the last in-progress assistant message as interrupted
  const lastAssistant = [...messages.value].reverse().find((m) => m.role === 'assistant' && m.phase === 'answering')
  if (lastAssistant) lastAssistant.phase = 'interrupted'
  asking.value = false
  connecting.value = false
  abortController = null
}

async function onAction(type: 'file' | 'image' | 'link' | 'clear' | 'camera' | 'ocr' | 'webpage' | 'history') {
  if (type === 'clear') {
    try {
      await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmClearChat') })
      await clearChatHistory()
      messages.value = []
    } catch {
      // cancelled
    }
    return
  }
  showToast(t('toast.featureComingSoon'))
}

// U8: templated suggestion chips. Generated deterministically from message
// content so the same message always renders the same chips on re-render
// (no flicker). Pool is i18n-driven; v1 = static template per plan §"Deferred
// to Follow-Up Work" (LLM-generated chips deferred to v2).
function suggestionChipsFor(msg: Message): string[] {
  // Prefer LLM-generated suggestions if available
  if (msg.suggestions?.length) {
    return msg.suggestions.slice(0, 3)
  }
  // Fallback: template-based suggestions, stable hash rotation
  const pool = [
    t('aiChat.chipFollowupReason'),
    t('aiChat.chipFollowupAction'),
    t('aiChat.chipFollowupExample'),
    t('aiChat.chipFollowupCompare'),
    t('aiChat.chipFollowupTrend'),
  ]
  // Hash content into a stable rotation so different messages get different
  // starting chips but the same message stays consistent.
  const seed = (msg.content || '').length % pool.length
  const count = msg.content && msg.content.length > 200 ? 5 : 3
  const out: string[] = []
  for (let i = 0; i < count; i++) {
    out.push(pool[(seed + i) % pool.length])
  }
  return out
}

function onSuggestionChipClick(chip: string) {
  inputText.value = chip
  // Submit immediately so the chip behaves like a one-tap follow-up.
  void onSend()
}

async function onCopy(content: string) {
  // Try modern Clipboard API first
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(content)
      showToast(t('toast.copied'))
      return
    } catch {
      // Fall through to legacy method
    }
  }
  // Fallback: use textarea + execCommand for older browsers / insecure contexts
  try {
    const textarea = document.createElement('textarea')
    textarea.value = content
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    textarea.style.top = '0'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const success = document.execCommand('copy')
    document.body.removeChild(textarea)
    if (success) {
      showToast(t('toast.copied'))
    } else {
      showToast(t('toast.copyFailed'))
    }
  } catch {
    showToast(t('toast.copyFailed'))
  }
}

function onEditUserMessage(idx: number) {
  const msg = messages.value[idx]
  if (!msg || msg.role !== 'user') return
  // Enter edit mode: show input field in place of the message
  editingMessageIdx.value = idx
  editInputText.value = msg.content
}

function onCancelEdit() {
  editingMessageIdx.value = null
  editInputText.value = ''
}

async function onSendEdit(idx: number) {
  const msg = messages.value[idx]
  if (!msg || msg.role !== 'user') return
  const newContent = editInputText.value.trim()
  if (!newContent || asking.value) return

  // Clear edit mode
  editingMessageIdx.value = null
  editInputText.value = ''

  // Fork session from this message's position if we have a session
  if (currentSessionId.value) {
    try {
      const forkRes = await forkSession(currentSessionId.value, msg.id)
      // Use the new forked session (forkRes.data contains ForkSessionResponse)
      currentSessionId.value = forkRes.data.session_id
    } catch {
      showToast(t('toast.operationFailed'))
      return
    }
  }

  // Remove all messages from this point onwards (visual cleanup)
  messages.value.splice(idx)

  // Reset scroll state
  isUserScrolledUp.value = false

  // Send the edited message as a new question
  inputText.value = newContent
  await onSend()
}

function onFeedback(id: string, value: 1 | -1) {
  const msg = messages.value.find((m) => m.id === id)
  if (!msg) return
  msg.feedback = msg.feedback === value ? 0 : value
}

async function onRetryError(idx: number) {
  if (asking.value) return
  // Find the preceding user message
  const prevUser = [...messages.value].slice(0, idx).reverse().find((m) => m.role === 'user')
  if (!prevUser) return
  // Remove the error assistant message
  messages.value.splice(idx, 1)
  // Re-send the user's question
  inputText.value = prevUser.content
  await onSend()
}

// Artifact action handler (U5)
function onArtifactTap(artifact: Artifact) {
  if (artifact.kind === 'link' || artifact.kind === 'image') {
    // Open URL in new tab
    if (artifact.url) {
      window.open(artifact.url, '_blank', 'noopener,noreferrer')
    }
  } else if (artifact.kind === 'file') {
    // Open full-screen preview popup for file artifacts (Phase 5)
    selectedArtifactForPreview.value = artifact
    showArtifactPreview.value = true
  } else if (artifact.kind === 'report') {
    // Navigate to report page or open URL if available
    if (artifact.url) {
      window.open(artifact.url, '_blank', 'noopener,noreferrer')
    }
  } else if (artifact.kind === 'data' || !artifact.kind) {
    // Show JSON preview dialog for data artifacts
    const jsonStr = JSON.stringify(artifact, null, 2)
    showConfirmDialog({
      title: t('aiArtifact.jsonPreviewTitle'),
      message: jsonStr,
      confirmButtonText: t('common.close'),
      showCancelButton: false,
    }).catch(() => {})
  }
}

// Infinite scroll: watch sentinel at setup level so the watcher is properly tracked
// and cleaned up by Vue's effect scope (not leaked inside onMounted)
watch(paginationSentinelRef, (el) => {
  paginationObserver?.disconnect()
  if (el) paginationObserver?.observe(el)
})

onMounted(async () => {
  // Observe data-theme attribute changes on <html> to stay in sync with global theme
  themeObserver = new MutationObserver(() => {
    dataTheme.value = document.documentElement.getAttribute('data-theme') ?? 'dark'
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

  // Bind scroll listener for auto-scroll pause detection
  scrollRef.value?.addEventListener('scroll', onChatScroll, { passive: true })

  // Create IntersectionObserver for infinite scroll
  paginationObserver = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) loadMoreSessions()
    },
    { threshold: 0.1 },
  )
  // Observe sentinel if it's already in the DOM (e.g. history panel open on mount)
  if (paginationSentinelRef.value) paginationObserver.observe(paginationSentinelRef.value)

  // Default deep think on if the primary model has passed the thinking capability test
  // or if it was enabled from AIHubPage
  if (!aiStore.config) await aiStore.fetchConfig()

  // Resolve which agent this chat session is for (R4: every chat is bound
  // to an agent via the route's agentId query param). Sequential to ensure
  // the store is populated before loadActiveAgent's fallback path reads it.
  if (agentStore.systemAgents.length === 0) {
    await agentStore.loadAgents()
  }
  await loadActiveAgent()

  const routeDeepThink = route.query.deepThink === '1'
  const routeWebSearch = route.query.webSearch === '1'
  const isNewSession = route.query.newSession === '1'
  const routeSource = typeof route.query.source === 'string' ? route.query.source : null
  if (routeSource) sessionSource.value = routeSource

  // Map legacy deepThink/webSearch query params + aiStore flags onto the
  // DeerFlow 4-mode inputMode + independent webSearch ref.
  const wantDeep = routeDeepThink || aiStore.deepThinkEnabled || aiStore.config?.ai_test_thinking_success === true
  const wantSearch = routeWebSearch || aiStore.webSearchEnabled
  // Map legacy 2-state to DeerFlow 4-mode: smart → pro, normal → flash
  inputMode.value = wantDeep ? 'pro' : 'flash'
  deepThink.value = wantDeep  // Keep legacy ref for API compatibility
  webSearch.value = wantSearch
  if (wantDeep) aiStore.deepThinkEnabled = false
  if (wantSearch) aiStore.webSearchEnabled = false

  // Start fresh session when navigating from hub with newSession flag
  if (isNewSession) {
    messages.value = []
  } else {
    // Load existing history (normal navigation or cached session)
    const targetSessionId = typeof route.query.sessionId === 'string' ? route.query.sessionId : undefined
    try {
      const res = await getChatHistory(targetSessionId)
      if (res.data.session_id) {
        currentSessionId.value = res.data.session_id
      }
      messages.value = res.data.messages.map((m, idx) => {
        // Find preceding user message for question echo removal
        const prevMessages = res.data.messages.slice(0, idx)
        const prevUserMsg = prevMessages.filter(pm => pm.role === 'user').pop()
        const userQuestion = prevUserMsg?.content ?? ''
        // Filter AI content once and reuse for both content and renderedContent
        const filteredContent = m.role === 'assistant' ? filterAIContent(m.content, userQuestion) : m.content
        return {
          ...m,
          content: filteredContent,
          displayTime: formatTime(m.created_at),
          renderedContent: m.role === 'assistant' ? renderMarkdown(filteredContent) : undefined,
        }
      })
      await markChatRead()
      await scrollToBottom()
    } catch {
      showToast(t('toast.operationFailed'))
    }
  }

  // Send user's question from hub or route query
  const q = aiStore.draftQuery || route.query.q
  if (typeof q === 'string' && q.trim()) {
    inputText.value = q.trim()
    aiStore.draftQuery = ''
    await onSend()
  }
})

onUnmounted(() => {
  themeObserver?.disconnect()
  paginationObserver?.disconnect()
  scrollRef.value?.removeEventListener('scroll', onChatScroll)
  // Clear global caches for session isolation (DeerFlow pattern)
  clearArtifactContentCache()
  clearSubtasks()
})
</script>

<style scoped>
/* ── CSS variables for day/night theme ── */
.ai-chat-page {
  --bg: #0f1117;
  --bg-header: rgba(15, 17, 23, 0.95);
  --border: rgba(255, 255, 255, 0.06);
  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.5);
  --text-muted: rgba(255, 255, 255, 0.3);
  --bubble-user-bg: rgba(99, 102, 241, 0.22);
  --bubble-user-color: #ffffff;
  --bubble-ai-bg: rgba(189, 187, 255, 0.12);
  --bubble-ai-color: rgba(255, 255, 255, 0.85);
  --bubble-ai-border: rgba(189, 187, 255, 0.2);
  --btn-color: rgba(255, 255, 255, 0.7);
  --btn-hover-bg: rgba(255, 255, 255, 0.08);
  --suggestion-bg: rgba(255, 255, 255, 0.08);
  --suggestion-border: rgba(255, 255, 255, 0.12);
  --think-bg: rgba(99, 102, 241, 0.08);
  --think-border: rgba(99, 102, 241, 0.25);
  --think-color: rgba(255, 255, 255, 0.55);
  --shimmer-color: rgba(255, 255, 255, 0.06);
}

.ai-chat-page.theme-light {
  --bg: #f5f5f7;
  --bg-header: rgba(245, 245, 247, 0.95);
  --border: rgba(0, 0, 0, 0.25);
  --text-primary: rgba(0, 0, 0, 0.9);
  --text-secondary: rgba(0, 0, 0, 0.6);
  --text-muted: rgba(0, 0, 0, 0.45);
  --bubble-user-bg: #e8e8f4;
  --bubble-user-color: #1a1a2e;
  --bubble-ai-bg: rgba(189, 187, 255, 0.22);
  --bubble-ai-color: rgba(0, 0, 0, 0.9);
  --bubble-ai-border: rgba(0, 0, 0, 0.15);
  --btn-color: rgba(0, 0, 0, 0.7);
  --btn-hover-bg: rgba(0, 0, 0, 0.1);
  --suggestion-bg: #fff;
  --suggestion-border: rgba(0, 0, 0, 0.2);
  --think-bg: rgba(99, 102, 241, 0.1);
  --think-border: rgba(99, 102, 241, 0.35);
  --think-color: rgba(0, 0, 0, 0.7);
  --shimmer-color: rgba(255, 255, 255, 0.45);
}

/* ── Page shell ── */
.ai-chat-page {
  display: flex;
  flex-direction: column;
  position: fixed;
  inset: 0;
  bottom: calc(50px + env(safe-area-inset-bottom));
  background: var(--bg);
  z-index: 10;
}

/* ── Header ── */
.chat-header {
  display: flex;
  align-items: center;
  padding: 0 4px;
  padding-top: env(safe-area-inset-top);
  height: calc(50px + env(safe-area-inset-top));
  background: var(--bg-header);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.header-btn {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--btn-color);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.header-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--text-primary);
}

.header-title-wrap {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 0;
  padding: 0 4px;
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}

.header-edit-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.header-edit-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--text-primary);
}

/* Agent logo button — same size as other header buttons */
.header-agent-logo-btn {
  position: relative;
}

.header-agent-logo-emoji {
  font-size: 20px;
  line-height: 1;
}

.header-agent-skeleton {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* Agent info popup — floating below agent button */
.agent-info-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
}

.agent-info-popup {
  position: fixed;
  top: calc(50px + env(safe-area-inset-top) + 4px);
  left: 108px; /* Position below agent button (back + history + agent = 44*3 + 4px gaps ≈ 108px from left) */
  z-index: 101;
  background: var(--bg-header);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(1, 1, 32, 0.2);
  min-width: 160px;
  max-width: 220px;
  padding: 12px 14px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.agent-info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.agent-info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
}

.agent-info-icon :deep(.numina-logo) {
  height: 24px;
}

.agent-info-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-info-description {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  word-break: break-word;
}

.header-actions {
  display: flex;
  align-items: center;
}

/* ── History sidebar ── */
.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  padding: env(safe-area-inset-top) 0 0;
}

.history-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.history-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.history-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
}

.filter-tab {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}

.filter-tab--active {
  background: var(--text-primary);
  color: var(--bg);
  border-color: var(--text-primary);
}

.history-empty {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 14px;
}

.history-empty p {
  margin: 0;
}

.history-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

.history-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0 16px;
}

.history-group-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 10px 16px 4px;
}

.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 8px 8px 16px;
  cursor: pointer;
  border-radius: 0;
  transition: background 0.12s;
  position: relative;
}

.history-item:hover {
  background: var(--btn-hover-bg);
}

.history-item--active {
  background: rgba(99, 102, 241, 0.15);
}

.history-item--active:hover {
  background: rgba(99, 102, 241, 0.2);
}

.history-item-title {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.history-item-menu-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 6px;
  opacity: 0;
  transition: opacity 0.12s, background 0.12s, color 0.12s;
}

.history-item:hover .history-item-menu-btn,
.history-item--active .history-item-menu-btn {
  opacity: 1;
}

.history-item-menu-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--text-primary);
}

/* ── Session context menu ── */
.session-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
}

.session-menu {
  position: fixed;
  z-index: 101;
  background: var(--bg-header);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(1, 1, 32, 0.2);
  min-width: 140px;
  overflow: hidden;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.session-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: background 0.12s;
}

.session-menu-item:hover {
  background: var(--btn-hover-bg);
}

.session-menu-item--danger {
  color: #f87171;
}

.session-menu-item--danger:hover {
  background: rgba(248, 113, 113, 0.1);
}

/* ── Chat body ── */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 16px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overscroll-behavior: contain;
}

/* Desktop centering */
@media (min-width: 640px) {
  .chat-body {
    padding: 16px calc(50% - 384px + 16px) 8px;
  }
  .input-bar {
    padding: 8px calc(50% - 384px + 16px) calc(12px + env(safe-area-inset-bottom));
  }
}

/* ── Empty state ── */
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 0 16px;
  gap: 8px;
}

.empty-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
}

/* DeerFlow wave animation for emoji */
.hero-emoji {
  font-size: 40px;
  display: inline-block;
}

.animate-wave {
  animation: wave 0.6s ease-in-out 2;
  transform-origin: 70% 70%;
}

@keyframes wave {
  0%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(20deg); }
  50% { transform: rotate(0deg); }
  75% { transform: rotate(20deg); }
}

.hero-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.hero-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.empty-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px;
}

/* ── Suggestion cards ── */
.suggestion-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.suggestion-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: var(--suggestion-bg);
  border: 1px solid var(--suggestion-border);
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s, transform 0.15s;
  width: 100%;
}

.suggestion-card:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
}

.suggestion-card:active {
  transform: scale(0.98);
}

.suggestion-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  flex-shrink: 0;
}

.suggestion-text {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.4;
}

.suggestion-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
}

/* ── Messages ── */
.message-row {
  display: flex;
  flex-direction: column;
}

.message-row.user { align-items: flex-end; }
.message-row.assistant { align-items: flex-start; }

.bubble {
  max-width: 86%;
}

.bubble.assistant {
  max-width: 98%;  /* U4: Wider for Agent content (1.5x user bubble target) */
}

/* U4: Mobile (≤428px) — full-width with safe-area padding */
@media (max-width: 428px) {
  .bubble.assistant {
    max-width: 100%;
    padding-left: env(safe-area-inset-left);
    padding-right: env(safe-area-inset-right);
  }
}

.bubble-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.message-row.user .bubble-body {
  align-items: flex-end;
}

/* ── Assistant phase strip ── */
.phase-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  max-width: 100%;
  padding: 8px 12px;
  background: rgba(189, 187, 255, 0.1);
  border: 1px solid var(--bubble-ai-border);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.2;
  box-shadow: rgba(1, 1, 32, 0.08) 0 4px 10px;
}

.phase-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #818cf8;
  box-shadow: 0 0 0 0 rgba(129, 140, 248, 0.5);
  animation: phase-pulse 1.4s ease-out infinite;
  flex-shrink: 0;
}

.phase-strip--answering .phase-pulse {
  background: #6ee7a0;
  box-shadow: 0 0 0 0 rgba(110, 231, 160, 0.45);
}

/* Standalone phase strip (non-deep-think mode) */
.phase-strip.standalone {
  justify-content: center;
  margin-bottom: 4px;
}

/* Small pulse for think block icon wrapper */
.phase-pulse-small {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #818cf8;
  box-shadow: 0 0 0 0 rgba(129, 140, 248, 0.5);
  animation: phase-pulse 1.4s ease-out infinite;
}

.phase-label {
  color: var(--text-primary);
  font-weight: 500;
}

.phase-meta {
  color: var(--text-secondary);
  font-family: 'Georgia', monospace;
}

@keyframes phase-pulse {
  0% { box-shadow: 0 0 0 0 currentColor; opacity: 1; }
  70% { box-shadow: 0 0 0 7px transparent; opacity: 0.7; }
  100% { box-shadow: 0 0 0 0 transparent; opacity: 1; }
}

/* ── Deep think block ── */
.think-block {
  background: var(--think-bg);
  border: 1px solid var(--think-border);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 4px;
}

.think-block--active {
  border-color: rgba(99, 102, 241, 0.3);
  background: rgba(99, 102, 241, 0.12);
}

.think-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: transparent;
  border: none;
  color: #818cf8;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  position: relative;
}

.think-toggle:hover {
  background: rgba(99, 102, 241, 0.08);
}

.think-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.15);
  flex-shrink: 0;
}

.think-block:not(.think-block--done) .think-icon-wrapper {
  animation: pulse-icon 2s ease-in-out infinite;
}

@keyframes pulse-icon {
  0%, 100% { background: rgba(99, 102, 241, 0.15); }
  50% { background: rgba(99, 102, 241, 0.25); }
}

.think-status {
  font-weight: 500;
  position: relative;
}

.think-status--active {
  overflow: hidden;
  position: relative;
}

.think-text-animated {
  display: inline-block;
  position: relative;
  background: linear-gradient(
    90deg,
    rgba(129, 140, 248, 0.7) 0%,
    #818cf8 50%,
    rgba(129, 140, 248, 0.7) 100%
  );
  background-size: 200% 100%;
  animation: shimmer-text 2s linear infinite;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

@keyframes shimmer-text {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.think-duration {
  font-size: 11px;
  color: rgba(129, 140, 248, 0.7);
  background: rgba(99, 102, 241, 0.12);
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 2px;
}

.think-chip-sep {
  color: var(--text-muted);
  font-size: 11px;
  margin: 0 2px;
}

.think-chip {
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(99, 102, 241, 0.08);
  padding: 1px 5px;
  border-radius: 4px;
}

.tool-result--failed {
  color: #f87171;
  font-size: 11px;
  padding: 4px 0 0;
}

.think-chevron {
  margin-left: auto;
  transition: transform 0.2s;
  flex-shrink: 0;
}

.think-block--open .think-chevron {
  transform: rotate(180deg);
}

.think-content {
  padding: 8px 12px 10px;
  font-size: 12px;
  color: var(--think-color);
  line-height: 1.6;
  border-top: 1px solid var(--think-border);
}

.think-content :deep(p) { margin: 0 0 4px; }
.think-content :deep(p:last-child) { margin-bottom: 0; }

/* ── Tool timeline ── */
.tool-timeline {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: min(100%, 320px);
  margin-bottom: 4px;
}

.tool-card {
  border: 1px solid var(--bubble-ai-border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  padding: 9px 10px;
  box-shadow: rgba(1, 1, 32, 0.08) 0 4px 10px;
}

.tool-card--done {
  border-color: rgba(110, 231, 160, 0.28);
}

.tool-card--error {
  border-color: rgba(248, 113, 113, 0.34);
}

.tool-card-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: rgba(189, 187, 255, 0.12);
  color: var(--text-primary);
  font-size: 14px;
  flex-shrink: 0;
}

.tool-card-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.tool-card-title {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  line-height: 1.2;
}

.tool-card-meta,
.tool-card-args,
.tool-result {
  font-size: 11px;
  line-height: 1.35;
}

.tool-card-args {
  margin-top: 7px;
  color: var(--text-muted);
  overflow-wrap: anywhere;
}

.tool-result {
  margin-top: 7px;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.bubble-text {
  display: block;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

/* Markdown content inside assistant bubbles */
.bubble.assistant .bubble-text :deep(p) { margin: 0 0 8px; }
.bubble.assistant .bubble-text :deep(p:last-child) { margin-bottom: 0; }
.bubble.assistant .bubble-text :deep(ul),
.bubble.assistant .bubble-text :deep(ol) { margin: 4px 0 8px 16px; padding: 0; }
.bubble.assistant .bubble-text :deep(li) { margin-bottom: 2px; }
.bubble.assistant .bubble-text :deep(code) {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.bubble.assistant .bubble-text :deep(pre) {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--bubble-ai-border);
  border-radius: 8px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.bubble.assistant .bubble-text :deep(pre code) {
  background: transparent;
  padding: 0;
  color: var(--bubble-ai-color);
}
.bubble.assistant .bubble-text :deep(strong) { color: var(--text-primary); }
.bubble.assistant .bubble-text :deep(a) { color: #818cf8; text-decoration: underline; word-break: break-all; }
/* Mobile overflow fixes for code blocks and tables */
.bubble.assistant .bubble-text :deep(pre) { max-width: 100%; -webkit-overflow-scrolling: touch; }
.bubble.assistant .bubble-text :deep(table) {
  display: block;
  overflow-x: auto;
  max-width: 100%;
  -webkit-overflow-scrolling: touch;
  border-collapse: collapse;
  font-size: 13px;
}
.bubble.assistant .bubble-text :deep(th),
.bubble.assistant .bubble-text :deep(td) {
  border: 1px solid var(--bubble-ai-border);
  padding: 4px 8px;
  white-space: nowrap;
}
.bubble.assistant .bubble-text :deep(img) { max-width: 100%; height: auto; }

/* ── U7: Bouncing 3-dot streaming indicator (replaces blinking block cursor) ── */
.stream-dots {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: 4px;
  vertical-align: middle;
}
.stream-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: stream-bounce 1.2s ease-in-out infinite;
}
.stream-dot:nth-child(2) { animation-delay: 0.15s; }
.stream-dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes stream-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-3px); opacity: 1; }
}
@media (prefers-reduced-motion: reduce) {
  .stream-dot { animation: none; opacity: 0.7; }
}

/* ── U8: templated suggestion chips after assistant answer completes ── */
.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
  padding-top: 6px;
}
.suggestion-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  font-size: 12px;
  line-height: 1.3;
  color: var(--text-primary);
  background: var(--card-bg);
  border: 1px solid var(--separator);
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.suggestion-chip:hover {
  background: var(--bg-secondary);
  border-color: var(--van-primary-color);
  color: var(--van-primary-color);
}
.suggestion-chip:active {
  transform: scale(0.97);
}
@media (prefers-reduced-motion: reduce) {
  .suggestion-chip { transition: none; }
  .suggestion-chip:active { transform: none; }
}

/* ── Interrupted hint ── */
.interrupted-hint {
  font-size: 12px;
  color: var(--text-muted);
  padding: 4px 4px 0;
}

.bubble.assistant .bubble-text {
  background: var(--bubble-ai-bg);
  color: var(--bubble-ai-color);
  border-bottom-left-radius: 4px;
  border: 1px solid var(--bubble-ai-border);
}

.msg-time {
  font-size: 11px;
  color: var(--text-muted);
  padding: 0 4px;
}

/* ── User message footer: actions + time in same row ── */
.msg-footer {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px;
}

.msg-footer--user {
  justify-content: flex-end;
  flex-direction: row-reverse; /* time on right, actions on left */
}

/* User bubble: reduce vertical padding to match font height */
.bubble.user .bubble-text {
  background: var(--bubble-user-bg);
  color: var(--bubble-user-color);
  border-bottom-right-radius: 4px;
  padding: 6px 12px; /* Reduced from 10px 14px */
}

/* ── User message send status ── */
.send-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 2px 4px;
  justify-content: flex-end;
}
.send-status--sending {
  color: var(--text-muted);
}
.send-status--failed {
  color: #f87171;
}
.send-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: send-dot-pulse 1.2s ease-in-out infinite;
}
@keyframes send-dot-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}
@media (prefers-reduced-motion: reduce) {
  .send-status-dot { animation: none; opacity: 0.7; }
}
.send-retry-btn {
  background: none;
  border: 1px solid currentColor;
  border-radius: 4px;
  color: inherit;
  cursor: pointer;
  font-size: 11px;
  padding: 1px 6px;
  min-height: 22px;
}
.send-retry-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ── Message action buttons ── */
.msg-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

/* ── Edit mode: user message becomes input field ── */
.edit-input-wrapper {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: var(--bubble-user-bg);
  border-radius: 12px;
  border: 1px solid var(--border);
}

.edit-input-field {
  background: transparent;
  padding: 0;
}

.edit-input-field :deep(.van-field__control) {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.6;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.edit-cancel-btn,
.edit-send-btn {
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}

.edit-cancel-btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

.edit-cancel-btn:hover:not(:disabled) {
  background: var(--btn-hover-bg);
}

.edit-send-btn {
  background: var(--van-primary-color);
  border: none;
  color: #fff;
}

.edit-send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.edit-cancel-btn:disabled,
.edit-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* User message actions - positioned on right */
.msg-actions--user {
  justify-content: flex-end;
}

.message-row:hover .msg-actions,
.message-row:focus-within .msg-actions,
.message-row:active .msg-actions {
  opacity: 1;
}

/* Mobile: always show actions for touch */
@media (max-width: 768px) {
  .msg-actions {
    opacity: 1;
  }
}

/* List reorder animation */
.msg-move {
  transition: transform 0.2s ease;
}

.msg-action-btn {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.msg-action-btn:hover {
  background: var(--btn-hover-bg);
  color: var(--btn-color);
}

.msg-action-btn:disabled {
  cursor: default;
  opacity: 0.3;
}

.msg-action-btn--active {
  color: #818cf8;
}

/* ── Message enter animation ── */
.msg-list {
  display: contents;
}

.msg-enter-active {
  animation: msg-in 0.2s ease-out both;
}

@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Scroll-to-bottom floating button ── */
.scroll-to-bottom-btn {
  position: fixed;
  bottom: calc(72px + env(safe-area-inset-bottom));
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  background: var(--suggestion-bg);
  border: 1px solid var(--suggestion-border);
  border-radius: 20px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  z-index: 10;
  white-space: nowrap;
  min-height: 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.scroll-to-bottom-btn:active {
  opacity: 0.8;
}
.scroll-btn-enter-active,
.scroll-btn-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.scroll-btn-enter-from,
.scroll-btn-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

/* ── Input bar ── */
.input-bar {
  padding: 8px 16px calc(12px + env(safe-area-inset-bottom));
  background: var(--bg-header);
  border-top: 1px solid var(--border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  flex-shrink: 0;
}

@media (prefers-reduced-motion: reduce) {
  .hero-glow,
  .suggestion-card,
  .msg-enter-active,
  .phase-pulse,
  .think-icon-wrapper,
  .think-text-animated,
  .thinking-halo,
  .bubble-text--appearing {
    animation: none;
    transition: none;
  }
}

/* ── Thinking halo effect ── */
.bubble.assistant--thinking {
  position: relative;
  overflow: visible;
}

/* ── Connecting state region ── */
.connecting-region {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 4px;
  font-size: 13px;
  color: var(--text-secondary);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}
.connecting-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-secondary);
  flex-shrink: 0;
  animation: connecting-pulse 1.2s ease-in-out infinite;
}
@keyframes connecting-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.15); }
}
.connecting-label { font-size: 13px; }
.connecting-sep { color: var(--text-muted); }
.connecting-time { color: var(--text-muted); font-size: 12px; font-variant-numeric: tabular-nums; }

/* ── Shimmer sweep animation ── */
.shimmer-active {
  background-image: linear-gradient(
    90deg,
    transparent 0%,
    var(--shimmer-color, rgba(255,255,255,0.07)) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer-sweep 2s linear infinite;
}
@keyframes shimmer-sweep {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .shimmer-active { animation: none; background-image: none; }
  .connecting-dot { animation: none; opacity: 0.7; }
}

.thinking-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px 20px;
  min-height: 48px;
}

.thinking-halo {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    rgba(189, 187, 255, 0.2),
    rgba(129, 140, 248, 0.6),
    rgba(189, 187, 255, 0.2),
    rgba(129, 140, 248, 0.6),
    rgba(189, 187, 255, 0.2)
  );
  animation: halo-spin 1.5s linear infinite;
  position: relative;
}

.thinking-halo::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 50%;
  background: var(--bg);
}

@keyframes halo-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.thinking-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

/* ── Bubble content fade-in ── */
.bubble-text--appearing {
  animation: content-fade-in 0.2s ease-out;
}

@keyframes content-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* ── Error state ── */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 16px;
}

.error-msg {
  font-size: 13px;
  color: #f87171;
  margin: 0;
  line-height: 1.5;
}

.error-retry-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 8px;
  background: rgba(248, 113, 113, 0.1);
  color: #f87171;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.error-retry-btn:hover {
  background: rgba(248, 113, 113, 0.18);
  border-color: rgba(248, 113, 113, 0.45);
}

.error-retry-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

/* Light mode error adjustments */
.ai-chat-page.theme-light .error-retry-btn {
  border-color: rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.12);
}

.ai-chat-page.theme-light .error-retry-btn:hover {
  background: rgba(248, 113, 113, 0.22);
}

/* ── History pagination sentinel ── */
.history-pagination-sentinel {
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.history-load-more-text {
  font-size: 11px;
  color: var(--text-muted);
}
</style>
