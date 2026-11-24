<template>
  <div class="learning-topic-page">
    <RoleShimmer v-if="loading" variant="clay-pulse" />

    <template v-else-if="topic">
      <!-- Simplified top bar — back arrow + subject name -->
      <div class="top-bar">
        <button class="top-bar__back" @click="goBack" :aria-label="t('learning.backToMap')">
          <IIcon icon="lucide:chevron-left" size="20" />
        </button>
        <span class="top-bar__subject">{{ subjectLabel(topic.subject) }}</span>
      </div>

      <!-- Topic title row with curriculum friendly tag -->
      <div class="topic-title-row">
        <h1 class="topic-title">{{ displayName }}</h1>
        <span v-if="firstResolvedStandard" class="curriculum-tag">
          {{ curriculumFriendlyLabel(firstResolvedStandard) }}
        </span>
      </div>

      <!-- Mastery progress bar — compact -->
      <div v-if="progress" class="mastery-section">
        <div class="mastery-header">
          <span class="mastery-label">{{ t(`learning.status.${progress.mastery_level}`) }}</span>
          <span class="mastery-score" v-if="progress.mastery_score != null">
            {{ Math.round(progress.mastery_score * 100) }}%
          </span>
        </div>
        <div v-if="progress.mastery_score != null" class="mastery-bar">
          <div class="mastery-bar__fill" :style="{ width: `${progress.mastery_score * 100}%` }" />
        </div>
        <div v-else class="mastery-bar mastery-bar--empty">
          <span class="mastery-bar__empty-label">{{ t('learning.notStartedYet') }}</span>
        </div>
      </div>

      <!-- Socratic curiosity hook -->
      <TopicHookQuestion
        v-if="hookQuestion && !hookSkipped"
        :question="hookQuestion"
        @skip="hookSkipped = true"
      />

      <!-- Description -->
      <div class="description-section">
        <p class="description-text">{{ displayDescription }}</p>
      </div>

      <!-- Hero action buttons — above the fold -->
      <div class="hero-actions">
        <button class="btn-primary btn-cta" :disabled="starting" @click="onStartLearning">
          <IIcon icon="lucide:play" size="18" />
          {{ starting ? t('common.loading') : t('learning.startLearningCta') }}
        </button>
        <button class="btn-secondary" @click="goToPractice">
          {{ t('practice.startPractice') }}
        </button>
      </div>

      <!-- Teach-back — only for mastered topics, styled as text link -->
      <div v-if="isMastered" class="teach-back-link-row">
        <button class="btn-text-link" @click="goToTeachBack">
          🎓 {{ t('learning.teach_back.start_btn') }}
        </button>
      </div>

      <!-- "Learn more" collapsible section -->
      <div class="details-section">
        <button class="details-toggle" @click="detailsExpanded = !detailsExpanded">
          <span>{{ t('learning.learnMore') }}</span>
          <IIcon :icon="detailsExpanded ? 'lucide:chevron-up' : 'lucide:chevron-down'" size="16" />
        </button>
        <div v-show="detailsExpanded" class="details-body">
          <!-- Breadcrumb path — moved here -->
          <div class="breadcrumb-trail-compact">
            <span class="breadcrumb-item" @click="goBack">{{ t('learning.title') }}</span>
            <span class="breadcrumb-sep">/</span>
            <span class="breadcrumb-item">{{ subjectLabel(topic.subject) }}</span>
            <span v-if="topic.domain" class="breadcrumb-sep">/</span>
            <span v-if="topic.domain" class="breadcrumb-item breadcrumb-item--active">
              {{ translateDomain(t, topic.domain) }}
            </span>
          </div>

          <!-- Curriculum standard callout — detailed -->
          <div v-if="firstResolvedStandard" class="curriculum-callout">
            {{ firstResolvedStandard.name }} · {{ firstResolvedStandard.code }}
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

          <!-- Real-world connections (Issue #201) -->
          <RealWorldConnections :connections="displayRealWorldConnections" />

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
                <span v-if="edge.review_status === 'machine'" class="ai-badge">{{ t('learning.machineEdge.aiBadge') }}</span>
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
                <span v-if="edge.review_status === 'machine'" class="ai-badge">{{ t('learning.machineEdge.aiBadge') }}</span>
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
        </div>
      </div>

      <!-- Submit assignment — bottom, only when pending -->
      <button
        v-if="hasPendingAssignment"
        class="btn-secondary btn-submit-assignment"
        :disabled="submitting"
        @click="onSubmitAssignment"
      >
        {{ submitting ? t('common.loading') : t('learning.submitAssignment') }}
      </button>
    </template>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <!-- A missing topic cannot be fixed by retrying — the child's taxonomy
           may have changed under them (e.g. locale-specific seed data landing
           mid-session).  Send them back to the map, which reloads fresh. -->
      <router-link v-if="errorIsNotFound" to="/learning" class="btn-secondary">
        {{ t('learning.backToMap') }}
      </router-link>
      <button v-else class="btn-secondary" @click="load">{{ t('common.retry') }}</button>
    </div>

    <!-- Difficulty warning dialog -->
    <van-dialog
      v-model:show="showDifficultyDialog"
      :title="difficultyDialogTitle"
      :show-cancel-button="!!suggestedTopicId"
      :confirm-button-text="t('learning.difficultyWarning.continueAnyway')"
      :cancel-button-text="t('learning.difficultyWarning.goSuggested')"
      @confirm="proceedToSession"
      @cancel="goToSuggestedTopic"
    >
      <div class="difficulty-dialog__content">
        <div class="difficulty-dialog__icon">️</div>
        <p class="difficulty-dialog__message">{{ difficultyMessage }}</p>
        <p
          v-if="suggestedTopicName"
          class="difficulty-dialog__suggestion"
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
import { domainLabel as translateDomain } from '@/utils/domainLabel'
import {
  getTopicDetail,
  getTopicGraph,
  getTopicHook,
  getMyLearningMap,
  getMyAssignments,
  createSession,
  submitAssignment,
  translateTopic,
  getMyPaths,
  type TopicResponse,
  type ProgressResponse,
  type CurriculumStandard,
  type AssignmentResponse,
  type TopicGraphResponse,
  type SessionResponse,
  type HookQuestionResponse,
} from '@/api/learning'
import RoleShimmer from '@/components/RoleShimmer.vue'
import TopicHookQuestion from '@/components/learning/TopicHookQuestion.vue'
import RealWorldConnections from '@/components/learning/RealWorldConnections.vue'
import IIcon from '@/components/IIcon.vue'
import { hasChineseChars } from '@numina/shared'

const { t, locale } = useI18n()
const { topicDisplayName, topicDescription } = useLocalizedTopic()
const route = useRoute()
const router = useRouter()
const { increment, decrement } = usePageLoading()

// Collapsible details section
const detailsExpanded = ref(false)

function subjectLabel(subject: string): string {
  const key = `learning.subject.${subject}`
  const translated = t(key)
  return translated === key ? subject.charAt(0).toUpperCase() + subject.slice(1) : translated
}

/**
 * Map a curriculum standard code to a child-friendly stage label.
 * 2022 MOE codes carry a 学段 prefix: S1 (grades 1-2), S2 (3-4), S3 (5-6),
 * S4 (7-9), SH (high school). UK codes use KS1-KS4.
 * e.g., "S2.AP.03" → "三四年级会学到" / "Grades 3-4"
 */
const STAGE_LABEL_KEYS: Record<string, string> = {
  S1: 'learning.curriculum.stage1',
  S2: 'learning.curriculum.stage2',
  S3: 'learning.curriculum.stage3',
  S4: 'learning.curriculum.stage4',
  SH: 'learning.curriculum.stageHS',
  KS1: 'learning.curriculum.stage1',
  KS2: 'learning.curriculum.stage2',
  KS3: 'learning.curriculum.stage4',
  KS4: 'learning.curriculum.stageHS',
}

function curriculumFriendlyLabel(standard: CurriculumStandard): string {
  if (!standard.code) return t('learning.curriculum.ariaLabel')
  const moe = standard.code.match(/^(S[1-4]|SH)\./)
  const uk = standard.code.match(/^[A-Z]+\.(KS[1-4])\./)
  const stage = moe?.[1] ?? uk?.[1]
  const key = stage ? STAGE_LABEL_KEYS[stage] : undefined
  return key ? t(key) : t('learning.curriculum.ariaLabel')
}

const topicId = computed(() => route.params.id as string)

const loading = ref(true)
const starting = ref(false)
const submitting = ref(false)
const translating = ref(false)
const error = ref('')
const errorIsNotFound = ref(false)
const topic = ref<TopicResponse | null>(null)
const progress = ref<ProgressResponse | null>(null)
const allProgress = ref<ProgressResponse[]>([])
const graphData = ref<TopicGraphResponse | null>(null)
const pendingAssignment = ref<AssignmentResponse | null>(null)

// Hook question state
const hookQuestion = ref<HookQuestionResponse | null>(null)
const hookSkipped = ref(false)

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

const displayRealWorldConnections = computed(() => {
  if (!topic.value) return []
  if (locale.value.startsWith('zh') && topic.value.real_world_connections_zh) {
    return topic.value.real_world_connections_zh
  }
  return topic.value.real_world_connections ?? []
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
  if (w.type === 'age') {
    const levelKey = `learning.ageGroup.${w.level}`
    const levelLabel = t(levelKey)
    return t('learning.difficultyWarning.ageMessage', {
      level: levelLabel === levelKey ? w.level : levelLabel,
    })
  }
  return t('learning.difficultyWarning.prereqMessage', { count: w.unmet_count })
})

const suggestedTopicId = computed(() => difficultyWarning.value?.suggested_topic_id ?? null)

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

/** Whether this topic has a pending assignment for the current child */
const hasPendingAssignment = computed(() => pendingAssignment.value !== null)

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

function goToPractice() {
  router.push(`/learning/practice/${topicId.value}`)
}

/** True when this topic has been mastered — enables the teach-back entry. */
const isMastered = computed(() => progress.value?.mastery_level === 'mastered')

function goToTeachBack() {
  const subject = (topic.value?.subject as string) || 'mathematics'
  const ageGroup = (topic.value?.age_group as string) || 'mid'
  router.push(
    `/learning/teach-back/${topicId.value}?subject=${subject}&ageGroup=${ageGroup}`,
  )
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
  errorIsNotFound.value = false
  hookSkipped.value = false
  try {
    const [topicDetail, progressList, graph, hook, assignments] = await Promise.all([
      getTopicDetail(topicId.value),
      getMyLearningMap(),
      getTopicGraph(topicId.value).catch(() => null),
      getTopicHook(topicId.value).catch(() => null),
      getMyAssignments().catch(() => [] as AssignmentResponse[]),
    ])
    topic.value = topicDetail
    allProgress.value = progressList
    graphData.value = graph
    hookQuestion.value = hook
    pendingAssignment.value =
      assignments.find((a) => a.topic_id === topicId.value && a.status === 'pending') ?? null

    // Find progress for this topic
    const topicProgress = progressList.find((p) => p.topic_id === topicId.value)
    progress.value = topicProgress ?? null

    // Load path context (non-blocking)
    loadPathContext()
  } catch (e: unknown) {
    const err = e as { response?: { status?: number } }
    if (err?.response?.status === 404) {
      errorIsNotFound.value = true
      error.value = t('learning.topicNotFound')
    } else {
      error.value = t('toast.loadFailed')
    }
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
    } else if (code === 'LEARNING_TOPIC_NOT_FOUND') {
      // The topic resolved for this page but no longer matches the child's
      // effective taxonomy (e.g. locale seed data landed mid-session).
      // A retry cannot help — offer the map, which reloads against the
      // current taxonomy.
      errorIsNotFound.value = true
      error.value = t('learning.error.topicUnavailable')
      topic.value = null
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
  const pending = pendingAssignment.value
  if (!pending) return
  submitting.value = true
  try {
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

/* Top bar — simplified */
.top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.top-bar__back {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  color: var(--color-ink);
  cursor: pointer;
  transition: background 0.15s;
}

.top-bar__back:active {
  background: var(--color-hairline);
}

.top-bar__subject {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-ink);
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

.curriculum-tag {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: var(--radius-md);
  background: rgba(var(--color-brand-ochre-rgb), 0.15);
  /* Ochre #e8b94a on this tint is 1.62:1 — unreadable. Darkened ochre
     keeps the hue and reaches 5.52:1 (WCAG AA at 12px). */
  color: #7a5c0e;
  font-family: Inter, "PingFang SC", sans-serif;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
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

.mastery-bar--empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 20px;
  background: transparent;
  border: 1px dashed var(--color-hairline);
  border-radius: var(--radius-md);
  overflow: visible;
}

.mastery-bar__empty-label {
  font-family: Inter, "PingFang SC", sans-serif;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  color: var(--color-body);
  opacity: 0.75;
}

.mastery-bar__fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: 4px;
  transition: width 0.4s ease;
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

/* Hero action buttons — above the fold */
.hero-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 20px;
  margin-bottom: 16px;
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
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

.btn-cta {
  font-size: 16px;
  min-height: 52px;
}

/* Teach-back text link */
.teach-back-link-row {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.btn-text-link {
  background: none;
  border: none;
  color: var(--color-brand-ochre, #e8b94a);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  padding: 8px 16px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.btn-text-link:active {
  opacity: 0.7;
}

/* Details collapsible section */
.details-section {
  margin-bottom: 20px;
}

.details-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 12px;
  background: none;
  border: 1px dashed var(--color-hairline);
  border-radius: var(--radius-md);
  color: var(--color-body);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  min-height: 44px;
  transition: background 0.15s;
}

.details-toggle:active {
  background: var(--color-surface-soft);
}

.details-body {
  margin-top: 16px;
}

/* Breadcrumb trail inside details */
.breadcrumb-trail-compact {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  flex-wrap: wrap;
}

.breadcrumb-item {
  cursor: pointer;
}

.breadcrumb-item--active {
  color: var(--color-ink);
  font-weight: 500;
}

.breadcrumb-sep {
  color: var(--color-body);
  opacity: 0.5;
}

/* Submit assignment button at bottom */
.btn-submit-assignment {
  margin-top: 16px;
}

/* Difficulty dialog */
.difficulty-dialog__content {
  padding: 16px;
  text-align: center;
}

.difficulty-dialog__icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.difficulty-dialog__message {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--van-dialog-message-text-color);
  margin: 0 0 8px;
  line-height: 1.5;
}

.difficulty-dialog__suggestion {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--van-primary-color);
  cursor: pointer;
  margin: 0;
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

/* ── Dark mode: boost callout + machine chip on dark card (#152828) ── */
[data-theme="dark"] .curriculum-callout {
  background: rgba(var(--color-brand-ochre-rgb), 0.22);
  border-left-color: rgba(var(--color-brand-ochre-rgb), 0.65);
}

[data-theme="dark"] .curriculum-tag {
  background: rgba(var(--color-brand-ochre-rgb), 0.28);
  /* --color-brand-ochre (#d4a83a) on this tint is 4.0:1 — below AA for 12px.
     This lighter ochre keeps the hue at 5.08:1. */
  color: #f5d27a;
}

[data-theme="dark"] .topic-chip--machine {
  border-color: var(--color-brand-ochre);
}

[data-theme="dark"] .ai-badge {
  background: rgba(var(--color-brand-ochre-rgb), 0.28);
}
</style>
