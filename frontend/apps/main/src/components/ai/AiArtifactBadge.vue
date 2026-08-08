<template>
  <transition name="artifact-badge">
    <button
      v-if="count > 0"
      class="artifact-badge-btn"
      role="button"
      :aria-label="t('aiArtifact.badgeLabel', { count })"
      @click="$emit('tap')"
    >
      <span class="badge-icon" aria-hidden="true">📎</span>
      <span class="badge-count" aria-hidden="true">{{ count }}</span>
    </button>
  </transition>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

defineProps<{
  count: number
}>()

defineEmits<{
  tap: []
}>()

const { t } = useI18n()
</script>

<style scoped>
.artifact-badge-btn {
  position: fixed;
  bottom: calc(72px + env(safe-area-inset-bottom));
  right: 16px;
  z-index: 11;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--suggestion-bg, rgba(129, 140, 248, 0.1));
  border: 1px solid var(--suggestion-border, rgba(129, 140, 248, 0.25));
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  transition: background 0.15s, border-color 0.15s, color 0.15s, transform 0.15s;
}

.artifact-badge-btn:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
  color: var(--text-primary);
}

.artifact-badge-btn:active {
  transform: scale(0.95);
}

.badge-icon {
  font-size: 18px;
  line-height: 1;
}

.badge-count {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 9px;
  background: var(--van-primary-color);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  text-align: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

/* Transition animations */
.artifact-badge-enter-active,
.artifact-badge-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}

.artifact-badge-enter-from,
.artifact-badge-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

@media (prefers-reduced-motion: reduce) {
  .artifact-badge-btn,
  .artifact-badge-enter-active,
  .artifact-badge-leave-active {
    transition: none;
  }
  .artifact-badge-btn:active {
    transform: none;
  }
}
</style>