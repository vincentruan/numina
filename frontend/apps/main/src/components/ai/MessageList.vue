<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import MessageGroup from '@/components/ai-chat/MessageGroup.vue'
import type { ChatMessage, PlanningStep } from '@/types/ai-chat/message-group'
import { useMessageGroups } from '@/composables/ai-chat/useMessageGroups'

const props = defineProps<{
  messages: ChatMessage[]
  isStreaming: boolean
  threadId?: string
  planningSteps?: PlanningStep[]
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

/** Index of the last assistant-type group (for planningSteps display) */
const lastAssistantGroupIndex = computed(() => {
  const groups = messageGroups.value
  for (let i = groups.length - 1; i >= 0; i--) {
    if (groups[i].type === 'assistant') return i
  }
  return -1
})

// ── Auto-scroll with user-interrupt (R5) ──
const SCROLL_THRESHOLD = 50 // px from bottom to consider "at bottom"
const isAutoScrolling = ref(true)
const userScrolledUp = ref(false)

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
  }
  scrollToBottom()
})

onUnmounted(() => {
  if (scrollRef.value) {
    scrollRef.value.removeEventListener('scroll', onScroll)
  }
})
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
        :is-loading="isStreaming && index === lastAssistantGroupIndex"
        :planning-steps="index === lastAssistantGroupIndex ? planningSteps : undefined"
        :is-last-assistant="index === lastAssistantGroupIndex"
        @suggestion-click="(text: string) => emit('suggestionClick', text)"
        @artifact-tap="(artifact: { id: string; title: string; kind: string; url?: string; path?: string }) => emit('artifactTap', artifact)"
      />
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
</style>
