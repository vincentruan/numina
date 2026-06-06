<script setup lang="ts">
/**
 * U6: Suggestion chips (NOT pills) for follow-up prompts.
 *
 * Per Vant 4 guidelines: border-radius 4px for buttons/badges, NOT pill-shaped.
 * Templates like "查看{category}详情" with context-derived interpolation.
 */

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  /** List of suggestion strings to display */
  suggestions: string[]
}>()

const emit = defineEmits<{
  (e: 'select', text: string): void
}>()

const { t } = useI18n()

// Check for reduced motion preference
const prefersReducedMotion = computed(() => {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
})

const handleClick = (text: string) => {
  emit('select', text)
}
</script>

<template>
  <div
    v-if="suggestions.length > 0"
    class="suggestion-chips"
    :class="{ 'suggestion-chips--static': prefersReducedMotion }"
    role="group"
    :aria-label="t('aiChat.suggestionsAria')"
  >
    <button
      v-for="(text, idx) in suggestions"
      :key="idx"
      class="suggestion-chip"
      type="button"
      @click="handleClick(text)"
    >
      {{ text }}
    </button>
  </div>
</template>

<style scoped>
.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0;
  animation: fade-in 0.2s ease-out;
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Reduced motion: no animation */
.suggestion-chips--static {
  animation: none;
}

.suggestion-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, rgba(255, 255, 255, 0.85));
  background: var(--suggestion-bg, rgba(255, 255, 255, 0.08));
  border: 1px solid var(--suggestion-border, rgba(255, 255, 255, 0.12));
  border-radius: 4px; /* 4px sharp radius */
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.suggestion-chip:hover {
  background: var(--suggestion-bg, rgba(255, 255, 255, 0.12));
  border-color: var(--suggestion-border, rgba(255, 255, 255, 0.2));
}

.suggestion-chip:focus-visible {
  outline: 2px solid var(--van-primary-color, #007aff);
  outline-offset: 2px;
}

/* Mobile: smaller, can scroll */
@media (max-width: 375px) {
  .suggestion-chips {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: 12px; /* Extra space for scrollbar */
  }

  .suggestion-chip {
    font-size: 13px;
    padding: 5px 10px;
    max-width: 140px;
  }
}
</style>