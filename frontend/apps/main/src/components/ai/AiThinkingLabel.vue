<script setup lang="ts">
/**
 * U3: Shimmer thinking label with auto-collapse.
 *
 * Replaces pulsing dot + timer with DeerFlow-style shimmer animation.
 * - Streaming: "思考中..." with shimmer sweep
 * - Done: "思考了 Xs" → auto-collapse after 1s (once)
 *
 * Per DESIGN.md: uses CSS variables, respects prefers-reduced-motion.
 */

import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  /** True while AI is streaming thinking content */
  isStreaming: boolean
  /** Duration in seconds (only meaningful when !isStreaming) */
  duration: number
}>()

const emit = defineEmits<{
  (e: 'auto-collapse'): void
}>()

const { t } = useI18n()

// Auto-collapse state: fires once after streaming ends
const hasAutoCollapsed = ref(false)
let collapseTimer: ReturnType<typeof setTimeout> | null = null

watch(
  () => props.isStreaming,
  (streaming, wasStreaming) => {
    // Transition from streaming → done: start auto-collapse timer
    if (wasStreaming && !streaming && !hasAutoCollapsed.value) {
      collapseTimer = setTimeout(() => {
        hasAutoCollapsed.value = true
        emit('auto-collapse')
      }, 1000) // 1 second delay per DeerFlow reasoning.tsx
    }
    // Re-streaming: clear any pending collapse
    if (streaming && collapseTimer) {
      clearTimeout(collapseTimer)
      collapseTimer = null
    }
  },
  { immediate: true }
)

onUnmounted(() => {
  if (collapseTimer) clearTimeout(collapseTimer)
})

// Display text based on state
const displayText = computed(() => {
  if (props.isStreaming) {
    return t('aiChat.thinkingLabel')
  }
  // Use floor so durations < 1 show '<1s'
  const seconds = Math.floor(props.duration)
  if (seconds < 1) {
    return t('aiChat.thoughtSeconds', { seconds: '<1' })
  }
  return t('aiChat.thoughtSeconds', { seconds: String(seconds) })
})

// Duration display for done state
const durationDisplay = computed(() => {
  if (props.isStreaming) return ''
  const seconds = Math.floor(props.duration)
  return seconds < 1 ? '<1s' : `${seconds}s`
})

// Check for reduced motion preference
const prefersReducedMotion = computed(() => {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
})
</script>

<template>
  <div
    class="ai-thinking-label"
    :class="{
      'ai-thinking-label--streaming': isStreaming,
      'ai-thinking-label--done': !isStreaming,
      'ai-thinking-label--static': prefersReducedMotion,
    }"
    :aria-live="isStreaming ? 'polite' : undefined"
    :aria-label="displayText"
  >
    <!-- Shimmer text during streaming -->
    <span v-if="isStreaming" class="thinking-text shimmer-text">
      {{ displayText }}
    </span>
    <!-- Done state: static text -->
    <span v-else class="thinking-text">
      {{ displayText }}
    </span>
  </div>
</template>

<style scoped>
.ai-thinking-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px; /* DESIGN.md: sharp for buttons/badges */
  background: var(--think-bg, rgba(99, 102, 241, 0.08));
  border: 1px solid var(--think-border, rgba(99, 102, 241, 0.25));
  font-size: 13px;
  font-weight: 500;
  color: var(--think-color, rgba(255, 255, 255, 0.55));
  transition: background 0.2s ease, border-color 0.2s ease;
}

/* Streaming state: slight highlight */
.ai-thinking-label--streaming {
  background: var(--think-bg, rgba(99, 102, 241, 0.12));
}

/* Done state: muted */
.ai-thinking-label--done {
  background: var(--think-bg, rgba(99, 102, 241, 0.06));
  border-color: var(--think-border, rgba(99, 102, 241, 0.15));
}

.thinking-text {
  white-space: nowrap;
}

/* Shimmer animation: gradient sweep left-to-right, 2s cycle */
.shimmer-text {
  background-image: linear-gradient(
    90deg,
    var(--shimmer-color, rgba(255, 255, 255, 0.06)) 0%,
    rgba(129, 140, 248, 0.7) 25%,
    #818cf8 50%,
    rgba(129, 140, 248, 0.7) 75%,
    var(--shimmer-color, rgba(255, 255, 255, 0.06)) 100%
  );
  background-size: 200% 100%;
  animation: shimmer-sweep 2s linear infinite;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent; /* Fallback for non-webkit browsers */
}

@keyframes shimmer-sweep {
  0% {
    background-position: 100% 0; /* Start from right */
  }
  100% {
    background-position: -100% 0; /* Sweep left */
  }
}

/* Reduced motion: static text without animation */
.ai-thinking-label--static .shimmer-text {
  background-image: none;
  -webkit-text-fill-color: inherit;
  color: var(--think-color, rgba(255, 255, 255, 0.55));
  animation: none;
}

/* Mobile: slightly smaller */
@media (max-width: 375px) {
  .ai-thinking-label {
    font-size: 12px;
    padding: 3px 6px;
  }
}
</style>