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
          <h2 class="session-header__title">{{ topicDisplayName }}</h2>
          <p class="session-header__type">{{ t(`learning.status.${session.session_type || 'learning'}`) }}</p>
        </div>
      </div>

      <!-- Chat area placeholder -->
      <!-- TODO: Integrate DeerFlow SSE streaming via adapted useThreadChat composable -->
      <div class="chat-area">
        <div v-if="session.thread_id" class="chat-placeholder">
          <div class="chat-placeholder__icon">💬</div>
          <p class="chat-placeholder__title">{{ t('learning.session.chatTitle') }}</p>
          <p class="chat-placeholder__desc">{{ t('learning.session.chatDesc') }}</p>
          <div class="chat-placeholder__thread">
            <span class="thread-label">Thread:</span>
            <span class="thread-id">{{ session.thread_id }}</span>
          </div>
        </div>
        <div v-else class="chat-placeholder">
          <div class="chat-placeholder__icon">📝</div>
          <p class="chat-placeholder__title">{{ t('learning.session.noThread') }}</p>
        </div>
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
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="btn-secondary" @click="load">{{ t('common.retry') }}</button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningSession' })

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import { getSession, getTopicDetail, type SessionResponse, type TopicResponse } from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const sessionId = computed(() => route.params.id as string)

const loading = ref(true)
const ending = ref(false)
const error = ref('')
const session = ref<SessionResponse | null>(null)
const topic = ref<TopicResponse | null>(null)

const topicDisplayName = computed(() => {
  if (!topic.value) return ''
  if (locale.value.startsWith('zh') && topic.value.name_zh) return topic.value.name_zh
  return topic.value.name || topic.value.topic_key
})

function goBack() {
  router.push('/learning')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const sessionData = await getSession(sessionId.value)
    session.value = sessionData

    // Load topic detail for display
    if (sessionData.topic_id) {
      const topicData = await getTopicDetail(sessionData.topic_id)
      topic.value = topicData
    }
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function onEndSession() {
  if (ending.value) return
  ending.value = true
  try {
    // TODO: Call end session API when available
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

.session-header__type {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  margin: 0;
}

/* Chat area */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 300px;
  margin-bottom: 20px;
}

.chat-placeholder {
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

.chat-placeholder__icon {
  font-size: 48px;
  line-height: 1;
  margin-bottom: 16px;
}

.chat-placeholder__title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 8px;
}

.chat-placeholder__desc {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  margin: 0 0 16px;
  line-height: 1.5;
}

.chat-placeholder__thread {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
}

.thread-label {
  color: var(--color-body);
}

.thread-id {
  color: var(--color-brand-ochre);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

/* Session actions */
.session-actions {
  margin-top: auto;
}

.btn-finish {
  width: 100%;
  background: var(--color-primary);
  color: var(--color-on-dark);
  border: none;
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
