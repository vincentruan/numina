<script setup lang="ts">
import { ref, computed } from 'vue'
import { showFailToast, showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { updateThread } from '@/api/ai-chat'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'
import TokenUsage from '@/components/ai-chat/TokenUsage.vue'
import IIcon from '@/components/IIcon.vue'
import { getAgentIcon, isEmoji } from '@/utils/agent'
import type { ThreadSession } from '@/types/ai-chat/session'
import type { Agent } from '@/types/agent'

defineOptions({ name: 'ChatHeader' })

const NUMINA_AGENT_NAME = 'numina'

const props = defineProps<{
  activeThreadId: string | null
  sessions: ThreadSession[]
  tokenUsageTotal?: number
  isStreaming?: boolean
  activeAgent: Agent | null
}>()

const emit = defineEmits<{
  back: []
  history: []
  newChat: []
  titleUpdated: [threadId: string, newTitle: string]
}>()

const router = useRouter()
const { t } = useI18n()

// Agent info popup state
const showAgentInfo = ref(false)

// Edit title state
const showEditTitleDialog = ref(false)
const editTitleInput = ref('')
const isUpdatingTitle = ref(false)

// Header title: show thread title or "New Chat"
const headerTitle = computed(() => {
  if (!props.activeThreadId) return t('aiChat.newChat')
  const session = props.sessions.find(s => s.thread_id === props.activeThreadId)
  return session?.title || t('aiChat.newChat')
})

// Check if title can be edited - only when there's an active thread AND the
// title has been generated (not the default "新对话"). Before the first
// message or while the LLM title is still pending, the edit button is hidden.
const canEditTitle = computed(() => {
  return !!props.activeThreadId && headerTitle.value !== t('aiChat.newChat')
})

// Check if title needs scroll animation (titles >8 chars overflow container)
const titleNeedsScroll = computed(() => {
  return headerTitle.value.length > 8
})

function onToggleAgentInfo() {
  showAgentInfo.value = !showAgentInfo.value
}

function onEditTitle() {
  // If the title is still the default (LLM title not yet generated), start
  // with an empty input so the user can type a custom title from scratch.
  editTitleInput.value = headerTitle.value === t('aiChat.newChat') ? '' : headerTitle.value
  showEditTitleDialog.value = true
}

async function onConfirmEditTitle() {
  if (isUpdatingTitle.value) return // Prevent double submission
  if (!props.activeThreadId || !editTitleInput.value.trim()) return
  const newTitle = editTitleInput.value.trim()
  isUpdatingTitle.value = true
  try {
    await updateThread(props.activeThreadId, { title: newTitle })
    showSuccessToast(t('aiChat.renameSessionSuccess'))
    showEditTitleDialog.value = false // Close dialog only on success
    emit('titleUpdated', props.activeThreadId, newTitle)
  } catch {
    showFailToast(t('aiChat.renameSessionFailed'))
    // Keep dialog open on failure so user can retry
  } finally {
    isUpdatingTitle.value = false
  }
}

function onBack() {
  emit('back')
  router.push('/ai')
}

function onOpenHistory() {
  emit('history')
  router.push('/ai/chat/history')
}

function onNewChat() {
  emit('newChat')
}
</script>

<template>
  <div class="chat-header">
    <button class="header-btn" :aria-label="t('common.back')" @click="onBack">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="15 18 9 12 15 6"/>
      </svg>
    </button>
    <button class="header-btn" :aria-label="t('aiChat.historyAria')" @click="onOpenHistory">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
    </button>
    <!-- Agent logo button — shows popup with name + description on click -->
    <button
      v-if="activeAgent"
      class="header-btn header-agent-logo-btn"
      :aria-label="t('aiChat.agentInfoAria')"
      @click="onToggleAgentInfo"
    >
      <AIBrainIcon v-if="activeAgent.agent_name === NUMINA_AGENT_NAME" :active="true" />
      <span v-else-if="isEmoji(getAgentIcon(activeAgent.icon))" class="header-agent-logo-emoji">
        {{ getAgentIcon(activeAgent.icon) || '🤖' }}
      </span>
      <IIcon v-else :icon="getAgentIcon(activeAgent.icon)" size="20" :color="activeAgent.color || 'var(--van-primary-color)'" />
    </button>
    <!-- Title wrap: title (truncated or scrolling) + inline edit button -->
    <div class="header-title-wrap">
      <div class="header-title-container" :class="{ 'needs-scroll': titleNeedsScroll }">
        <h1 class="header-title">{{ headerTitle }}</h1>
      </div>
      <button
        v-if="canEditTitle"
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
    <!-- Agent info popup - teleported to body to escape .chat-header's
         stacking context (backdrop-filter creates one, trapping fixed children
         below sibling panels like the tool-call steps panel). -->
    <Teleport v-if="showAgentInfo && activeAgent" to="body">
      <div
        class="agent-info-backdrop"
        @click="showAgentInfo = false"
      />
      <div
        class="agent-info-popup"
        role="dialog"
        aria-label="Agent information"
        @click.stop
      >
        <div class="agent-info-header">
          <span class="agent-info-icon" aria-hidden="true">
            <AIBrainIcon v-if="activeAgent.agent_name === NUMINA_AGENT_NAME" :active="true" />
            <span v-else-if="isEmoji(getAgentIcon(activeAgent.icon))">
              {{ getAgentIcon(activeAgent.icon) || '🤖' }}
            </span>
            <IIcon v-else :icon="getAgentIcon(activeAgent.icon)" size="24" :color="activeAgent.color || 'var(--van-primary-color)'" />
          </span>
          <span class="agent-info-name">{{ activeAgent.display_name }}</span>
        </div>
        <p class="agent-info-description">{{ activeAgent.description || t('aiChat.agentNoDescription') }}</p>
      </div>
    </Teleport>
    <div class="header-actions">
      <TokenUsage v-if="activeThreadId" :thread-id="activeThreadId" :refresh-trigger="tokenUsageTotal" :is-streaming="isStreaming" />
      <button class="header-btn" :aria-label="t('aiChat.newChatAria')" @click="onNewChat">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </button>
    </div>

    <!-- Edit title dialog
         teleport="body" is required: .chat-header has backdrop-filter which
         creates a containing block for position:fixed descendants, trapping
         the dialog inside the 50px header without it. -->
    <van-dialog
      v-model:show="showEditTitleDialog"
      teleport="body"
      :title="t('aiChat.editTitle')"
      show-cancel-button
      :loading="isUpdatingTitle"
      @confirm="onConfirmEditTitle"
      @cancel="showEditTitleDialog = false"
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
  </div>
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  padding: 0 4px;
  padding-top: env(safe-area-inset-top);
  height: calc(50px + env(safe-area-inset-top));
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
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
  color: rgba(0, 0, 0, 0.7);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.header-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.9);
}

