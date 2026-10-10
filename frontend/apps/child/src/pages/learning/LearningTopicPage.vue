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

      <!-- Topic title row with curriculum badge -->
      <div class="topic-title-row">
        <h1 class="topic-title">{{ displayName }}</h1>
        <span
          v-if="firstResolvedStandard"
          class="curriculum-badge"
          :aria-label="t('learning.curriculum.ariaLabel')"
        >{{ t('learning.curriculum.badgeGlyph') }}</span>
      </div>

      <!-- Curriculum standard callout -->
      <div v-if="firstResolvedStandard" class="curriculum-callout">
        {{ firstResolvedStandard.name }} · {{ firstResolvedStandard.code }}
      </div>

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

      <!-- Translate button -->
      <van-button
        v-if="showTranslateButton"
        :loading="translating"
        :loading-text="t('learning.translating')"
        size="normal"
        type="primary"
        block
        class="translate-btn"
        @click="handleTranslate"
      >
        {{ topic?.name_zh ? t('learning.retranslate') : t('learning.translate') }}
      </van-button>

      <!-- Evidence / Standards -->
      <div v-if="topic.evidence && topic.evidence.length > 0" class="evidence-section">
        <h3 class="section-title">{{ t('learning.evidence') }}</h3>
        <ul class="evidence-list">
          <li v-for="(item, idx) in displayEvidence" :key="idx" class="evidence-item">
            {{ item }}
          </li>
        </ul>
      </div>

      <!-- Learning path: prerequisites + dependents -->
      <div v-if="graphData?.prerequisites?.length" class="graph-section">
        <h3 class="section-title">{{ t('learning.prerequisites') }}</h3>
        <div class="topic-chips">
          <van-tag
            v-for="edge in graphData.prerequisites"
            :key="edge.topic.id"
            :type="prereqStatusTagType(edge.topic)"
            plain
            size="medium"
            :class="['topic-chip', { 'topic-chip--machine': edge.review_status === 'machine' }]"
            :aria-label="edge.review_status === 'machine'
              ? t('learning.machineEdge.ariaLabel', { name: topicDisplayName(edge.topic) })
              : undefined"
            @click="navigateToTopic(edge.topic.id)"
          >
            <van-icon
              :name="prereqStatusIconName(edge.topic.id)"
              size="12"
              :aria-label="t(`learning.status.${getProgressLevel(edge.topic.id)}`)"
            />
            {{ topicDisplayName(edge.topic) }}
            <span v-if="edge.review_status === 'machine'" class="ai-badge">AI</span>
          </van-tag>
        </div>
      </div>

      <div v-if="graphData?.dependents?.length" class="graph-section">
        <h3 class="section-title">{{ t('learning.nextSteps') }}</h3>
        <div class="topic-chips">
          <van-tag
            v-for="edge in graphData.dependents"
            :key="edge.topic.id"
            :type="prereqStatusTagType(edge.topic)"
            plain
            size="medium"
            :class="['topic-chip', { 'topic-chip--machine': edge.review_status === 'machine' }]"
            :aria-label="edge.review_status === 'machine'
              ? t('learning.machineEdge.ariaLabel', { name: topicDisplayName(edge.topic) })
              : undefined"
            @click="navigateToTopic(edge.topic.id)"
          >
            <van-icon
              :name="prereqStatusIconName(edge.topic.id)"
              size="12"
              :aria-label="t(`learning.status.${getProgressLevel(edge.topic.id)}`)"
            />
            {{ topicDisplayName(edge.topic) }}
            <span v-if="edge.review_status === 'machine'" class="ai-badge">AI</span>
          </van-tag>
        </div>
      </div>

      <!-- Path context bar -->
      <div v-if="activePathInfo" class="path-context-bar">
        <span>{{ t('learning.path.contextBar', activePathInfo) }}</span>
        <van-button
          size="mini"
          type="primary"
          plain
          @click="router.push(`/learning/path/${activePathInfo.pathId}`)"
        >
          {{ t('learning.path.detail') }}
        </van-button>
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

    <!-- Difficulty warning dialog -->
    <van-dialog
      v-model:show="showDifficultyDialog"
      :title="difficultyDialogTitle"
      show-cancel-button
      :confirm-button-text="t('learning.difficultyWarning.continueAnyway')"
      :cancel-button-text="t('learning.difficultyWarning.goSuggested')"
      @confirm="proceedToSession"
      @cancel="goToSuggestedTopic"
    >
      <div style="padding: 16px; text-align: center">
        <div style="font-size: 32px; margin-bottom: 8px">⚠️</div>
        <p>{{ difficultyMessage }}</p>
        <p
          v-if="suggestedTopicName"
          style="color: var(--van-primary-color); cursor: pointer"
          @click="goToSuggestedTopic"
        >
          {{ t('learning.difficultyWarning.suggestion', { name: suggestedTopicName }) }}
        </p>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningTopic' })

