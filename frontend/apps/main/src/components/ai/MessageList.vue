<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MessageGroup from '@/components/ai-chat/MessageGroup.vue'
import StreamingIndicator from '@/components/ai-chat/StreamingIndicator.vue'
import type { ChatMessage, MessageGroup as MessageGroupType } from '@/types/ai-chat/message-group'
import type { PlanStep } from '@/types/agent-stream'
import { useMessageGroups } from '@/composables/ai-chat/useMessageGroups'
import { extractLegacyFields } from '@/utils/ai-chat/messageAdapter'

const props = defineProps<{
  messages: ChatMessage[]
  isStreaming: boolean
  threadId?: string
  canBranch?: boolean
  branchingMessageId?: string | null
  answeredInterruptIds?: Set<string>
  supersededGroups?: Map<string, MessageGroupType[]>
  supersededVersionIndex?: Map<string, number>
}>()

const emit = defineEmits<{
  retry: []
  stop: []
  suggestionClick: [text: string]
  artifactTap: [artifact: { id: string; title: string; kind: string; url?: string; path?: string }]
  branch: [messageId: string, messageIds: string[]]
  clarificationSubmit: [payload: { threadId: string; interruptId: string; answer: string }]
  feedback: [messageId: string, value: 1 | -1]
  showPrevVersion: [humanMessageId: string]
  showNextVersion: [humanMessageId: string]
}>()

const { t } = useI18n()

const scrollRef = ref<HTMLElement | null>(null)

// Group messages for display (dedupe + group into DeerFlow 6-type structure)
const messageGroups = useMessageGroups(toRef(props, 'messages'))

/**
 * Index of the last assistant-origin group (assistant / assistant:processing /
 * assistant:clarification / etc.) so the streaming/loading state reaches the
 * group that is currently producing content - including a tool-call-only
 * ``assistant:processing`` group that has no text content yet. Previously this
 * only matched ``type === 'assistant'``, so during tool execution (when the
 * last group is ``assistant:processing``) isLoading never reached ChainOfThought
 * and pending tool calls couldn't show a running spinner.
 */
const lastAssistantGroupIndex = computed(() => {
  const groups = visibleMessageGroups.value
  for (let i = groups.length - 1; i >= 0; i--) {
    if (groups[i].type === 'assistant' || groups[i].type.startsWith('assistant:')) return i
  }
  return -1
})

/**
 * Shared helper: map each group index → the human message id of its turn.
 * A "turn" starts at a human message and includes all subsequent assistant/tool
 * groups until the next human message. Uses the human message's stable `id`
 * (not positional index) so the mapping survives visible-array shifts when
 * superseded groups have a different count than live groups.
 */
function computeHumanMessageIds(groups: MessageGroupType[]): Map<number, string> {
  const ids = new Map<number, string>()
  let currentHumanId: string | undefined
  for (let i = 0; i < groups.length; i++) {
    if (groups[i].type === 'human') {
      const humanMsg = groups[i].messages.find(m => m.type === 'human')
      currentHumanId = humanMsg?.id
    }
    if (currentHumanId) ids.set(i, currentHumanId)
  }
  return ids
}

/**
 * Map each VISIBLE group index → the human message id of its turn.
 * Computed over visibleMessageGroups so the indices correspond to the
 * positions the template iterates.
 */
const groupToHumanMessageId = computed(() =>
  computeHumanMessageIds(visibleMessageGroups.value),
)

/**
 * Visible groups with retry version pagination applied.
 *
 * When the user retried a turn and there are superseded groups, only the
 * version the user is currently viewing is shown.
 *
 * Algorithm: for each turn that has superseded groups, check the version index.
 * - Version 1 (default): show the LIVE groups from messageGroups (the new response).
 * - Version 0: replace the live assistant groups for that turn with the superseded ones.
 *
 * Uses stable human message ids (not positional turn indices) to look up
 * superseded/version maps, so the mapping is immune to visible-array shifts
 * when an earlier turn's superseded groups have a different count.
 */
const visibleMessageGroups = computed(() => {
  const groups = messageGroups.value
  const superseded = props.supersededGroups
  const versionMap = props.supersededVersionIndex

  if (!superseded || superseded.size === 0) return groups

  // Compute human message id for each raw group (shared helper).
  const humanIds = computeHumanMessageIds(groups)

  // Build the result: for turns with version 0, replace live assistant groups
  // with superseded groups.
  const result: MessageGroupType[] = []
  let i = 0
  while (i < groups.length) {
    const hId = humanIds.get(i) ?? ''
    const verIdx = versionMap?.get(hId) ?? 1

    if (hId && superseded.has(hId) && verIdx === 0) {
      // Keep the human group, replace the rest with superseded groups.
      result.push(groups[i]) // human group
      i++
      // Skip all non-human groups for this turn.
      while (i < groups.length && humanIds.get(i) === hId && groups[i].type !== 'human') {
        i++
      }
      // Inject superseded groups.
      const supGroups = superseded.get(hId)
      if (supGroups) {
        result.push(...supGroups)
      }
    } else {
      result.push(groups[i])
      i++
    }
  }

  return result
})

