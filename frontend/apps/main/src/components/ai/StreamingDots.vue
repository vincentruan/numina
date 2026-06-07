<script setup lang="ts">
/**
 * U6: Streaming indicator with three bouncing dots.
 *
 * Replaces flickering cursor with DeerFlow-style bouncing dots.
 * 0.2s stagger delay per dot.
 *
 * Per Vant 4 guidelines: respects prefers-reduced-motion (static dots).
 */

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Check for reduced motion preference
const prefersReducedMotion = computed(() => {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
})
</script>

<template>
  <span
    class="streaming-dots"
    :class="{ 'streaming-dots--static': prefersReducedMotion }"
    aria-hidden="true"
  >
    <!-- Visually hidden live region for screen readers -->
    <span class="sr-only">{{ t('aiChat.generatingResponse') }}</span>
    <!-- Three bouncing dots -->
    <span class="dot dot--1" />
    <span class="dot dot--2" />
    <span class="dot dot--3" />
  </span>
</template>

<style scoped>
.streaming-dots {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px;
}

/* Screen reader only */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-secondary, rgba(255, 255, 255, 0.55));
  animation: bounce 1s ease-in-out infinite;
}

.dot--1 {
  animation-delay: 0s;
}

.dot--2 {
  animation-delay: 0.2s;
}

.dot--3 {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-6px);
  }
}

/* Reduced motion: static dots */
.streaming-dots--static .dot {
  animation: none;
}

/* Mobile: slightly smaller */
@media (max-width: 375px) {
  .dot {
    width: 5px;
    height: 5px;
  }
}
</style>