<template>
  <div class="practice-answer-input">
    <!-- Multiple choice -->
    <div v-if="question.question_type === 'multiple_choice' && question.options" class="options-list">
      <button
        v-for="opt in question.options"
        :key="opt.key"
        class="option-btn"
        :class="{
          'option-btn--selected': selectedKey === opt.key,
          'option-btn--correct': showFeedback && opt.key === correctKey,
          'option-btn--wrong': showFeedback && selectedKey === opt.key && selectedKey !== correctKey,
        }"
        :disabled="disabled || showFeedback"
        @click="onSelect(opt.key)"
      >
        <span class="option-key">{{ opt.key }}</span>
        <span class="option-text">{{ displayOptionText(opt) }}</span>
      </button>
    </div>

    <!-- True/false -->
    <div v-else-if="question.question_type === 'true_false'" class="tf-row">
      <button
        class="tf-btn"
        :class="{
          'tf-btn--selected': selectedKey === 'T',
          'tf-btn--correct': showFeedback && isTrueCorrect,
          'tf-btn--wrong': showFeedback && selectedKey === 'T' && !isTrueCorrect,
        }"
        :disabled="disabled || showFeedback"
        @click="onSelect('T')"
      >
        {{ t('practice.answer.true') }}
      </button>
      <button
        class="tf-btn"
        :class="{
          'tf-btn--selected': selectedKey === 'F',
          'tf-btn--correct': showFeedback && !isTrueCorrect,
          'tf-btn--wrong': showFeedback && selectedKey === 'F' && !isFalseCorrect,
        }"
        :disabled="disabled || showFeedback"
        @click="onSelect('F')"
      >
        {{ t('practice.answer.false') }}
      </button>
    </div>

    <!-- Multi fill blank -->
    <div v-else-if="question.question_type === 'multi_fill_blank'" class="multi-blank-list">
      <div v-for="i in blankCount" :key="i" class="multi-blank-row">
        <span class="multi-blank-label">{{ i }}</span>
        <input
          v-model="multiBlanks[i - 1]"
          class="answer-input"
          type="text"
          :disabled="disabled || showFeedback"
          @keyup.enter="submitMultiBlank"
        />
      </div>
      <button
        class="multi-blank-submit"
        :disabled="disabled || showFeedback"
        @click="submitMultiBlank"
      >
        {{ t('common.confirm') }}
      </button>
    </div>

    <!-- AI graded -->
    <div v-else-if="question.question_type === 'ai_graded'" class="ai-graded">
      <textarea
        v-model="aiAnswer"
        class="ai-graded-textarea"
        rows="4"
        :placeholder="t('practice.answer.inputPlaceholder')"
        :disabled="disabled || showFeedback || aiGrading"
      />
      <button
        class="multi-blank-submit"
        :disabled="disabled || showFeedback || aiGrading"
        @click="submitAiAnswer"
      >
        {{ aiGrading ? t('practice.answer.aiGrading') : t('common.confirm') }}
      </button>
    </div>

    <!-- Fill blank / calculation -->
    <div v-else class="input-row">
      <input
        v-model="textAnswer"
        class="answer-input"
        type="text"
        inputmode="decimal"
        :placeholder="t('practice.answer.inputPlaceholder')"
        :disabled="disabled || showFeedback"
        @keyup.enter="submitText"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { QuestionOption, QuestionResponse } from '@/api/practice'

const props = defineProps<{
  question: QuestionResponse
  disabled: boolean
  showFeedback: boolean
  isCorrect: boolean
}>()

const emit = defineEmits<{
  submit: [answer: Record<string, unknown>]
}>()

const { t } = useI18n()

// Reset transient UI state when the question changes (IMPORTANT-7 fix)
watch(
  () => props.question.id,
  () => {
    selectedKey.value = null
    textAnswer.value = ''
    multiBlanks.value = []
    aiAnswer.value = ''
    aiGrading.value = false
  },
)

const selectedKey = ref<string | null>(null)
const textAnswer = ref('')
const multiBlanks = ref<string[]>([])
const aiAnswer = ref('')
const aiGrading = ref(false)

const blankCount = computed(() => {
  const ans = props.question.answer as Record<string, unknown>
  const blanks = ans?.blanks
  return Array.isArray(blanks) ? Math.min(blanks.length, 5) : (props.question.blank_count ?? 1)
})

const correctKey = computed(() => {
  const ans = props.question.answer as Record<string, unknown>
  return String(ans?.key ?? '')
})

const isTrueCorrect = computed(() => correctKey.value === 'T')
const isFalseCorrect = computed(() => correctKey.value !== 'T')

function displayOptionText(opt: QuestionOption): string {
  return (props.question.stem_zh ? opt.text_zh || opt.text : opt.text)
}

function onSelect(key: string) {
  selectedKey.value = key
  if (props.question.question_type === 'multiple_choice') {
    emit('submit', { key })
  } else {
    // true_false: map T/F to boolean value
    emit('submit', { value: key === 'T' })
  }
}

function submitText() {
  const raw = textAnswer.value.trim()
  if (!raw) return
  if (props.question.question_type === 'calculation') {
    const num = Number(raw)
    emit('submit', { answer: Number.isNaN(num) ? raw : num })
  } else {
    emit('submit', { value: raw })
  }
}

function submitMultiBlank() {
  const blanks = multiBlanks.value.map((v) => v.trim())
  if (blanks.some((v) => !v)) return
  emit('submit', { blanks })
}

function submitAiAnswer() {
  const raw = aiAnswer.value.trim()
  if (!raw) return
  aiGrading.value = true
  emit('submit', { text: raw })
}

defineExpose({ submitText, submitMultiBlank })
</script>

<style scoped>
.practice-answer-input {
  margin: 0 16px 12px;
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.option-btn,
.tf-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 48px;
  padding: 10px 14px;
  border: 2px solid var(--color-border, #e5e0d5);
  border-radius: 14px;
  background: var(--color-surface-card);
  font-size: 16px;
  color: var(--color-ink);
  text-align: left;
  transition: border-color 0.2s, background 0.2s;
}

.option-btn--selected {
  border-color: var(--color-primary);
}

.option-btn--correct,
.tf-btn--correct {
  border-color: #2e9e5b;
  background: rgba(46, 158, 91, 0.1);
}

.option-btn--wrong,
.tf-btn--wrong {
  border-color: #d9534f;
  background: rgba(217, 83, 79, 0.1);
}

.tf-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.input-row {
  padding: 4px 0;
}

.answer-input {
  width: 100%;
  min-height: 48px;
  padding: 10px 14px;
  border: 2px solid var(--color-border, #e5e0d5);
  border-radius: 14px;
  background: var(--color-surface-card);
  font-size: 18px;
  color: var(--color-ink);
}

.answer-input:focus {
  outline: none;
  border-color: var(--color-primary);
}

.multi-blank-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.multi-blank-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.multi-blank-label {
  width: 24px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--color-body);
}

.multi-blank-submit {
  min-height: 48px;
  padding: 10px 14px;
  border: none;
  border-radius: 14px;
  background: var(--color-primary);
  color: var(--color-canvas);
  font-size: 16px;
}

.ai-graded {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ai-graded-textarea {
  width: 100%;
  padding: 10px 14px;
  border: 2px solid var(--color-border, #e5e0d5);
  border-radius: 14px;
  background: var(--color-surface-card);
  font-size: 16px;
  color: var(--color-ink);
  resize: vertical;
}

.ai-graded-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
}
</style>
