<template>
  <div class="learning-topic-page">
    <RoleShimmer v-if="loading" variant="clay-pulse" />

    <template v-else-if="topic">
      <!-- Breadcrumb -->
      <div class="breadcrumb">
        <span class="breadcrumb__item" @click="goBack">{{ t('learning.title') }}</span>
        <span class="breadcrumb__sep">/</span>
        <span class="breadcrumb__item">{{ topic.subject }}</span>
        <span v-if="topic.domain" class="breadcrumb__sep">/</span>
        <span v-if="topic.domain" class="breadcrumb__item breadcrumb__item--active">{{ topic.domain }}</span>
      </div>

      <!-- Topic title -->
      <h1 class="topic-title">{{ displayName }}</h1>

      <!-- Mastery progress bar -->
      <div v-if="progress" class="mastery-section">
        <div class="mastery-header">
          <span class="mastery-label">{{ t(`learning.status.${progress.mastery_level}`) }}</span>
          <span class="mastery-score" v-if="progress.mastery_score != null">
            {{ Math.round(progress.mastery_score * 100) }}%
          </span>
        </div>
        <div class="mastery-bar">
          <div
            class="mastery-bar__fill"
            :style="{ width: `${(progress.mastery_score ?? 0) * 100}%` }"
          />
        </div>
        <p class="mastery-attempts">{{ t('learning.attempts', { count: progress.attempts }) }}</p>
      </div>

      <!-- Description -->
      <div class="description-section">
        <p class="description-text">{{ displayDescription }}</p>
      </div>

      <!-- Evidence / Standards -->
      <div v-if="topic.evidence && topic.evidence.length > 0" class="evidence-section">
        <h3 class="section-title">{{ t('learning.evidence') }}</h3>
        <ul class="evidence-list">
          <li v-for="(item, idx) in displayEvidence" :key="idx" class="evidence-item">
            {{ item }}
          </li>
        </ul>
      </div>

      <!-- Action buttons -->
      <div class="action-buttons">
        <button class="btn-primary" :disabled="starting" @click="onStartLearning">
          {{ starting ? t('common.loading') : t('learning.startLearning') }}
        </button>
        <button class="btn-secondary" :disabled="submitting" @click="onSubmitAssignment">
          {{ submitting ? t('common.loading') : t('learning.submitAssignment') }}
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
defineOptions({ name: 'LearningTopic' })

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { showSuccessToast, showFailToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import {
  getTopicDetail,
  getMyLearningMap,
  getMyAssignments,
  createSession,
  submitAssignment,
  type TopicResponse,
  type ProgressResponse,
  type AssignmentResponse,
} from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'

const { t, locale } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const topicId = computed(() => route.params.id as string)

const loading = ref(true)
const starting = ref(false)
const submitting = ref(false)
const error = ref('')
const topic = ref<TopicResponse | null>(null)
const progress = ref<ProgressResponse | null>(null)
const allProgress = ref<ProgressResponse[]>([])

const displayName = computed(() => {
  if (!topic.value) return ''
  return topicDisplayName(topic.value)
})

const displayDescription = computed(() => {
  if (!topic.value) return ''
  return topicDescription(topic.value)
})

const displayEvidence = computed(() => {
  if (!topic.value) return []
  if (locale.value.startsWith('zh') && topic.value.evidence_zh) return topic.value.evidence_zh as string[]
  return topic.value.evidence
})

function goBack() {
  router.push('/learning')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [topicDetail, progressList] = await Promise.all([
      getTopicDetail(topicId.value),
      getMyLearningMap(),
    ])
    topic.value = topicDetail
    allProgress.value = progressList

    // Find progress for this topic
    const topicProgress = progressList.find((p) => p.topic_id === topicId.value)
    progress.value = topicProgress ?? null
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function onStartLearning() {
  if (starting.value) return
  starting.value = true
  try {
    const session = await createSession({ topic_id: topicId.value })
    router.push(`/learning/session/${session.id}`)
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    starting.value = false
  }
}

async function onSubmitAssignment() {
  if (submitting.value) return
  submitting.value = true
  try {
    // Find a pending assignment for this topic
    const assignments = await getMyAssignments()
    const pending = assignments.find(
      (a: AssignmentResponse) => a.topic_id === topicId.value && a.status === 'pending',
    )
    if (!pending) {
      showFailToast(t('learning.noPendingAssignment'))
      return
    }
    await submitAssignment(pending.id)
    showSuccessToast(t('learning.submitSuccess'))
    // Reload progress
    await load()
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    submitting.value = false
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
.learning-topic-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
}

.breadcrumb__item {
  cursor: pointer;
}

.breadcrumb__item--active {
  color: var(--color-ink);
  font-weight: 500;
}

.breadcrumb__sep {
  color: var(--color-body);
  opacity: 0.5;
}

.topic-title {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 16px;
  line-height: 1.3;
}

/* Mastery section */
.mastery-section {
  margin-bottom: 20px;
}

.mastery-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.mastery-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}

.mastery-score {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-ochre);
}

.mastery-bar {
  height: 8px;
  background: var(--color-hairline);
  border-radius: 4px;
  overflow: hidden;
}

.mastery-bar__fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 4px;
  transition: width 0.4s ease;
}

.mastery-attempts {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  margin: 6px 0 0;
}

/* Description */
.description-section {
  margin-bottom: 20px;
}

.description-text {
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-body);
  line-height: 1.6;
  margin: 0;
}

/* Evidence */
.evidence-section {
  margin-bottom: 24px;
}

.section-title {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 10px;
}

.evidence-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-item {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body);
  padding: 10px 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  line-height: 1.5;
}

/* Action buttons */
.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 24px;
}

.btn-primary,
.btn-secondary {
  width: 100%;
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

.btn-primary {
  background: var(--color-primary);
  color: var(--color-on-dark);
}

.btn-secondary {
  background: var(--color-surface-soft);
  color: var(--color-ink);
  border: 1px solid var(--color-hairline);
}

.btn-primary:active,
.btn-secondary:active {
  transform: scale(0.97);
}

.btn-primary:disabled,
.btn-secondary:disabled {
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
</style>