/**
 * Human message ids that have superseded groups (for pagination control placement).
 * Uses the same stable string keys as supersededGroups.
 */
const turnsWithSuperseded = computed(() => {
  const superseded = props.supersededGroups
  if (!superseded || superseded.size === 0) return new Set<string>()
  return new Set(superseded.keys())
})

/**
 * Show the three-dot thinking indicator while the user's message has been sent
 * but no assistant-type group exists yet (the AI hasn't produced any text or
 * tool-call chunk). Once an assistant / assistant:processing / etc. group
 * appears, that group renders its own streaming indicator and this placeholder
 * hides. Without this, the only feedback during the first model round-trip is
 * the input-box button state, which looks like the page is stuck.
 */
const showThinkingIndicator = computed(() => {
  if (!props.isStreaming) return false
  const groups = messageGroups.value
  if (groups.length === 0) return false
  return groups[groups.length - 1].type === 'human'
})

/**
 * Get planSteps from the previous group (for detecting redundant completion summaries).
 * DeerFlow pattern: when todos are complete, the final "已完成！" message is redundant
 * because the todo list itself is the final output.
 */
function getPrevGroupPlanSteps(index: number): PlanStep[] | undefined {
  if (index === 0) return undefined
  const prevGroup = visibleMessageGroups.value[index - 1]
  if (!prevGroup) return undefined
  // Only look at the first AI message in the previous group
  const firstAiMsg = prevGroup.messages.find(m => m.type === 'ai')
  if (!firstAiMsg) return undefined
  const legacy = extractLegacyFields(firstAiMsg)
  return legacy?.planSteps
}

/**
 * Check if the current group is the last group for its turn.
 * Used to position the pagination control after the last group of a retried turn.
 */
function lastGroupForTurn(index: number): boolean {
  const groups = visibleMessageGroups.value
  if (index >= groups.length - 1) return true
  const currentHumanId = groupToHumanMessageId.value.get(index) ?? ''
  const nextHumanId = groupToHumanMessageId.value.get(index + 1) ?? ''
  return currentHumanId !== nextHumanId
}

// ── Auto-scroll with user-interrupt (R5) + MutationObserver (P1) ──
const SCROLL_THRESHOLD = 50 // px from bottom to consider "at bottom"
const isAutoScrolling = ref(true)
const userScrolledUp = ref(false)
let _mutationObserver: MutationObserver | null = null
let _scrollDebounceTimer: ReturnType<typeof setTimeout> | null = null

/** Check if the scroll position is near the bottom */
function isNearBottom(): boolean {
  const el = scrollRef.value
  if (!el) return true
  return el.scrollTop + el.clientHeight >= el.scrollHeight - SCROLL_THRESHOLD
}

