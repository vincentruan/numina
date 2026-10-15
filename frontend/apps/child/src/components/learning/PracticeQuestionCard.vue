<template>
  <div class="practice-question-card">
    <div class="card-header">
      <span class="q-index">{{ indexLabel }}</span>
    </div>
    <div class="card-stem">
      <p class="stem-text">{{ displayStem }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { QuestionResponse } from '@/api/practice'

const props = defineProps<{
  question: QuestionResponse
  index: number
  total: number
}>()

const { t, locale } = useI18n()

const indexLabel = computed(() => `${props.index + 1} / ${props.total}`)

const displayStem = computed(() => {
  return locale.value.startsWith('zh')
    ? props.question.stem_zh || props.question.stem
    : props.question.stem
})
</script>

<style scoped>
.practice-question-card {
  background: var(--color-surface-card);
  border-radius: 16px;
  padding: 16px;
  margin: 12px 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.q-index {
  font-variant-numeric: tabular-nums;
  font-size: 13px;
  color: var(--color-body);
}

.stem-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  line-height: 1.5;
}
</style>
