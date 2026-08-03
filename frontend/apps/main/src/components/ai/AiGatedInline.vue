<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import IIcon from '@/components/IIcon.vue'

const props = defineProps<{
  /** If true, the user is the family owner and can enable AI; otherwise they need to ask the admin. */
  isOwner?: boolean
  /** Optional contextual title instead of the generic one. */
  title?: string
}>()

const router = useRouter()
const { t } = useI18n()

function onAction() {
  router.push('/settings')
}
</script>

<template>
  <div class="ai-gated-inline" role="status" :aria-label="t('aiGated.inlineAriaLabel')">
    <IIcon icon="lucide:bot" size="20" class="ai-gated-inline__icon" aria-hidden="true" />
    <div class="ai-gated-inline__body">
      <p class="ai-gated-inline__title">
        {{ title ?? t('aiGated.inlineTitle') }}
      </p>
      <p class="ai-gated-inline__desc">
        {{ isOwner ? t('aiGated.inlineDescOwner') : t('aiGated.inlineDescMember') }}
      </p>
    </div>
    <button
      v-if="isOwner"
      type="button"
      class="ai-gated-inline__action"
      @click="onAction"
    >
      {{ t('aiGated.inlineAction') }}
    </button>
  </div>
</template>

<style scoped>
.ai-gated-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-secondary, #f7f8fa);
  border-radius: 10px;
  color: var(--text-secondary, #969799);
}
.ai-gated-inline__icon {
  flex-shrink: 0;
  color: var(--color-primary, #6366f1);
  opacity: 0.8;
}
.ai-gated-inline__body {
  flex: 1;
  min-width: 0;
}
.ai-gated-inline__title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #323233);
  margin: 0 0 2px;
}
.ai-gated-inline__desc {
  font-size: 11px;
  line-height: 1.4;
  color: var(--text-tertiary, #c8c9cc);
  margin: 0;
}
.ai-gated-inline__action {
  flex-shrink: 0;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-primary, #6366f1);
  background: transparent;
  border: 1px solid currentColor;
  border-radius: 12px;
  cursor: pointer;
}
.ai-gated-inline__action:active {
  opacity: 0.7;
}
</style>