/** Scroll to the bottom smoothly */
function scrollToBottom() {
  const el = scrollRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

/**
 * Debounced scroll triggered by MutationObserver.
 * Uses requestAnimationFrame + 50ms debounce to batch rapid DOM changes
 * (e.g. markdown image load, table render, code block expansion).
 */
function onMutationScroll() {
  if (!isAutoScrolling.value) return
  if (_scrollDebounceTimer) clearTimeout(_scrollDebounceTimer)
  _scrollDebounceTimer = setTimeout(() => {
    requestAnimationFrame(() => {
      if (isAutoScrolling.value) {
        scrollToBottom()
      }
    })
  }, 50)
}

/** Set up MutationObserver to catch async DOM height changes */
function setupMutationObserver() {
  const el = scrollRef.value
  if (!el) return
  // Clean up previous observer if any
  _mutationObserver?.disconnect()
  _mutationObserver = new MutationObserver(() => {
    onMutationScroll()
  })
  _mutationObserver.observe(el, {
    childList: true,
    subtree: true,
    characterData: true,
  })
}

/** Handle scroll events: detect user scroll-up vs at-bottom */
function onScroll() {
  if (!scrollRef.value) return
  if (isNearBottom()) {
    // User scrolled back to bottom — resume auto-scroll
    userScrolledUp.value = false
    isAutoScrolling.value = true
  } else {
    // User scrolled up — pause auto-scroll
    userScrolledUp.value = true
    isAutoScrolling.value = false
  }
}

/** "回到底部" button click */
function onScrollToBottom() {
  scrollToBottom()
  userScrolledUp.value = false
  isAutoScrolling.value = true
}

// Auto-scroll to bottom on new messages (only if user hasn't scrolled up)
watch(
  () => props.messages.length,
  async () => {
    await nextTick()
    if (isAutoScrolling.value) {
      scrollToBottom()
    }
  }
)

// Also auto-scroll during streaming as content grows (last message content changes)
watch(
  () => props.messages[props.messages.length - 1]?.content,
  async () => {
    if (!props.isStreaming) return
    await nextTick()
    if (isAutoScrolling.value) {
      scrollToBottom()
    }
  }
)

// Reset scroll state when streaming starts (new user message)
watch(
  () => props.isStreaming,
  (streaming) => {
    if (streaming) {
      // User just sent a message — scroll to bottom and enable auto-scroll
      isAutoScrolling.value = true
      userScrolledUp.value = false
      nextTick(() => scrollToBottom())
    }
  }
)

onMounted(() => {
  if (scrollRef.value) {
    scrollRef.value.addEventListener('scroll', onScroll, { passive: true })
    setupMutationObserver()
  }
  scrollToBottom()
})

onUnmounted(() => {
  if (scrollRef.value) {
    scrollRef.value.removeEventListener('scroll', onScroll)
  }
  _mutationObserver?.disconnect()
  _mutationObserver = null
  if (_scrollDebounceTimer) {
    clearTimeout(_scrollDebounceTimer)
    _scrollDebounceTimer = null
  }
})
</script>

<template>
  <div ref="scrollRef" class="message-list">
    <div v-if="messages.length === 0" class="message-list-empty">
      <p>{{ t('aiChat.startConversation') }}</p>
    </div>
    <div v-else class="message-list-content">
      <template v-for="(group, index) in visibleMessageGroups" :key="group.id ?? index">
        <MessageGroup
          :group="group"
          :thread-id="threadId"
          :is-loading="isStreaming && index === lastAssistantGroupIndex"
          :is-last-assistant="index === lastAssistantGroupIndex"
          :can-branch="canBranch"
          :branching-message-id="branchingMessageId"
          :answered-interrupt-ids="answeredInterruptIds"
          :prev-group-plan-steps="getPrevGroupPlanSteps(index)"
          @suggestion-click="(text: string) => emit('suggestionClick', text)"
          @artifact-tap="(artifact: { id: string; title: string; kind: string; url?: string; path?: string }) => emit('artifactTap', artifact)"
          @branch="(messageId: string, messageIds: string[]) => emit('branch', messageId, messageIds)"
          @clarification-submit="(payload: { threadId: string; interruptId: string; answer: string }) => emit('clarificationSubmit', payload)"
          @feedback="(messageId: string, value: 1 | -1) => emit('feedback', messageId, value)"
          @retry="emit('retry')"
        />
        <!-- Retry version pagination control (DeerFlow §2.1: < prev/next >) -->
        <div
          v-if="turnsWithSuperseded.has(groupToHumanMessageId.get(index) ?? '') && lastGroupForTurn(index)"
          class="version-pagination"
        >
          <button
            v-if="supersededVersionIndex?.get(groupToHumanMessageId.get(index) ?? '') === 1"
            class="version-nav-btn"
            type="button"
            :aria-label="t('aiChat.prevVersion')"
            @click="emit('showPrevVersion', groupToHumanMessageId.get(index) ?? '')"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            <span>{{ t('aiChat.prevVersion') }}</span>
          </button>
          <button
            v-if="supersededVersionIndex?.get(groupToHumanMessageId.get(index) ?? '') === 0"
            class="version-nav-btn"
            type="button"
            :aria-label="t('aiChat.nextVersion')"
            @click="emit('showNextVersion', groupToHumanMessageId.get(index) ?? '')"
          >
            <span>{{ t('aiChat.nextVersion') }}</span>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </button>
        </div>
      </template>
      <!-- Three-dot thinking indicator: fills the gap between send and first AI chunk -->
      <div v-if="showThinkingIndicator" class="thinking-placeholder">
        <StreamingIndicator :visible="true" />
      </div>
    </div>

    <!-- "回到底部" floating button (shown when user scrolled up) -->
    <Transition name="scroll-btn">
      <button
        v-if="userScrolledUp"
        class="scroll-to-bottom-btn"
        type="button"
        :aria-label="t('aiChat.scrollToBottom')"
        @click="onScrollToBottom"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
    </Transition>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: 20px; /* Small gap above the in-flow InputBox below */
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
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

/* Three-dot thinking bubble shown while waiting for the first AI chunk */
.thinking-placeholder {
  padding: 10px 16px;
  background: var(--bubble-ai-bg, rgba(189, 187, 255, 0.12));
  border-radius: 12px;
  width: fit-content;
  max-width: 80%;
}

/* "回到底部" floating button */
.scroll-to-bottom-btn {
  position: sticky;
  bottom: 16px;
  align-self: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--van-primary-color, #6366f1);
  color: #fff;
  border: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: transform 0.15s ease;
}

.scroll-to-bottom-btn:hover {
  transform: scale(1.05);
}

.scroll-to-bottom-btn:active {
  transform: scale(0.95);
}

/* Scroll button transition */
.scroll-btn-enter-active,
.scroll-btn-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.scroll-btn-enter-from,
.scroll-btn-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.8);
}

/* Retry version pagination (DeerFlow §2.1: < prev/next > control) */
.version-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 0;
}

.version-nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: var(--van-background-2, #f7f8fa);
  color: var(--van-text-color-2, #646566);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.version-nav-btn:hover {
  background: var(--van-active-color, rgba(0, 0, 0, 0.06));
  color: var(--van-text-color, #323233);
}

.version-nav-btn:active {
  transform: scale(0.96);
}
</style>
