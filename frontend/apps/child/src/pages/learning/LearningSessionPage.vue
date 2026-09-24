<template>
  <div class="learning-session-page">
    <RoleShimmer v-if="loading" variant="clay-pulse" />

    <template v-else-if="session">
      <!-- Back navigation -->
      <div class="session-nav">
        <button class="back-btn" @click="goBack">
          &larr; {{ t('common.back') }}
        </button>
      </div>

      <!-- Session topic info -->
      <div class="session-header">
        <div class="session-header__icon">🎓</div>
        <div class="session-header__info">
          <h2 class="session-header__title">{{ topicDisplayNameText }}</h2>
          <div class="session-header__meta">
            <span
              class="session-badge"
              :class="session.session_type === 'tutorial' ? 'badge--tutorial' : 'badge--assessment'"
            >
              {{ t(`learning.status.${session.session_type || 'learning'}`) }}
            </span>
            <span v-if="isStreaming" class="status-indicator status-indicator--active">
              {{ t('learning.session.streaming') }}
            </span>
            <span v-else-if="isCompleted" class="status-indicator status-indicator--done">
              {{ t('learning.session.completed') }}
            </span>
          </div>
        </div>
      </div>

      <!-- Chat messages -->
      <div class="chat-area" ref="chatAreaRef">
        <div v-if="messages.length === 0 && !isStreaming" class="chat-empty">
          <div class="chat-empty__icon">💬</div>
          <p class="chat-empty__title">{{ t('learning.session.chatTitle') }}</p>
          <p class="chat-empty__desc">{{ t('learning.session.chatDesc') }}</p>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="chat-msg"
          :class="`chat-msg--${msg.role}`"
        >
          <div class="chat-msg__bubble">
            <!-- Tool call display (collapsible) -->
            <details v-if="msg.toolCall" class="tool-details">
              <summary class="tool-details__summary">
                🔧 {{ msg.toolCall.name }}
              </summary>
              <pre class="tool-details__content">{{ JSON.stringify(msg.toolCall.arguments, null, 2) }}</pre>
            </details>

            <!-- Tool result display (collapsible) -->
            <details v-if="msg.toolResult" class="tool-details">
              <summary class="tool-details__summary">
                📋 {{ msg.toolResult.name }}
              </summary>
              <pre class="tool-details__content">{{ typeof msg.toolResult.output === 'string' ? msg.toolResult.output : JSON.stringify(msg.toolResult.output, null, 2) }}</pre>
            </details>

            <!-- Regular text content -->
            <div v-if="msg.content" class="chat-msg__text">{{ msg.content }}</div>
          </div>
        </div>

        <!-- Streaming text (current response being typed) -->
        <div v-if="currentStreamText" class="chat-msg chat-msg--assistant">
          <div class="chat-msg__bubble">
            <div class="chat-msg__text">{{ currentStreamText }}</div>
            <span class="typing-cursor">|</span>
          </div>
        </div>

        <!-- Error display -->
        <div v-if="chatError" class="chat-error">
          <p>{{ chatError }}</p>
          <button class="btn-retry" @click="onRetry">{{ t('common.retry') }}</button>
        </div>
      </div>

      <!-- Input area (enabled when streaming or completed — multi-turn tutorial) -->
      <div v-if="session.thread_id" class="chat-input-area">
        <input
          v-model="inputText"
          class="chat-input"
          type="text"
          :placeholder="t('learning.session.inputPlaceholder')"
          :disabled="isStreaming"
          @keyup.enter="onSendMessage"
        />
        <button
          class="chat-send-btn"
          :disabled="isStreaming || !inputText.trim()"
          @click="onSendMessage"
        >
          {{ t('learning.session.send') }}
        </button>
      </div>

      <!-- Session actions -->
      <div class="session-actions">
        <button
          class="btn-finish"
          :disabled="ending"
          @click="onEndSession"
        >
          {{ ending ? t('common.loading') : t('learning.session.finish') }}
        </button>
      </div>
    </template>

    <!-- Error state -->
    <div v-else-if="loadError" class="error-state">
      <p>{{ loadError }}</p>
      <button class="btn-secondary" @click="load">{{ t('common.retry') }}</button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningSession' })

