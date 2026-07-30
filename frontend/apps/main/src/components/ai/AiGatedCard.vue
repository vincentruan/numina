<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

defineProps<{
  /** Whether the current user is the family owner and can enable AI. */
  isOwner?: boolean
}>()

const router = useRouter()
const { t } = useI18n()

function onAction() {
  router.push('/settings/ai')
}
</script>

<template>
  <div class="ai-gated-card" role="status" :aria-label="t('aiHub.disabledTitle')">
    <div class="ai-gated-card__icon" aria-hidden="true">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9.663 17h4.673M12 3a6 6 0 0 1 6 6c0 2.22-1.2 4.16-3 5.2V16a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 12 3z"/>
        <path d="M9 21h6"/>
        <line x1="2" y1="2" x2="22" y2="22" stroke-width="1.8"/>
      </svg>
    </div>
    <p class="ai-gated-card__title">{{ t('aiHub.disabledTitle') }}</p>
    <p class="ai-gated-card__desc">
      {{ isOwner ? t('aiGated.fullDescOwner') : t('aiHub.disabledDesc') }}
    </p>
    <button
      v-if="isOwner"
      type="button"
      class="ai-gated-card__action"
      @click="onAction"
    >
      {{ t('aiHub.disabledAction') }}
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="9 18 15 12 9 6"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
.ai-gated-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 24px;
  margin: 16px;
  background: var(--card-bg, #fff);
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}
.ai-gated-card__icon {
  color: var(--text-tertiary, #c8c9cc);
  margin-bottom: 12px;
}
.ai-gated-card__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #323233);
  margin: 0 0 6px;
}
.ai-gated-card__desc {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary, #969799);
  margin: 0 0 16px;
  max-width: 280px;
}
.ai-gated-card__action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  background: var(--color-primary, #6366f1);
  border: none;
  border-radius: 20px;
  cursor: pointer;
}
.ai-gated-card__action:active {
  opacity: 0.9;
}
</style>
