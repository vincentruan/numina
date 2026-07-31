<template>
  <Teleport to="body">
    <Transition name="manifesto-popup-fade">
      <div
        v-if="visible"
        class="manifesto-popup-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="t('manifesto.title')"
        @click.self="$emit('update:visible', false)"
      >
        <div class="manifesto-popup-card">
          <div class="manifesto-popup-icon">📜</div>
          <h2 class="manifesto-popup-title">{{ manifestoTitle }}</h2>
          <p class="manifesto-popup-hint">{{ t('manifesto.popupHint') }}</p>
          <button class="manifesto-popup-cta" @click="$emit('navigate')">
            {{ t('manifesto.goToSign') }}
          </button>
          <button
            class="manifesto-popup-dismiss"
            @click="$emit('update:visible', false)"
          >
            {{ t('common.cancel') }}
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  manifestoTitle: string
  visible: boolean
}>()

defineEmits<{
  'update:visible': [value: boolean]
  navigate: []
}>()

const { t } = useI18n()
</script>

<style scoped>
.manifesto-popup-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.45);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 1000;
}

.manifesto-popup-card {
  background: var(--color-surface-card, #ffffff);
  border-radius: var(--radius-lg, 20px);
  padding: 28px 24px;
  max-width: 320px;
  width: 100%;
  text-align: center;
  box-shadow: 0 12px 40px rgba(10, 10, 10, 0.18);
  border: 1px solid var(--color-hairline, #e5e2d6);
}

.manifesto-popup-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.manifesto-popup-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-ink, #0a0a0a);
  margin: 0 0 8px;
  line-height: 1.3;
}

.manifesto-popup-hint {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-body, #3d3d3d);
  margin: 0 0 20px;
  line-height: 1.5;
}

.manifesto-popup-cta {
  width: 100%;
  background: var(--color-primary, #0a0a0a);
  color: var(--color-on-dark, #ffffff);
  border: none;
  border-radius: var(--radius-md, 12px);
  padding: 14px;
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
  transition: transform 0.1s;
}

.manifesto-popup-cta:active {
  transform: scale(0.96);
}

.manifesto-popup-dismiss {
  width: 100%;
  background: transparent;
  color: var(--color-muted, #6b6b6b);
  border: none;
  padding: 12px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  cursor: pointer;
  margin-top: 4px;
}

.manifesto-popup-fade-enter-active,
.manifesto-popup-fade-leave-active {
  transition: opacity 200ms ease-out;
}

.manifesto-popup-fade-enter-from,
.manifesto-popup-fade-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .manifesto-popup-overlay {
    backdrop-filter: none;
  }
}
</style>
