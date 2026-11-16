<script setup lang="ts">
/**
 * SmartTutorPanel — main interactive panel for Socratic guided problem-solving.
 *
 * Composes TeacherAvatar, SocraticSteps, QuickActions, KnowledgeBridgeOverlay,
 * and the useSmartTutor composable into a cohesive tutoring experience.
 *
 * Usage:
 *   <SmartTutorPanel
 *     :session-id="sessionId"
 *     :question-id="questionId"
 *     :subject="topic.subject"
 *     :age-group="childAgeGroup"
 *   />
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import TeacherAvatar from './TeacherAvatar.vue'
import SocraticSteps from './SocraticSteps.vue'
import QuickActions from './QuickActions.vue'
import KnowledgeBridgeOverlay from './KnowledgeBridgeOverlay.vue'
import { useSmartTutor } from '@/composables/useSmartTutor'

interface Props {
  sessionId: string
  questionId: string
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
  persona,
  knowledgeBridge,
  stepCount,
  isStreaming,
  canSendAnswer,
  startTutoring,
  submitAnswer,
  requestHint,
  confirmUnderstanding,
  disconnect,
  reset,
} = useSmartTutor()

const answerInput = ref('')
const showKnowledgeMap = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const started = ref(false)

// Auto-scroll on new messages
watch(messages, () => {
  requestAnimationFrame(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}, { deep: true })

// Auto-start when mounted
async function handleStart() {
  started.value = true
  await startTutoring(props.sessionId, props.questionId)
}

function handleSend() {
  const text = answerInput.value.trim()
  if (!text || !canSendAnswer.value) return
  answerInput.value = ''
  submitAnswer(text)
}

function handleHint() {
  requestHint()
}

function handleUnderstand() {
  confirmUnderstanding()
}

function handleNeedMoreHelp() {
  submitAnswer(t('learning.smart_tutor.need_more_help'))
}

function handleRestart() {
  reset()
  started.value = false
}

onUnmounted(() => {
  disconnect()
})

const effectiveSubject = computed(() => persona.value?.subject ?? props.subject)
const effectiveAgeGroup = computed(() => persona.value?.age_group ?? props.ageGroup)
</script>

<template>
  <div class="smart-tutor-panel">
    <!-- Header: Teacher Avatar + Steps -->
    <div class="smart-tutor-panel__header">
      <TeacherAvatar
        :subject="effectiveSubject"
        :age-group="effectiveAgeGroup"
        :phase="currentPhase"
        :is-streaming="isStreaming"
      />
      <SocraticSteps
        v-if="started"
        :current-phase="currentPhase"
        :step-count="stepCount"
      />
    </div>

    <!-- Chat area -->
    <div ref="chatContainer" class="smart-tutor-panel__chat">
      <!-- Start state -->
      <div v-if="!started" class="smart-tutor-panel__welcome">
        <div class="smart-tutor-panel__welcome-icon">🎓</div>
        <p class="smart-tutor-panel__welcome-text">
          {{ t('learning.smart_tutor.welcome') }}
        </p>
        <van-button type="primary" round @click="handleStart">
          {{ t('learning.smart_tutor.start_btn') }}
        </van-button>
      </div>

      <!-- Messages -->
      <template v-for="msg in messages" :key="msg.id">
        <!-- Assistant message -->
        <div v-if="msg.role === 'assistant'" class="smart-tutor-panel__msg smart-tutor-panel__msg--assistant">
          <div class="smart-tutor-panel__bubble smart-tutor-panel__bubble--assistant">
            {{ msg.content }}
          </div>
        </div>

        <!-- User message -->
        <div v-else-if="msg.role === 'user'" class="smart-tutor-panel__msg smart-tutor-panel__msg--user">
          <div class="smart-tutor-panel__bubble smart-tutor-panel__bubble--user">
            {{ msg.content }}
          </div>
        </div>

        <!-- Tool call/result (collapsed) -->
        <div v-else-if="msg.role === 'tool'" class="smart-tutor-panel__msg smart-tutor-panel__msg--tool">
          <div class="smart-tutor-panel__tool-badge">
            <span v-if="msg.toolCall">🔧 {{ msg.toolCall.name }}</span>
            <span v-else-if="msg.toolResult">✓ {{ msg.toolResult.name }}</span>
          </div>
        </div>
      </template>

      <!-- Streaming indicator -->
      <div v-if="isStreaming" class="smart-tutor-panel__msg smart-tutor-panel__msg--assistant">
        <div class="smart-tutor-panel__bubble smart-tutor-panel__bubble--assistant">
          <span v-if="currentStreamText">{{ currentStreamText }}</span>
          <span v-else class="smart-tutor-panel__typing">
            <span class="dot" /><span class="dot" /><span class="dot" />
          </span>
        </div>
      </div>

      <!-- Error -->
      <div v-if="error" class="smart-tutor-panel__error">
        <van-icon name="warning-o" />
        {{ error }}
        <van-button size="mini" plain @click="handleRestart">
          {{ t('common.retry') }}
        </van-button>
      </div>
    </div>

    <!-- Quick actions -->
    <QuickActions
      v-if="started"
      :phase="currentPhase"
      :is-streaming="isStreaming"
      @hint="handleHint"
      @understand="handleUnderstand"
      @need-more-help="handleNeedMoreHelp"
      @show-knowledge-map="showKnowledgeMap = true"
    />

    <!-- Input area -->
    <div v-if="started" class="smart-tutor-panel__input">
      <van-field
        :model-value="answerInput"
        :placeholder="t('learning.smart_tutor.input_placeholder')"
        :disabled="isStreaming"
        maxlength="500"
        autosize
        type="textarea"
        rows="1"
        @update:model-value="answerInput = $event"
        @keyup.enter.exact.prevent="handleSend"
      />
      <van-button
        type="primary"
        size="small"
        round
        icon="guide-o"
        :disabled="!answerInput.trim() || !canSendAnswer"
        @click="handleSend"
      />
    </div>

    <!-- Knowledge bridge overlay -->
    <KnowledgeBridgeOverlay
      :bridge="knowledgeBridge"
      :visible="showKnowledgeMap"
      @close="showKnowledgeMap = false"
    />
  </div>
</template>

<style scoped>
.smart-tutor-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-canvas, #fffaf0);
  overflow: hidden;
}

.smart-tutor-panel__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-surface-card, #fff);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.smart-tutor-panel__chat {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  -webkit-overflow-scrolling: touch;
}

/* Welcome state */
.smart-tutor-panel__welcome {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 32px 16px;
  text-align: center;
}

