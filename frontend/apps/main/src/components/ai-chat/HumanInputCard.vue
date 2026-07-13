<script setup lang="ts">
/**
 * HumanInputCard - AI clarification prompt card
 *
 * Renders an interactive card where the AI agent asks the user a question
 * with optional choice buttons. Supports custom text input and multiple
 * status states (pending, submitting, answered, error, superseded).
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownContent from './MarkdownContent.vue'

const { t } = useI18n()

interface Option {
  label: string
  value: string
}

const props = withDefaults(defineProps<{
  question: string
  options?: Option[]
  context?: string
  choiceWithOther?: boolean
  status?: 'pending' | 'submitting' | 'answered' | 'error' | 'superseded'
  answer?: string
  errorMessage?: string
  threadId: string
  interruptId: string
}>(), {
  status: 'pending',
})

const emit = defineEmits<{
  submit: [answer: string]
}>()

const customText = ref('')
const isComposing = ref(false)

const isInteractive = computed(() => props.status === 'pending')
const isSubmitting = computed(() => props.status === 'submitting')
const isAnswered = computed(() => props.status === 'answered')
const isError = computed(() => props.status === 'error')
const isSuperseded = computed(() => props.status === 'superseded')

function submitOption(value: string) {
  if (!isInteractive.value) return
  emit('submit', value)
}

function submitCustom() {
  const text = customText.value.trim()
  if (!text || !isInteractive.value) return
  emit('submit', text)
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !isComposing.value) {
    e.preventDefault()
    submitCustom()
  }
}

function handleRetry() {
  // Re-emit the last answer or custom text for retry
  if (props.answer) {
    emit('submit', props.answer)
  }
}
</script>

<template>
  <div
    class="human-input-card"
    :class="[status]"
    role="group"
    :aria-label="t('aiChat.clarification.title')"
  >
    <!-- Header -->
    <div class="card-header">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="header-icon">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
      </svg>
      <span class="header-title">{{ t('aiChat.clarification.title') }}</span>
    </div>

    <!-- Context (optional background) -->
    <div v-if="context" class="card-context">
      <MarkdownContent :content="context" />
    </div>

    <!-- Question -->
    <div class="card-question">
      <MarkdownContent :content="question" />
    </div>

    <!-- Option buttons -->
    <div v-if="options && options.length > 0 && isInteractive" class="card-options">
      <button
        v-for="(opt, idx) in options"
        :key="idx"
        class="option-btn"
        :disabled="isSubmitting"
        @click="submitOption(opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- Selected options display (answered state) -->
    <div v-if="isAnswered && answer" class="card-answer">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="answer-icon">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
      <span class="answer-text">{{ answer }}</span>
    </div>

    <!-- Custom text input (pending with choiceWithOther or no options) -->
    <div
      v-if="isInteractive && (choiceWithOther || !options?.length)"
      class="card-input"
    >
      <textarea
        v-model="customText"
        class="custom-textarea"
        :placeholder="t('aiChat.clarification.customInput')"
        :disabled="isSubmitting"
        rows="2"
        @keydown="handleKeydown"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
      />
      <button
        class="submit-btn"
        :disabled="!customText.trim() || isSubmitting"
        @click="submitCustom"
      >
        <svg
          v-if="isSubmitting"
          class="submit-spinner animate-spin"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path d="M21 12a9 9 0 11-6.219-8.56"/>
        </svg>
        <span v-else>{{ t('aiChat.clarification.submit') }}</span>
      </button>
    </div>

    <!-- Submitting state (no options, no custom input area) -->
    <div v-if="isSubmitting && !choiceWithOther && options?.length" class="card-submitting">
      <svg
        class="submit-spinner animate-spin"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <path d="M21 12a9 9 0 11-6.219-8.56"/>
      </svg>
      <span>{{ t('aiChat.clarification.submitting') }}</span>
    </div>

    <!-- Error state -->
    <div v-if="isError" class="card-error">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="error-icon">
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
      </svg>
      <span class="error-text">{{ t('aiChat.clarification.error') }}</span>
      <span v-if="errorMessage" class="error-detail">{{ errorMessage }}</span>
      <button class="retry-btn" @click="handleRetry">
        {{ t('aiChat.clarification.retry') }}
      </button>
    </div>

    <!-- Superseded state -->
    <div v-if="isSuperseded" class="card-superseded">
      <span>{{ t('aiChat.clarification.superseded') }}</span>
    </div>
  </div>
</template>

<style scoped>
.human-input-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--card-bg);
  border: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
}

.human-input-card.superseded {
  opacity: 0.5;
  pointer-events: none;
}

.human-input-card.error {
  border-color: #ef4444;
}

/* Header */
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--van-primary-color);
}

.header-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.header-title {
  line-height: 1.4;
}

/* Context */
.card-context {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  padding: 4px 0;
  opacity: 0.8;
}

/* Question */
.card-question {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
}

/* Option buttons */
.card-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.option-btn {
  padding: 6px 14px;
  font-size: 13px;
  color: var(--van-primary-color);
  background: transparent;
  border: 1px solid var(--van-primary-color);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  line-height: 1.4;
}

.option-btn:hover:not(:disabled) {
  background: var(--van-primary-color);
  color: #fff;
}

.option-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Answer display */
.card-answer {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(34, 197, 94, 0.08);
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-primary);
}

.answer-icon {
  width: 14px;
  height: 14px;
  color: #22c55e;
  flex-shrink: 0;
  margin-top: 2px;
}

.answer-text {
  line-height: 1.5;
}

/* Custom input */
.card-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.custom-textarea {
  width: 100%;
  padding: 8px 10px;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--bg-primary);
  border: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  resize: vertical;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  box-sizing: border-box;
}

.custom-textarea:focus {
  border-color: var(--van-primary-color);
}

.custom-textarea:disabled {
  opacity: 0.5;
}

.submit-btn {
  align-self: flex-end;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  font-size: 13px;
  color: #fff;
  background: var(--van-primary-color);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Submitting indicator */
.card-submitting {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
}

.submit-spinner {
  color: var(--van-primary-color);
}

/* Error */
.card-error {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 6px;
  font-size: 13px;
}

.error-icon {
  width: 14px;
  height: 14px;
  color: #ef4444;
  flex-shrink: 0;
}

.error-text {
  color: #ef4444;
  font-weight: 500;
}

.error-detail {
  color: var(--text-secondary);
  width: 100%;
  font-size: 12px;
}

.retry-btn {
  margin-left: auto;
  padding: 4px 12px;
  font-size: 12px;
  color: #ef4444;
  background: transparent;
  border: 1px solid #ef4444;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.retry-btn:hover {
  background: rgba(239, 68, 68, 0.1);
}

/* Superseded */
.card-superseded {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
}

/* Spinner */
.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Mobile */
@media (max-width: 375px) {
  .human-input-card {
    padding: 8px;
  }

  .option-btn {
    font-size: 12px;
    padding: 5px 10px;
  }
}
</style>
