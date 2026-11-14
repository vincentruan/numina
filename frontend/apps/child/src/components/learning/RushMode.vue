<template>
  <div class="rush-mode">
    <!-- Loading state while questions are fetched -->
    <div v-if="loading" class="rush-state rush-state--loading">
      <p class="rush-state__label">{{ t('learning.rush.loading') }}</p>
    </div>

    <!-- Error state with retry -->
    <div v-else-if="error" class="rush-state rush-state--error">
      <p class="rush-state__label">{{ t('learning.rush.errorLoading') }}</p>
      <button class="rush-retry-btn" @click="$emit('retry')">
        {{ t('learning.rush.retry') }}
      </button>
    </div>

    <!-- Countdown + question flow -->
    <div v-else-if="!finished" class="rush-active">
      <div class="rush-topbar">
        <button class="rush-exit" :aria-label="t('learning.rush.exit')" @click="exit">
          ✕
        </button>
        <div class="rush-timer" :class="{ 'rush-timer--low': secondsLeft <= 10 }">
          {{ t('learning.rush.countdown', { seconds: secondsLeft }) }}
        </div>
        <div class="rush-score">
          {{ t('learning.rush.scoreValue', { correct: correctCount }) }}
        </div>
      </div>

      <div v-if="currentQuestion" class="rush-question">
        <p class="rush-question__stem">{{ currentQuestion.stem }}</p>
        <div class="rush-question__options">
          <button
            v-for="option in currentQuestion.options"
            :key="option.key"
            class="rush-option"
            :class="{ 'rush-option--selected': selectedKey === option.key }"
            @click="selectedKey = option.key"
          >
            {{ option.text }}
          </button>
        </div>
        <button
          class="rush-submit"
          :disabled="selectedKey === null"
          @click="submit"
        >
          {{ t('learning.challenge.check') }}
        </button>
      </div>
    </div>

    <!-- Score screen -->
    <div v-else class="rush-finished">
      <p class="rush-finished__title">{{ t('learning.rush.finished') }}</p>
      <p class="rush-finished__score">
        {{ t('learning.rush.score') }}: {{ correctCount }}
      </p>
      <p v-if="finishedEarly" class="rush-finished__time-left">
        {{ t('learning.rush.timeLeft', { seconds: secondsLeft }) }}
      </p>
      <button class="rush-done-btn" @click="exit">
        {{ t('learning.challenge.continue') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { QuestionResponse } from '@/api/practice'
import {
  batchGetQuestions,
  createPracticeSession,
  type PracticeSessionResponse,
} from '@/api/practice'

defineOptions({ name: 'RushMode' })

const props = defineProps<{
  topicId: string
  durationSeconds?: number
}>()

const emit = defineEmits<{
  exit: []
  retry: []
}>()

const { t } = useI18n()

const duration = props.durationSeconds ?? 60

const loading = ref(true)
const error = ref(false)
const finished = ref(false)
const finishedEarly = ref(false)

const session = ref<PracticeSessionResponse | null>(null)
const questions = ref<QuestionResponse[]>([])
const currentIndex = ref(0)
const correctCount = ref(0)
const secondsLeft = ref(duration)
const selectedKey = ref<string | null>(null)

let timerHandle: ReturnType<typeof setInterval> | null = null

const currentQuestion = computed(() => questions.value[currentIndex.value])

async function start() {
  loading.value = true
  error.value = false
  try {
    const resp = await createPracticeSession({
      topic_id: props.topicId,
      session_mode: 'rush',
      // Request enough questions to sustain the full duration.
      count: Math.max(duration, 30),
    })
    session.value = resp
    const fetched = await batchGetQuestions(resp.question_ids)
    const byId = new Map(fetched.map((q) => [q.id, q]))
    questions.value = resp.question_ids
      .map((id) => byId.get(id))
      .filter((q): q is QuestionResponse => !!q)
    if (questions.value.length === 0) {
      error.value = true
      return
    }
    loading.value = false
    startTimer()
  } catch {
    loading.value = false
    error.value = true
  }
}

function startTimer() {
  timerHandle = setInterval(() => {
    if (secondsLeft.value > 0) {
      secondsLeft.value--
    }
    if (secondsLeft.value === 0) {
      finish(false)
    }
  }, 1000)
}

function clearTimer() {
  if (timerHandle !== null) {
    clearInterval(timerHandle)
    timerHandle = null
  }
}

/** Compare the child's pick to the stored answer; counts one point when they
 *  match. Advances immediately — no per-question feedback, per KTD6. */
function submit() {
  if (selectedKey.value === null || !currentQuestion.value) return
  const answer = currentQuestion.value.answer as { answer?: unknown } | undefined
  if (answer && String(answer.answer) === selectedKey.value) {
    correctCount.value++
  }
  selectedKey.value = null
  if (currentIndex.value + 1 < questions.value.length) {
    currentIndex.value++
  } else {
    finish(true)
  }
}

function finish(early: boolean) {
  clearTimer()
  finishedEarly.value = early
  finished.value = true
  // Rush does NOT call finishPracticeSession — it is scored client-side and
  // does not advance mastery. The session is intentionally left open on the
  // backend (or garbage-collected by the usual inactivity policy).
}

function exit() {
  clearTimer()
  emit('exit')
}

onMounted(() => {
  start()
})

onBeforeUnmount(() => {
  clearTimer()
})
</script>

<style scoped>
.rush-mode {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.rush-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px 16px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
}

.rush-state__label {
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-ink);
}

.rush-retry-btn {
  min-height: 44px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  border: none;
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: 15px;
  font-weight: 600;
}

.rush-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 12px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
}

.rush-exit {
  min-width: 44px;
  min-height: 44px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.rush-timer {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-ink);
}

.rush-timer--low {
  color: var(--color-brand-coral);
}

.rush-score {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-brand-mint);
}

.rush-question {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-lg);
}

.rush-question__stem {
  font-family: Inter, sans-serif;
  font-size: 16px;
  color: var(--color-ink);
  line-height: 1.5;
}

.rush-question__options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rush-option {
  min-height: 48px;
  padding: 10px 14px;
  border: 2px solid var(--color-hairline);
  border-radius: var(--radius-md);
  background: var(--challenge-object-bg);
  color: var(--color-ink);
  font-size: 15px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.rush-option--selected {
  border-color: var(--color-brand-ochre);
  background: var(--challenge-object-active);
}

.rush-submit {
  min-height: 48px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

.rush-submit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.rush-finished {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px 16px;
  background: var(--color-surface-soft);
  border-radius: var(--radius-lg);
}

.rush-finished__title {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-ink);
}

.rush-finished__score {
  font-family: Inter, sans-serif;
  font-size: 28px;
  font-weight: 700;
  color: var(--color-brand-mint);
}

.rush-finished__time-left {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted);
}

.rush-done-btn {
  min-height: 48px;
  padding: 10px 24px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: var(--color-on-primary);
  font-size: 15px;
  font-weight: 600;
}
</style>
