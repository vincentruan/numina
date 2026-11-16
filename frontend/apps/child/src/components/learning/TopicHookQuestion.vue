<template>
  <div v-if="question" class="hook-question">
    <div class="hook-question__icon">💡</div>
    <p class="hook-question__label">{{ t('learning.hook.thinkAbout') }}</p>
    <p class="hook-question__text">{{ displayText }}</p>
    <button class="hook-question__skip" @click="$emit('skip')">
      {{ t('learning.hook.skip') }} →
    </button>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'TopicHookQuestion' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { HookQuestionResponse } from '@/api/learning'

const props = defineProps<{
  question: HookQuestionResponse
}>()

defineEmits<{
  skip: []
}>()

const { t, locale } = useI18n()

const displayText = computed(() => {
  if (locale.value.startsWith('zh') && props.question.question_text_zh) {
    return props.question.question_text_zh
  }
  return props.question.question_text
})
</script>

<style scoped>
.hook-question {
  margin: 0 0 20px;
  padding: 20px;
  background: var(--color-surface-card);
  border: 2px solid rgba(var(--color-brand-ochre-rgb), 0.35);
  border-radius: var(--radius-md);
  text-align: center;
}

.hook-question__icon {
  font-size: 28px;
  margin-bottom: 8px;
}

.hook-question__label {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-brand-ochre);
  margin: 0 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.hook-question__text {
  font-family: Inter, sans-serif;
  font-size: 17px;
  font-weight: 500;
  color: var(--color-ink);
  line-height: 1.5;
  margin: 0 0 16px;
}

.hook-question__skip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-body);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  min-height: 44px;
  transition: color 0.15s;
}

.hook-question__skip:hover,
.hook-question__skip:active {
  color: var(--color-ink);
}

/* Dark mode */
[data-theme="dark"] .hook-question {
  border-color: rgba(var(--color-brand-ochre-rgb), 0.5);
  background: var(--color-surface-card);
}
</style>
