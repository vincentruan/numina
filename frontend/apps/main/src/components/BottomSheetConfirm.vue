<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    :transition="transitionName"
    @update:show="onPopupUpdate"
  >
    <div class="bottom-sheet-confirm">
      <div class="sheet-title">{{ title }}</div>
      <div v-if="description" class="sheet-description">{{ description }}</div>
      <div v-if="impactPreview" class="sheet-impact">
        <div class="sheet-impact-label">{{ t('bottomSheet.impactLabel') }}</div>
        <div class="sheet-impact-text">{{ impactPreview }}</div>
      </div>
      <div class="sheet-actions">
        <van-button block plain @click="onCancel">{{ cancelText || t('common.cancel') }}</van-button>
        <van-button block type="danger" @click="onConfirm">{{ confirmText || t('common.confirm') }}</van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  show: boolean
  title: string
  description?: string
  impactPreview?: string
  confirmText?: string
  cancelText?: string
}>(), {
  description: '',
  impactPreview: '',
  confirmText: '',
  cancelText: '',
})

const emit = defineEmits<{
  (e: 'update:show', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const prefersReducedMotion = typeof window !== 'undefined'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches

const transitionName = computed(() => prefersReducedMotion ? '' : 'van-slide-up')

function onPopupUpdate(value: boolean) {
  emit('update:show', value)
  if (!value) {
    emit('cancel')
  }
}

function onConfirm() {
  emit('confirm')
  emit('update:show', false)
}

function onCancel() {
  emit('cancel')
  emit('update:show', false)
}
</script>

<style scoped>
.bottom-sheet-confirm {
  padding: 20px 16px calc(16px + env(safe-area-inset-bottom));
}

.sheet-title {
  font-size: 16px;
  font-weight: 600;
  text-align: center;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.sheet-description {
  font-size: 14px;
  color: var(--text-secondary);
  text-align: center;
  margin-bottom: 12px;
  line-height: 1.5;
}

.sheet-impact {
  background: rgba(220, 38, 38, 0.06);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}

[data-theme='dark'] .sheet-impact {
  background: rgba(220, 38, 38, 0.12);
}

.sheet-impact-label {
  font-size: 12px;
  color: var(--color-error, #dc2626);
  font-weight: 600;
  margin-bottom: 4px;
}

.sheet-impact-text {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.sheet-actions {
  display: flex;
  gap: 12px;
}

@media (prefers-reduced-motion: reduce) {
  .bottom-sheet-confirm {
    animation: none !important;
  }
}
</style>
