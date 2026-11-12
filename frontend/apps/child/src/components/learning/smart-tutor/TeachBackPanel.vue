<script setup lang="ts">
/**
 * TeachBackPanel — child-teaches-AI panel for mastered topics.
 *
 * The child plays "teacher": an AI student persona asks confusions, the child
 * explains, and the dual-track grading marks each explanation hit/miss. When
 * every confusion is resolved the panel shows the "eureka" celebration.
 *
 * Usage:
 *   <TeachBackPanel :topic-id="topicId" :subject="subject" :age-group="ageGroup" />
 */
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import TeacherAvatar from './TeacherAvatar.vue'
import { useTeachBack, type TeachBackTurn } from '@/composables/useTeachBack'

interface Props {
  topicId: string
  subject: string
  ageGroup: string
}

const props = defineProps<Props>()

const { t } = useI18n()
const {
  messages,
  currentPhase,
  currentStreamText,
  error,
  turns,
  allConfusionsHit,
  teachBackSuccess,
  isStreaming,
  canSendAnswer,
  startTeachBack,
  submitExplanation,
  disconnect,
  reset,
} = useTeachBack()

const answerInput = ref('')
const chatContainer = ref<HTMLElement | null>(null)
const started = ref(false)

// Auto-scroll on new messages / turns
watch([messages, turns], () => {
  requestAnimationFrame(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}, { deep: true })

async function handleStart() {
  started.value = true
  await startTeachBack(props.topicId)
}

function handleSend() {
  const text = answerInput.value.trim()
  if (!text || !canSendAnswer.value) return
  answerInput.value = ''
  submitExplanation(text)
}

function handleRestart() {
  reset()
  started.value = false
}

function verdictLabel(turn: TeachBackTurn): string {
  return turn.verdict === 'hit'
    ? t('learning.teach_back.verdict_hit')
    : t('learning.teach_back.verdict_miss')
}

onUnmounted(() => {
  disconnect()
})
</script>

<template>
  <div class="teach-back-panel">
    <!-- Header -->
    <div class="teach-back-panel__header">
      <TeacherAvatar
        :subject="props.subject"
        :age-group="props.ageGroup"
        :phase="currentPhase"
        :is-streaming="isStreaming"
      />
      <span class="teach-back-panel__title">
        {{ t('learning.teach_back.title') }}
      </span>
    </div>

    <!-- Chat area -->
    <div ref="chatContainer" class="teach-back-panel__chat">
      <!-- Start state -->
      <div v-if="!started" class="teach-back-panel__welcome">
        <div class="teach-back-panel__welcome-icon">🧑‍🎓</div>
        <p class="teach-back-panel__welcome-text">
          {{ t('learning.teach_back.welcome') }}
        </p>
        <van-button type="primary" round @click="handleStart">
          {{ t('learning.teach_back.start_btn') }}
        </van-button>
      </div>

      <!-- Messages -->
      <template v-for="msg in messages" :key="msg.id">
        <div v-if="msg.role === 'assistant'" class="teach-back-panel__msg teach-back-panel__msg--assistant">
          <div class="teach-back-panel__bubble teach-back-panel__bubble--assistant">
            {{ msg.content }}
          </div>
        </div>
        <div v-else-if="msg.role === 'user'" class="teach-back-panel__msg teach-back-panel__msg--user">
          <div class="teach-back-panel__bubble teach-back-panel__bubble--user">
            {{ msg.content }}
          </div>
        </div>
      </template>

      <!-- Turn verdicts -->
      <div v-for="(turn, idx) in turns" :key="`turn-${idx}`" class="teach-back-panel__verdict">
        <span
          class="teach-back-panel__verdict-badge"
          :class="turn.verdict === 'hit' ? 'teach-back-panel__verdict-badge--hit' : 'teach-back-panel__verdict-badge--miss'"
        >
          {{ turn.verdict === 'hit' ? '✓' : '…' }} {{ verdictLabel(turn) }}
        </span>
        <span v-if="turn.extracted_expression" class="teach-back-panel__verdict-expr">
          {{ turn.extracted_expression }}
        </span>
      </div>

      <!-- Streaming indicator -->
      <div v-if="isStreaming" class="teach-back-panel__msg teach-back-panel__msg--assistant">
        <div class="teach-back-panel__bubble teach-back-panel__bubble--assistant">
          <span v-if="currentStreamText">{{ currentStreamText }}</span>
          <span v-else class="teach-back-panel__typing">
            <span class="dot" /><span class="dot" /><span class="dot" />
          </span>
        </div>
      </div>

      <!-- Eureka celebration -->
      <div v-if="teachBackSuccess && allConfusionsHit" class="teach-back-panel__eureka">
        <div class="teach-back-panel__eureka-icon">🎉</div>
        <p class="teach-back-panel__eureka-text">
          {{ t('learning.teach_back.eureka') }}
        </p>
      </div>

      <!-- Error -->
      <div v-if="error" class="teach-back-panel__error">
        <van-icon name="warning-o" />
        {{ error }}
        <van-button size="mini" plain @click="handleRestart">
          {{ t('common.retry') }}
        </van-button>
      </div>
    </div>

    <!-- Input -->
    <div v-if="started && !teachBackSuccess" class="teach-back-panel__input">
      <van-field
        v-model="answerInput"
        :placeholder="t('learning.teach_back.input_placeholder')"
        :disabled="!canSendAnswer"
        @keyup.enter="handleSend"
      />
      <van-button type="primary" :disabled="!canSendAnswer" @click="handleSend">
        {{ t('learning.teach_back.send_btn') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.teach-back-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.teach-back-panel__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--van-border-color, #ebedf0);
}

.teach-back-panel__title {
  font-weight: 600;
  font-size: 15px;
}

.teach-back-panel__chat {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.teach-back-panel__welcome {
  text-align: center;
  padding: 32px 16px;
}

.teach-back-panel__welcome-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.teach-back-panel__welcome-text {
  color: #646566;
  margin-bottom: 20px;
  line-height: 1.6;
}

.teach-back-panel__msg {
  display: flex;
}

.teach-back-panel__msg--assistant {
  justify-content: flex-start;
}

.teach-back-panel__msg--user {
  justify-content: flex-end;
}

.teach-back-panel__bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.5;
  word-break: break-word;
}

.teach-back-panel__bubble--assistant {
  background: #f2f3f5;
  color: #323233;
  border-top-left-radius: 2px;
}

.teach-back-panel__bubble--user {
  background: #1989fa;
  color: #fff;
  border-top-right-radius: 2px;
}

.teach-back-panel__verdict {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 4px;
}

.teach-back-panel__verdict-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}

.teach-back-panel__verdict-badge--hit {
  background: #e8f8ee;
  color: #07c160;
}

.teach-back-panel__verdict-badge--miss {
  background: #fff2f0;
  color: #ee0a24;
}

.teach-back-panel__verdict-expr {
  font-family: monospace;
  font-size: 12px;
  color: #969799;
}

.teach-back-panel__typing {
  display: inline-flex;
  gap: 4px;
}

.teach-back-panel__typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #969799;
  animation: blink 1.4s infinite both;
}

.teach-back-panel__typing .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.teach-back-panel__typing .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}

.teach-back-panel__eureka {
  text-align: center;
  padding: 24px 16px;
}

.teach-back-panel__eureka-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.teach-back-panel__eureka-text {
  font-size: 16px;
  font-weight: 600;
  color: #07c160;
}

.teach-back-panel__error {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ee0a24;
  font-size: 14px;
  padding: 8px 4px;
}

.teach-back-panel__input {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--van-border-color, #ebedf0);
  align-items: center;
}
</style>