import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { showSuccessToast, showFailToast, type TagType } from 'vant'
import axios from 'axios'
import { usePageLoading } from '@/composables/usePageLoading'
import {
  getTopicDetail,
  getTopicGraph,
  getMyLearningMap,
  getMyAssignments,
  createSession,
  submitAssignment,
  translateTopic,
  getMyPaths,
  type TopicResponse,
  type ProgressResponse,
  type AssignmentResponse,
  type TopicGraphResponse,
  type SessionResponse,
} from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'
import { hasChineseChars } from '@numina/shared'

const { t, locale } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

const topicId = computed(() => route.params.id as string)

const loading = ref(true)
const starting = ref(false)
const submitting = ref(false)
const translating = ref(false)
const error = ref('')
const topic = ref<TopicResponse | null>(null)
const progress = ref<ProgressResponse | null>(null)
const allProgress = ref<ProgressResponse[]>([])
const graphData = ref<TopicGraphResponse | null>(null)

// Difficulty dialog state
const showDifficultyDialog = ref(false)
const pendingSessionId = ref<string | null>(null)
const difficultyWarning = ref<SessionResponse['difficulty_warning']>(null)

// Path context state
const activePathInfo = ref<{ name: string; completed: number; total: number; pathId: string } | null>(null)

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

const firstResolvedStandard = computed(() => {
  if (!topic.value?.curriculum_standards) return null
  return topic.value.curriculum_standards.find((s) => s.code != null) ?? null
})

const difficultyDialogTitle = computed(() => {
  if (difficultyWarning.value?.type === 'age')
    return t('learning.difficultyWarning.ageTitle')
  return t('learning.difficultyWarning.prereqTitle')
})

const difficultyMessage = computed(() => {
  const w = difficultyWarning.value
  if (!w) return ''
  if (w.type === 'age')
    return t('learning.difficultyWarning.ageMessage', { level: w.level })
  return t('learning.difficultyWarning.prereqMessage', { count: w.unmet_count })
})

const suggestedTopicName = computed(() => {
  const w = difficultyWarning.value
  if (!w) return null
  return locale.value.startsWith('zh')
    ? w.suggested_topic_name_zh || w.suggested_topic_name
    : w.suggested_topic_name
})

const showTranslateButton = computed(() => {
  if (locale.value !== 'zh-CN') return false
  if (!topic.value) return false
  // Don't offer translation for originally-Chinese content
  if (hasChineseChars(topic.value.name)) return false
  // Hide if already translated
  if (topic.value.name_zh) return false
  return true
})

async function handleTranslate() {
  if (!topic.value) return
  translating.value = true
  try {
    await translateTopic(topic.value.id)
    showSuccessToast(t('learning.translationComplete'))
    await load()
  } catch {
    showFailToast(t('learning.translationFailed'))
  } finally {
    translating.value = false
  }
}

function goBack() {
  router.push('/learning')
}

function getProgressLevel(topicIdStr: string): string {
  const prog = allProgress.value.find(p => p.topic_id === topicIdStr)
  return prog?.mastery_level ?? 'available'
}

function prereqStatusIconName(topicIdStr: string): string {
  const level = getProgressLevel(topicIdStr)
  if (level === 'mastered') return 'success'
  if (level === 'locked') return 'lock'
  return 'unlock'
}

function prereqStatusTagType(topic: TopicResponse): TagType {
  const level = getProgressLevel(topic.id)
  if (level === 'mastered') return 'success'
  if (level === 'locked') return 'default'
  return 'primary'
}