.smart-tutor-panel__welcome-icon {
  font-size: 48px;
}

.smart-tutor-panel__welcome-text {
  font-size: 15px;
  color: var(--color-body, #666);
  line-height: 1.5;
}

/* Messages */
.smart-tutor-panel__msg {
  display: flex;
  max-width: 85%;
}

.smart-tutor-panel__msg--assistant {
  align-self: flex-start;
}

.smart-tutor-panel__msg--user {
  align-self: flex-end;
}

.smart-tutor-panel__msg--tool {
  align-self: center;
  max-width: 100%;
}

.smart-tutor-panel__bubble {
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.smart-tutor-panel__bubble--assistant {
  background: var(--color-surface-card, #fff);
  color: var(--color-ink, #0a0a0a);
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.smart-tutor-panel__bubble--user {
  background: var(--color-primary, var(--color-on-primary, #0a0a0a));
  color: var(--color-canvas, #fff);
  border-bottom-right-radius: 4px;
}

.smart-tutor-panel__tool-badge {
  font-size: 11px;
  color: var(--color-body, #999);
  padding: 4px 10px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 12px;
}

/* Typing indicator */
.smart-tutor-panel__typing .dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-body, #999);
  margin: 0 2px;
  animation: typing-bounce 1.2s ease-in-out infinite;
}

.smart-tutor-panel__typing .dot:nth-child(2) {
  animation-delay: 0.2s;
}

.smart-tutor-panel__typing .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-4px); }
}

/* Error */
.smart-tutor-panel__error {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(231, 76, 60, 0.08);
  border-radius: 8px;
  font-size: 13px;
  color: #E74C3C;
}

/* Input area */
.smart-tutor-panel__input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-surface-card, #fff);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.smart-tutor-panel__input :deep(.van-field) {
  flex: 1;
  padding: 6px 10px;
  background: var(--color-canvas, #f5f5f5);
  border-radius: 12px;
}
</style>
