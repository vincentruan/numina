<template>
  <div class="practice-session-page">
    <!-- Loading state -->
    <RoleShimmer v-if="loading" variant="clay-pulse" />

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="btn-secondary" @click="load">{{ t('common.retry') }}</button>
    </div>

    <!-- Phase 1: mode selection -->
    <div v-else-if="phase === 'mode'" class="mode-phase">
      <h1 class="page-title">{{ displayTopicName }}</h1>
      <div class="mode-list">
        <button
          v-for="m in modes"
          :key="m.count"
          class="mode-btn"
          :disabled="starting"
          @click="startSession(m.count)"
        >
          <span class="mode-name">{{ m.label }}</span>
          <span class="mode-count">{{ m.count }}</span>
        </button>
      </div>
    </div>

    <!-- Phase 2: answering -->
    <div v-else-if="phase === 'answering'" class="answer-phase">
      <van-progress
        :percentage="progressPercent"
        stroke-width="6"
        class="progress-bar"
      />

      <PracticeQuestionCard
        :question="currentQuestion"
        :index="currentIndex"
        :total="totalQuestions"
      />

      <PracticeAnswerInput
        :key="currentQuestion.id"
        ref="answerInputRef"
        :question="currentQuestion"
        :disabled="submitting || feedbackShown"
        :show-feedback="feedbackShown"
        :is-correct="lastAttempt?.is_correct ?? false"
        @submit="onAnswerSubmit"
      />

      <!-- Feedback section -->
      <div v-if="feedbackShown" class="feedback-section">
        <div class="feedback-banner" :class="lastAttempt?.is_correct ? 'feedback-banner--correct' : 'feedback-banner--wrong'">
          <span class="feedback-icon">{{ lastAttempt?.is_correct ? '✓' : '✗' }}</span>
          <span>{{ lastAttempt?.is_correct ? t('practice.feedback.correct') : t('practice.feedback.wrong') }}</span>
        </div>
        <div v-if="!lastAttempt?.is_correct && currentQuestion.solution" class="solution-box">
          <p class="solution-title">{{ t('practice.feedback.solution') }}</p>
          <p v-for="(step, i) in currentQuestion.solution.steps || []" :key="i" class="solution-step">
            {{ step }}
          </p>
        </div>
        <button class="btn-primary next-btn" @click="nextQuestion">
          {{ isLastQuestion ? t('practice.feedback.finish') : t('practice.feedback.next') }}
        </button>
      </div>
    </div>

    <!-- Phase 3: result -->
    <div v-else-if="phase === 'result'" class="result-phase">
      <PracticeResultSummary
        :result="sessionResult!"
        @again="onAgain"
        @back="goBack"
      />
      <!-- Post-practice prerequisite recommendation -->
      <div v-if="sessionResult && sessionResult.total_score < 0.8 && recommendations.length > 0" class="prereq-recommend">
        <h3 class="prereq-recommend__title">{{ t('learning.practice.prereqReview') }}</h3>
        <div
          v-for="rec in recommendations"
          :key="rec.topic_id"
          class="prereq-card"
          @click="startPrereqPractice(rec.topic_id)"
        >
          <span class="prereq-card__name">{{ getRecDisplayName(rec) }}</span>
          <span class="prereq-card__reason">
            {{ t('learning.practice.prereqReason', { accuracy: Math.round(rec.accuracy * 100) }) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import {
  batchGetQuestions,
  createPracticeSession,
  finishPracticeSession,
  getPracticeRecommendations,
  submitPracticeAnswer,
  type PracticeAttemptResponse,
  type PracticeResultResponse,
  type PracticeSessionResponse,
  type QuestionResponse,
  type RecommendResponse,
} from '@/api/practice'
import PracticeQuestionCard from '@/components/learning/PracticeQuestionCard.vue'
import PracticeAnswerInput from '@/components/learning/PracticeAnswerInput.vue'
import PracticeResultSummary from '@/components/learning/PracticeResultSummary.vue'

defineOptions({ name: 'PracticeSessionPage' })

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()

const topicId = computed(() => String(route.params.topicId))

const loading = ref(false)
const error = ref('')
const starting = ref(false)
const submitting = ref(false)

const phase = ref<'mode' | 'answering' | 'result'>('mode')
const session = ref<PracticeSessionResponse | null>(null)
const questions = ref<QuestionResponse[]>([])
const currentIndex = ref(0)
const lastAttempt = ref<PracticeAttemptResponse | null>(null)
const feedbackShown = ref(false)
const sessionResult = ref<PracticeResultResponse | null>(null)
const recommendations = ref<RecommendResponse[]>([])

const answerInputRef = ref<InstanceType<typeof PracticeAnswerInput> | null>(null)

const modes = computed(() => [
  { count: 5, label: t('practice.mode.quick') },
  { count: 10, label: t('practice.mode.standard') },
  { count: 5, label: t('practice.mode.challenge') },
])

const displayTopicName = computed(() => {
  // Use topic name from session if available, otherwise fall back to i18n title
  if (session.value) {
    return t('practice.sessionTitle', { id: session.value.topic_id.slice(-6) })
  }
  return t('practice.title')
})

const totalQuestions = computed(() => questions.value.length)
const currentQuestion = computed(() => questions.value[currentIndex.value])
const isLastQuestion = computed(() => currentIndex.value >= totalQuestions.value - 1)
const progressPercent = computed(() =>
  Math.round(((currentIndex.value + (feedbackShown.value ? 1 : 0)) / totalQuestions.value) * 100),
)

async function startSession(count: number) {
  starting.value = true
  error.value = ''
  try {
    const resp = await createPracticeSession({
      topic_id: topicId.value,
      session_mode: 'practice',
      count,
    })
    session.value = resp
    // Fetch specific questions by ID using batch endpoint
    const fetched = await batchGetQuestions(resp.question_ids)
    const byId = new Map(fetched.map((q) => [q.id, q]))
    questions.value = resp.question_ids
      .map((qid) => byId.get(qid))
      .filter((q): q is QuestionResponse => !!q)
    if (questions.value.length === 0) {
      error.value = t('practice.errors.startFailed')
      return
    }
    phase.value = 'answering'
  } catch (e) {
    error.value = t('practice.errors.startFailed')
  } finally {
    starting.value = false
  }
}

async function onAnswerSubmit(answer: Record<string, unknown>) {
  if (!session.value || submitting.value || feedbackShown.value) return
  submitting.value = true
  try {
    const attempt = await submitPracticeAnswer(session.value.id, {
      question_id: currentQuestion.value.id,
      user_answer: answer,
      time_spent_seconds: undefined,
    })
    lastAttempt.value = attempt
    feedbackShown.value = true
  } catch (e) {
    // duplicate attempt or session ended — show toast so user knows
    showFailToast(t('practice.errors.submitFailed'))
  } finally {
    submitting.value = false
  }
}

async function nextQuestion() {
  if (isLastQuestion.value) {
    await doFinish()
    return
  }
  currentIndex.value += 1
  lastAttempt.value = null
  feedbackShown.value = false
}

async function doFinish() {
  if (!session.value) return
  try {
    sessionResult.value = await finishPracticeSession(session.value.id)
    phase.value = 'result'
    // Load prerequisite recommendations if score is low
    if (sessionResult.value.total_score < 0.8) {
      try {
        recommendations.value = await getPracticeRecommendations(topicId.value)
      } catch {
        // Non-critical — silently ignore
      }
    }
  } catch {
    error.value = t('practice.errors.finishFailed')
  }
}

function onAgain() {
  phase.value = 'mode'
  session.value = null
  questions.value = []
  currentIndex.value = 0
  lastAttempt.value = null
  feedbackShown.value = false
  sessionResult.value = null
  recommendations.value = []
}

function goBack() {
  router.back()
}

function getRecDisplayName(rec: { topic_name: string; topic_name_zh: string | null }): string {
  return locale.value === 'en-US' ? rec.topic_name : (rec.topic_name_zh || rec.topic_name)
}

function startPrereqPractice(prereqTopicId: string) {
  router.push(`/learning/practice/${prereqTopicId}`)
}

function load() {
  phase.value = 'mode'
  error.value = ''
  session.value = null
  questions.value = []
}
</script>

<style scoped>
.practice-session-page {
  min-height: 100%;
  padding-bottom: 24px;
}

.page-title {
  margin: 16px;
  font-size: 20px;
  color: var(--color-ink);
}

.mode-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 16px;
}

.mode-btn {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 56px;
  padding: 12px 16px;
  border: 1px solid var(--color-border, #e5e0d5);
  border-radius: 16px;
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-size: 16px;
}

.progress-bar {
  margin: 12px 16px;
}

.feedback-section {
  padding: 0 16px;
}

.feedback-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
}

.feedback-banner--correct {
  background: rgba(46, 158, 91, 0.12);
  color: #2e9e5b;
}

.feedback-banner--wrong {
  background: rgba(217, 83, 79, 0.12);
  color: #d9534f;
}

.solution-box {
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  background: var(--color-surface-card);
}

.solution-title {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}

.solution-step {
  margin: 2px 0;
  font-size: 14px;
  color: var(--color-body);
}

.next-btn {
  margin-top: 14px;
  width: 100%;
  min-height: 48px;
  border-radius: 14px;
  border: none;
  background: var(--color-primary);
  color: var(--color-canvas);
  font-size: 16px;
  font-weight: 600;
}

.error-state {
  padding: 40px 16px;
  text-align: center;
}

.btn-secondary {
  margin-top: 12px;
  min-height: 44px;
  padding: 0 20px;
  border-radius: 12px;
  border: 1px solid var(--color-border, #e5e0d5);
  background: var(--color-surface-card);
  color: var(--color-ink);
}

/* Post-practice prerequisite recommendation */
.prereq-recommend {
  margin-top: 20px;
  padding: 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
}

.prereq-recommend__title {
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 12px;
}

.prereq-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  cursor: pointer;
  margin-bottom: 8px;
}

.prereq-card:last-child {
  margin-bottom: 0;
}

.prereq-card__name {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
}

.prereq-card__reason {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
}
</style>
