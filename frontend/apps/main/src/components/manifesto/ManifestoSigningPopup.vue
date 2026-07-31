<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="manifesto-signing-popup"
      role="dialog"
      aria-modal="true"
      :aria-label="t('manifesto.manifestoUpdated')"
    >
      <div class="popup-backdrop" @click="close" />
      <div class="popup-card">
        <button class="popup-close" :aria-label="t('common.close')" @click="close">
          <van-icon name="cross" />
        </button>
        <h3 class="popup-title">{{ t('manifesto.manifestoUpdated') }}</h3>
        <p class="popup-text">{{ manifestoTitle }}</p>
        <van-button type="primary" block @click="onNavigate">
          {{ t('manifesto.goToSign') }}
        </van-button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  manifestoTitle: string
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  navigate: []
}>()

function close() {
  emit('update:visible', false)
}

function onNavigate() {
  emit('navigate')
}
</script>

<style scoped>
.manifesto-signing-popup {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.popup-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

@media (prefers-reduced-motion: reduce) {
  .popup-backdrop {
    backdrop-filter: none;
  }
}

.popup-card {
  position: relative;
  z-index: 1;
  background: var(--card-bg, #fff);
  border-radius: 16px;
  padding: 24px;
  margin: 16px;
  max-width: 360px;
  width: 100%;
  text-align: center;
}

.popup-close {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--text-secondary, #616161);
  cursor: pointer;
  border-radius: 50%;
  font-size: 18px;
}

.popup-close:hover {
  background: rgba(0, 0, 0, 0.05);
}

.popup-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  margin: 0 0 8px;
}

.popup-text {
  font-size: 14px;
  color: var(--text-secondary, #616161);
  margin: 0 0 20px;
  line-height: 1.5;
}
</style>
