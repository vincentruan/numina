<script setup lang="ts">
/**
 * HumanInputCard - AI clarification prompt card
 *
 * Renders an interactive card where the AI agent asks the user a question
 * with optional choice buttons.
 *
 * Interaction modes (aligned with DeerFlow ClarificationMiddleware):
 * - Single-select (default): click option -> immediate submit (one-step)
 * - Free text: textarea -> submit button
 * - choiceWithOther: options (one-step) + textarea with separate submit
 *
 * The answer is emitted to the parent which calls ``submitClarification`` -
 * sending a new ``HumanMessage`` with ``human_input_response`` (DeerFlow
 * pattern), NOT a resume endpoint.
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
  status?: 'pending' | 'submitting' | 'answered' | 'superseded'
  answer?: string
  threadId: string
  interruptId: string
}>(), {
  status: 'pending',
  options: undefined,
  context: undefined,
  answer: undefined,
})

const emit = defineEmits<{
  submit: [answer: string]
}>()

const customText = ref('')
const isComposing = ref(false)

const isInteractive = computed(() => props.status === 'pending')
const isSubmitting = computed(() => props.status === 'submitting')
const isAnswered = computed(() => props.status === 'answered')
const isSuperseded = computed(() => props.status === 'superseded')

const hasOptions = computed(() => (props.options?.length ?? 0) > 0)

/** Whether the submit button should be enabled (free-text mode) */
const canSubmit = computed(() => {
  if (!isInteractive.value || isSubmitting.value) return false
  // Free text mode (no options)
  return customText.value.trim().length > 0
})

/** Single-select: click option -> immediate submit (DeerFlow pattern) */
function handleOptionClick(value: string) {
  if (!isInteractive.value || isSubmitting.value) return
  // Single-select: immediate submit
  emit('submit', value)
}

/** Submit for free-text mode */
function submitAnswer() {
  if (!canSubmit.value) return
  const answer = customText.value.trim()
  if (answer) {
    emit('submit', answer)
    // Clear text after submit
    customText.value = ''
  }
}

function handleCustomKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !isComposing.value) {
    e.preventDefault()
    submitAnswer()
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
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="header-icon" aria-hidden="true">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
      </svg>
      <span :id="`title-${interruptId}`" class="header-title">{{ t('aiChat.clarification.title') }}</span>
    </div>

    <!-- Context (optional background) -->
    <div v-if="context" class="card-context">
      <MarkdownContent :content="context" />
    </div>

    <!-- Question -->
    <div :id="`question-${interruptId}`" class="card-question">
      <MarkdownContent :content="question" />
    </div>

    <!-- Single-select options: click -> immediate submit (DeerFlow pattern) -->
    <div v-if="hasOptions && isInteractive" class="card-options" role="radiogroup" :aria-labelledby="`question-${interruptId}`">
      <button
        v-for="(opt, idx) in options"
        :key="idx"
        class="option-btn"
        role="radio"
        :aria-checked="false"
        :disabled="isSubmitting"
        @click="handleOptionClick(opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- Answered state -->
    <div v-if="isAnswered && answer" class="card-answer" aria-live="polite">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="answer-icon" aria-hidden="true">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
      <span class="answer-text">{{ answer }}</span>
    </div>

    <!-- Custom text input (choiceWithOther in single-select, or free-text mode) -->
    <div
      v-if="isInteractive && (choiceWithOther || !hasOptions)"
      class="card-input"
    >
      <label :for="`textarea-${interruptId}`" class="sr-only">
        {{ hasOptions ? t('aiChat.clarification.customInput') : t('aiChat.clarification.inputPlaceholder') }}
      </label>
      <textarea
        :id="`textarea-${interruptId}`"
        v-model="customText"
        class="custom-textarea"
        :placeholder="hasOptions ? t('aiChat.clarification.customInput') : t('aiChat.clarification.inputPlaceholder')"
        :disabled="isSubmitting"
        rows="2"
        @keydown="handleCustomKeydown"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
      />
    </div>

    <!-- Submit button for custom-input-only mode (no options) -->
    <div v-if="isInteractive && !hasOptions && customText.trim()" class="card-submit-row">
      <button
        class="submit-btn"
        :disabled="isSubmitting"
        :aria-label="t('aiChat.clarification.submit')"
        @click="submitAnswer"
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
          aria-hidden="true"
        >
          <path d="M21 12a9 9 0 11-6.219-8.56"/>
        </svg>
        <span v-else>{{ t('aiChat.clarification.submit') }}</span>
      </button>
    </div>

    <!-- Submitting state -->
    <div v-if="isSubmitting" class="card-submitting" aria-live="polite">
      <svg
        class="submit-spinner animate-spin"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path d="M21 12a9 9 0 11-6.219-8.56"/>
      </svg>
      <span>{{ t('aiChat.clarification.submitting') }}</span>
    </div>

    <!-- Superseded state -->
    <div v-if="isSuperseded" class="card-superseded" aria-live="polite">
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

/* Single-select options - full-width outline buttons (DeerFlow pattern) */
.card-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-btn {
  width: 100%;
  min-height: 44px;
  padding: 10px 16px;
  font-size: 14px;
  color: var(--text-primary);
  background: transparent;
  border: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.12));
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  line-height: 1.4;
  text-align: left;
  white-space: pre-wrap;
  word-break: break-word;
}

.option-btn:hover:not(:disabled) {
  border-color: var(--van-primary-color);
  background: rgba(99, 102, 241, 0.06);
}

.option-btn:active:not(:disabled) {
  background: rgba(99, 102, 241, 0.12);
}

.option-btn:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
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

/* Submit row */
.card-submit-row {
  display: flex;
  justify-content: flex-end;
}

.submit-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  font-size: 13px;
  font-weight: 500;
  color: #fff;
  background: var(--van-primary-color);
  border: none;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.submit-btn:disabled {
  opacity: 0.4;
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

/* Superseded */
.card-superseded {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
}

/* Screen-reader only utility */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
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
    font-size: 13px;
    padding: 8px 12px;
  }
}
</style>
