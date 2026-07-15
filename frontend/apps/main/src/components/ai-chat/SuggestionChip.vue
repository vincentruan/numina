<script setup lang="ts">
/**
 * DeerFlow Suggestion 单条组件
 *
 * 参考: frontend/src/components/ai-elements/suggestion.tsx Suggestion
 */
defineProps<{
  text: string
  animationDelay?: string
}>()

const emit = defineEmits<{
  click: []
}>()
</script>

<template>
  <button
    class="suggestion-chip"
    :style="{ animationDelay }"
    @click="emit('click')"
  >
    {{ text }}
  </button>
</template>

<style scoped>
.suggestion-chip {
  opacity: 0;
  animation: fade-in-up 0.15s ease-in-out forwards;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
}

.suggestion-chip:hover {
  border-color: var(--van-primary-color);
  color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 8%, var(--card-bg));
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.suggestion-chip:active {
  transform: translateY(0);
  box-shadow: none;
}

/* DeerFlow reference: globals.css @keyframes fade-in-up */
@keyframes fade-in-up {
  0% {
    opacity: 0;
    transform: translateY(1rem) scale(1.2);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* 375px */
@media (max-width: 375px) {
  .suggestion-chip {
    max-width: 150px;
    font-size: 11px;
    padding: 6px 12px;
  }
}
</style>