function navigateToTopic(tid: string) {
  router.push(`/learning/topic/${tid}`)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [topicDetail, progressList, graph] = await Promise.all([
      getTopicDetail(topicId.value),
      getMyLearningMap(),
      getTopicGraph(topicId.value).catch(() => null),
    ])
    topic.value = topicDetail
    allProgress.value = progressList
    graphData.value = graph

    // Find progress for this topic
    const topicProgress = progressList.find((p) => p.topic_id === topicId.value)
    progress.value = topicProgress ?? null

    // Load path context (non-blocking)
    loadPathContext()
  } catch {
    error.value = t('toast.loadFailed')
  } finally {
    loading.value = false
  }
}

async function loadPathContext() {
  try {
    const paths = await getMyPaths()
    for (const path of paths) {
      const item = path.items?.find(
        (i) => String(i.topic_id) === String(topicId.value) && i.status !== 'completed',
      )
      if (item) {
        const displayName =
          locale.value.startsWith('zh') && path.name_zh ? path.name_zh : path.name
        activePathInfo.value = {
          name: displayName,
          completed: path.completed_count,
          total: path.total_count,
          pathId: path.id,
        }
        break
      }
    }
  } catch {
    // Non-critical — silently ignore
  }
}

async function onStartLearning() {
  if (starting.value) return
  starting.value = true
  try {
    const session = await createSession({ topic_id: topicId.value })

    if (session.difficulty_warning) {
      // Show dialog instead of navigating directly
      difficultyWarning.value = session.difficulty_warning
      pendingSessionId.value = session.id
      showDifficultyDialog.value = true
    } else {
      router.push(`/learning/session/${session.id}`)
    }
  } catch (err: unknown) {
    const code = axios.isAxiosError(err)
      ? (err.response?.data as Record<string, unknown> | undefined)?.code as string | undefined
      : undefined
    if (code === 'LEARNING_TOPIC_LOCKED') {
      showFailToast(t('learning.error.topicLocked'))
    } else if (code === 'LEARNING_PREREQUISITE_NOT_MET') {
      showFailToast(t('learning.error.prerequisiteNotMet'))
    } else {
      showFailToast(t('learning.error.sessionCreateFailed'))
    }
  } finally {
    starting.value = false
  }
}

function proceedToSession() {
  if (pendingSessionId.value) {
    router.push(`/learning/session/${pendingSessionId.value}`)
  }
}

function goToSuggestedTopic() {
  const w = difficultyWarning.value
  if (w?.suggested_topic_id) {
    router.push(`/learning/topic/${w.suggested_topic_id}`)
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

.topic-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
}

.topic-title {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0;
  line-height: 1.3;
  flex: 1 1 auto;
  min-width: 0;
}

.curriculum-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(var(--color-brand-ochre-rgb), 0.18);
  color: var(--color-brand-ochre);
  font-family: Inter, "PingFang SC", sans-serif;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}

.curriculum-callout {
  margin: 0 0 16px;
  padding: 10px 14px;
  background: rgba(var(--color-brand-ochre-rgb), 0.12);
  border-left: 3px solid rgba(var(--color-brand-ochre-rgb), 0.45);
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-ink);
  overflow-wrap: anywhere;
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

/* Translate button */
.translate-btn {
  margin-bottom: 20px;
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

/* Graph section */
.graph-section {
  margin-bottom: 16px;
}

.topic-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.topic-chip {
  cursor: pointer;
  padding: 6px 12px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.topic-chip:active {
  opacity: 0.7;
}

.topic-chip--machine {
  /* opacity: 1 ensures the dashed-border chip never reads as disabled (R7 intent) */
  opacity: 1;
}

.topic-chip--machine::before {
  /* Vant 4.10.2 draws the plain-tag border on ::before (not the element),
     so border-style on the element itself never reaches the visible border. */
  border-style: dashed;
}

.ai-badge {
  display: inline-flex;
  align-items: center;
  padding: 0 4px;
  margin-left: 2px;
  border-radius: 3px;
  background: rgba(var(--color-brand-ochre-rgb), 0.18);
  color: var(--color-brand-ochre);
  font-size: 10px;
  font-weight: 700;
  line-height: 1.4;
  letter-spacing: 0.5px;
}

/* Path context bar */
.path-context-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  margin: 16px 0;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-hairline);
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
}
</style>