/* Agent logo button */
.header-agent-logo-btn {
  position: relative;
}

.header-agent-logo-emoji {
  font-size: 20px;
  line-height: 1;
}

/* 数鸣 AIBrainIcon: strip the 3D button chrome so the brain mark scales to
 * match neighboring 20px header icons (mirrors InputBox.vue's handling). */
.header-agent-logo-btn :deep(.ai-button-wrapper),
.agent-info-icon :deep(.ai-button-wrapper) {
  transform: none !important;
}

.header-agent-logo-btn :deep(.ai-button-3d),
.agent-info-icon :deep(.ai-button-3d) {
  width: 32px;
  height: 32px;
  padding: 0;
  box-shadow: none;
  background: transparent;
  border: none;
  transform: none !important;
}

.header-agent-logo-btn :deep(.fg-icon),
.agent-info-icon :deep(.fg-icon) {
  width: 20px;
  height: 20px;
}

.header-agent-logo-btn :deep(.bg-icon),
.agent-info-icon :deep(.bg-icon) {
  width: 18px;
  height: 18px;
}

.header-title-wrap {
  /* flex:1 so the title region fills the space between the agent logo and
   * the right-pinned actions; the title then centers within this region
   * instead of shrinking to content width and hugging the left edge. */
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 0 4px;
  gap: 4px;
}

.header-title-container {
  min-width: 0;
  /* Cap width so very long titles truncate/scroll rather than squeeze the
   * edit button off-screen; scales up on tablets/PCs for breathing room. */
  max-width: clamp(120px, 22vw, 320px);
  overflow: hidden;
}

.header-title-container.needs-scroll {
  max-width: clamp(140px, 26vw, 360px);
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.9);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  /* Center the title text within its container. */
  text-align: center;
}

/* Scroll animation for long titles */
.header-title-container.needs-scroll .header-title {
  display: inline-block;
  max-width: none;
  text-overflow: unset;
  overflow: visible;
  animation: title-scroll 8s linear infinite;
  padding-right: 20px; /* Space for visual gap before repeat */
}

@keyframes title-scroll {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
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
  color: rgba(0, 0, 0, 0.4);
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s, color 0.15s;
}

.header-edit-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: rgba(0, 0, 0, 0.7);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  /* Pin to the right edge so token-usage / new-chat buttons stay fixed
   * regardless of title length. */
  margin-left: auto;
  flex-shrink: 0;
}

/* Agent info popup */
.agent-info-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
}

.agent-info-popup {
  position: fixed;
  top: calc(50px + env(safe-area-inset-top) + 4px);
  left: 108px;
  z-index: 2001;
  background: #ffffff;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  min-width: 160px;
  max-width: 220px;
  padding: 12px 14px;
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

.agent-info-name {
  font-size: 15px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.9);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-info-description {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.6);
  line-height: 1.5;
  margin: 0;
  word-break: break-word;
}

/* Dark mode
 * Wrap the FULL selector in :global() - Vue scoped CSS only scopes the last
 * simple selector outside :global(), so `:global([data-theme='dark']) .x`
 * compiles to `[data-theme='dark'] .x` (no [data-v-xxx]) and never matches.
 * See AIChatInput.vue:472 for the same gotcha. */
:global([data-theme='dark'] .chat-header) {
  background: rgba(var(--bg-primary-rgb, 15, 17, 23), 0.95);
  border-bottom-color: rgba(255, 255, 255, 0.06);
}

:global([data-theme='dark'] .header-btn) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .header-btn:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

:global([data-theme='dark'] .header-title) {
  color: var(--text-primary);
}

:global([data-theme='dark'] .header-edit-btn) {
  color: var(--text-secondary);
}

:global([data-theme='dark'] .header-edit-btn:hover) {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-primary);
}

:global([data-theme='dark'] .agent-info-popup) {
  /* Fully opaque background to prevent chat content from bleeding through
   * and overlapping the popup text. Use --bg-tertiary (#12122a) to match
   * other elevated dark surfaces (cards, action sheets). */
  background: var(--bg-tertiary);
  border-color: rgba(255, 255, 255, 0.06);
  box-shadow: 0 8px 24px rgba(1, 1, 32, 0.2);
}

:global([data-theme='dark'] .agent-info-name) {
  color: var(--text-primary);
}

:global([data-theme='dark'] .agent-info-description) {
  color: var(--text-secondary);
}
</style>