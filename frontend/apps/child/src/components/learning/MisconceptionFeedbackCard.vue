<template>
  <div
    v-if="feedback"
    class="misconception-card"
    role="status"
    aria-live="polite"
    data-test="misconception-card"
  >
    <div class="misconception-card__title">
      <span class="misconception-card__icon">💡</span>
      {{ t('practice.misconception.commonConfusion') }}
    </div>
    <p class="misconception-card__description" data-test="misconception-description">
      {{ displayDescription }}
    </p>
    <div v-if="hasDiagnostic" class="misconception-card__actions">
      <button
        type="button"
        class="misconception-card__btn misconception-card__btn--primary"
        data-test="misconception-try-btn"
        @click="$emit('diagnosticRequested')"
      >
        {{ t('practice.misconception.tryPractice') }}
      </button>
      <button
        type="button"
        class="misconception-card__btn misconception-card__btn--ghost"
        data-test="misconception-skip-btn"
        @click="$emit('dismissed')"
      >
        {{ t('practice.misconception.notNow') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MisconceptionFeedback } from '@/api/practice'

defineOptions({ name: 'MisconceptionFeedbackCard' })

const props = defineProps<{
  feedback: MisconceptionFeedback | null
}>()

defineEmits<{
  diagnosticRequested: []
  dismissed: []
}>()

const { t, locale } = useI18n({ useScope: 'global' })

const displayDescription = computed(() => {
  if (!props.feedback) return ''
  if (locale.value === 'zh-CN' && props.feedback.description_zh) {
    return props.feedback.description_zh
  }
  return props.feedback.description
})

const hasDiagnostic = computed(
  () => props.feedback?.diagnostic_question_id != null,
)
</script>

<style scoped>
.misconception-card {
  margin: 12px 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--color-surface-card);
  border: 1px solid var(--color-canvas);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}
.misconception-card__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  line-height: 1.3;
}
.misconception-card__icon {
  font-size: 18px;
}
.misconception-card__description {
  margin: 6px 0 12px;
  font-size: 13px;
  color: var(--color-body);
  line-height: 1.5;
}
.misconception-card__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.misconception-card__btn {
  flex: 1 1 0;
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  border: 1px solid transparent;
}
.misconception-card__btn--primary {
  background: var(--color-primary);
  color: var(--color-canvas);
}
.misconception-card__btn--ghost {
  background: transparent;
  color: var(--color-body);
  border-color: var(--color-body);
  opacity: 0.8;
}
</style>