import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { showSuccessToast, showFailToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import { useLearningChat } from '@/composables/useLearningChat'
import { getSession, getTopicDetail, endSession, type SessionResponse, type TopicResponse } from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'

const { t } = useI18n()
const { topicDisplayName } = useLocalizedTopic()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const sessionId = computed(() => route.params.id as string)

const loading = ref(true)
const ending = ref(false)
const loadError = ref('')
const session = ref<SessionResponse | null>(null)
const topic = ref<TopicResponse | null>(null)
const inputText = ref('')
const chatAreaRef = ref<HTMLElement | null>(null)

const {
  messages,
  status,
  currentStreamText,
  error: chatError,
  isStreaming,
  isCompleted,
  startAssessment,
  sendMessage,
  disconnect,
} = useLearningChat()

const topicDisplayNameText = computed(() => {
  if (!topic.value) return ''
  return topicDisplayName(topic.value)
})

// Auto-scroll to bottom when new messages arrive or streaming text updates
watch([messages, currentStreamText], () => {
  nextTick(() => {
    if (chatAreaRef.value) {
      chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
    }
  })
}, { deep: true })

function goBack() {
  router.push('/learning')
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const sessionData = await getSession(sessionId.value)
    session.value = sessionData

    // Load topic detail for display
    if (sessionData.topic_id) {
      const topicData = await getTopicDetail(sessionData.topic_id)
      topic.value = topicData
    }

    // Start the assessment stream if session has a thread_id
    if (sessionData.thread_id) {
      await startAssessment(sessionId.value)
    }
  } catch {
    loadError.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function onSendMessage() {
  if (!inputText.value.trim() || isStreaming.value) return
  const text = inputText.value
  inputText.value = ''
  await sendMessage(sessionId.value, text)
}

function onRetry() {
  if (session.value?.thread_id) {
    startAssessment(sessionId.value)
  }
}

async function onEndSession() {
  if (ending.value) return
  ending.value = true
  disconnect()
  try {
    await endSession(sessionId.value)
    showSuccessToast(t('learning.session.ended'))
    router.push('/learning')
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    ending.value = false
  }
}

onMounted(async () => {
  increment()
  try {
    await load()
  } finally {
    decrement()
  }
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.learning-session-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.session-nav {
  margin-bottom: 16px;
}

.back-btn {
  background: none;
  border: none;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  cursor: pointer;
  padding: 4px 0;
}

.session-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
}

.session-header__icon {
  font-size: 32px;
  line-height: 1;
}

.session-header__info {
  flex: 1;
  min-width: 0;
}

.session-header__title {
  font-family: Inter, sans-serif;
  font-size: 17px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-header__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-badge {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
}

.badge--tutorial {
  background: rgba(var(--color-primary-rgb, 59, 130, 246), 0.12);
  color: var(--color-primary, #3b82f6);
}

.badge--assessment {
  background: rgba(var(--color-brand-ochre-rgb, 234, 179, 8), 0.15);
  color: var(--color-brand-ochre, #b45309);
}

.status-indicator {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 500;
}

.status-indicator--active {
  color: var(--color-primary, #3b82f6);
}

.status-indicator--done {
  color: var(--color-success, #22c55e);
}

/* Chat area */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 200px;
  max-height: 60vh;
  overflow-y: auto;
  margin-bottom: 16px;
  padding: 4px;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
  background: var(--color-surface-soft);
  border: 1px dashed var(--color-hairline);
  border-radius: var(--radius-lg);
  text-align: center;
}

.chat-empty__icon {
  font-size: 48px;
  line-height: 1;
  margin-bottom: 16px;
}

.chat-empty__title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 8px;
}

.chat-empty__desc {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin: 0;
  line-height: 1.5;
}

/* Chat messages */
.chat-msg {
  display: flex;
}

.chat-msg--user {
  justify-content: flex-end;
}

.chat-msg--assistant,
.chat-msg--tool {
  justify-content: flex-start;
}

.chat-msg__bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: var(--radius-lg);
  font-family: Inter, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-msg--user .chat-msg__bubble {
  background: var(--color-primary, #3b82f6);
  color: var(--color-on-dark, #fff);
  border-bottom-right-radius: 4px;
}

.chat-msg--assistant .chat-msg__bubble {
  background: var(--color-surface-card);
  color: var(--color-ink);
  border-bottom-left-radius: 4px;
}

.chat-msg--tool .chat-msg__bubble {
  background: var(--color-surface-soft);
  color: var(--color-body);
  max-width: 90%;
}

.chat-msg__text {
  white-space: pre-wrap;
}

.typing-cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--color-primary, #3b82f6);
  font-weight: bold;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Tool details (collapsible) */
.tool-details {
  margin: 4px 0;
  font-size: 12px;
}

.tool-details__summary {
  cursor: pointer;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  color: var(--color-body);
  padding: 2px 0;
}

.tool-details__content {
  background: var(--color-canvas);
  border-radius: var(--radius-md);
  padding: 8px;
  margin: 4px 0 0;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--color-body);
}

/* Chat error */
.chat-error {
  padding: 12px 16px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: var(--radius-md);
  text-align: center;
}

.chat-error p {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: #ef4444;
  margin: 0 0 8px;
}

.btn-retry {
  background: none;
  border: 1px solid #ef4444;
  color: #ef4444;
  border-radius: var(--radius-md);
  padding: 6px 16px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  cursor: pointer;
}

/* Input area */
.chat-input-area {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 8px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
}

.chat-input {
  flex: 1;
  border: none;
  background: transparent;
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-ink);
  outline: none;
  padding: 8px 4px;
  min-height: 40px;
}

.chat-input::placeholder {
  color: var(--color-hairline);
}

.chat-input:disabled {
  opacity: 0.5;
}

.chat-send-btn {
  background: var(--color-primary, #3b82f6);
  color: var(--color-on-dark, #fff);
  border: none;
  border-radius: var(--radius-md);
  padding: 8px 16px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  min-height: 40px;
  transition: transform 0.1s;
}

.chat-send-btn:active {
  transform: scale(0.95);
}

.chat-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Session actions */
.session-actions {
  margin-top: auto;
}

.btn-finish {
  width: 100%;
  background: var(--color-surface-soft);
  color: var(--color-ink);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  padding: 14px;
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  min-height: 48px;
  transition: transform 0.1s;
}

.btn-finish:active {
  transform: scale(0.97);
}

.btn-finish:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Error state */
.error-state {
  text-align: center;
  padding: 40px 20px;
}

.error-state p {
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-body);
  margin: 0 0 16px;
}

.btn-secondary {
  background: var(--color-surface-soft);
  color: var(--color-ink);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  padding: 12px 24px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
</style>
