<template>
  <div
    v-if="candidate && prereqName && targetName"
    class="diagnosis-card"
    role="status"
    aria-live="polite"
    data-test="diagnosis-card"
  >
    <div class="diagnosis-card__title">
      {{ t('practice.diagnosis.title', { name: prereqName }) }}
    </div>
    <p class="diagnosis-card__evidence">
      {{
        t('practice.diagnosis.evidence', {
          count: candidate.sample_size ?? 0,
          topic: targetName,
        })
      }}
    </p>
    <div class="diagnosis-card__actions">
      <button
        type="button"
        class="diagnosis-card__btn diagnosis-card__btn--primary"
        data-test="practice-first-btn"
        @click="$emit('practiceFirst')"
      >
        {{ t('practice.diagnosis.practiceFirst', { name: prereqName }) }}
      </button>
      <button
        type="button"
        class="diagnosis-card__btn diagnosis-card__btn--ghost"
        data-test="continue-btn"
        @click="$emit('continue')"
      >
        {{ t('practice.diagnosis.continue', { topic: targetName }) }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'DiagnosisCard' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import type { RecommendResponse } from '@/api/practice'

// The diagnosis copy lives at practice.diagnosis.*, outside the per-page scope.
const { t } = useI18n({ useScope: 'global' })
const { topicDisplayName } = useLocalizedTopic()

const props = defineProps<{
  candidate: RecommendResponse | null
  targetTopicName: string | null
  targetTopicNameZh: string | null
}>()

defineEmits<{
  practiceFirst: []
  continue: []
}>()

const prereqName = computed(() => {
  if (!props.candidate) return null
  return topicDisplayName({
    name: props.candidate.topic_name,
    name_zh: props.candidate.topic_name_zh,
    description: '',
    description_zh: null,
  })
})

const targetName = computed(() =>
  topicDisplayName({
    name: props.targetTopicName,
    name_zh: props.targetTopicNameZh,
    description: '',
    description_zh: null,
  }),
)
</script>

<style scoped>
.diagnosis-card {
  margin: 12px 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-canvas);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.diagnosis-card__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  line-height: 1.3;
}
.diagnosis-card__evidence {
  margin: 6px 0 12px;
  font-size: 13px;
  color: var(--color-body);
  line-height: 1.4;
}
.diagnosis-card__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.diagnosis-card__btn {
  flex: 1 1 0;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid transparent;
}
.diagnosis-card__btn--primary {
  background: var(--color-primary);
  color: var(--color-canvas);
}
.diagnosis-card__btn--ghost {
  background: transparent;
  color: var(--color-ink);
  border-color: var(--color-ink);
}
.diagnosis-card__btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
</style>
