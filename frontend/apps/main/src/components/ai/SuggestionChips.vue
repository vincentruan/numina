<script setup lang="ts">
/**
 * U6: Suggestion chips (NOT pills) for follow-up prompts.
 *
 * Per Vant 4 guidelines: border-radius 4px for buttons/badges, NOT pill-shaped.
 * Templates like "查看{category}详情" with context-derived interpolation.
 *
 * Overflow chips with long text auto-scroll (marquee) for readability on mobile.
 */

import { computed, ref, watch, nextTick, onMounted } from 'vue'
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

// ── Marquee: detect overflow chips and apply scroll animation ──
const containerRef = ref<HTMLDivElement | null>(null)
const overflowIdxs = ref<Set<number>>(new Set())

function measureOverflow() {
  const container = containerRef.value
  if (!container || prefersReducedMotion.value) return

  // nextTick ensures DOM is painted before measuring
  nextTick(() => {
    const chips = container.querySelectorAll<HTMLButtonElement>('.suggestion-chip')
    const next = new Set<number>()

    chips.forEach((chip, idx) => {
      const text = chip.textContent ?? ''
      if (!text) return

      // Use scrollWidth vs clientWidth to detect overflow
      // (clientWidth is the visible area; scrollWidth is the full content width)
      const overflows = chip.scrollWidth > chip.clientWidth + 2
      if (overflows) {
        next.add(idx)
        // Set scroll distance as CSS variable for the animation
        const distance = chip.scrollWidth - chip.clientWidth
        chip.style.setProperty('--marquee-distance', `-${Math.round(distance)}px`)
      }
    })

    overflowIdxs.value = next
  })
}

// Re-measure when suggestions change
watch(
  () => props.suggestions,
  () => {
    overflowIdxs.value = new Set()
    nextTick(() => measureOverflow())
  },
  { deep: true }
)

// Initial measurement on mount (v-if may render with data already present)
onMounted(() => {
  measureOverflow()
})

const handleClick = (text: string) => {
  emit('select', text)
}
</script>

<template>
  <div
    v-if="suggestions.length > 0"
    ref="containerRef"
    class="suggestion-chips"
    :class="{ 'suggestion-chips--static': prefersReducedMotion }"
    role="group"
    :aria-label="t('aiChat.suggestionsAria')"
  >
    <button
      v-for="(text, idx) in suggestions"
      :key="idx"
      class="suggestion-chip"
      :class="{ 'suggestion-chip--scrolling': overflowIdxs.has(idx) }"
      type="button"
      @click="handleClick(text)"
    >
      <span class="suggestion-chip__text">{{ text }}</span>
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
  position: relative;
  display: inline-flex;
  align-items: center;
  max-width: min(100%, 280px);
  padding: 6px 12px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, rgba(255, 255, 255, 0.85));
  background: var(--suggestion-bg, rgba(255, 255, 255, 0.08));
  border: 1px solid var(--suggestion-border, rgba(255, 255, 255, 0.12));
  border-radius: 4px; /* 4px sharp radius */
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  overflow: hidden;
  text-align: left;
}

.suggestion-chip:hover {
  background: var(--suggestion-bg, rgba(255, 255, 255, 0.12));
  border-color: var(--suggestion-border, rgba(255, 255, 255, 0.2));
}

.suggestion-chip:focus-visible {
  outline: 2px solid var(--van-primary-color, #007aff);
  outline-offset: 2px;
}

/* Text span — normal state: truncate with ellipsis */
.suggestion-chip__text {
  display: inline-block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

/* Overflow scrolling — remove truncation and animate */
.suggestion-chip--scrolling .suggestion-chip__text {
  max-width: none;
  overflow: visible;
  text-overflow: clip;
  animation: suggestion-marquee 8s ease-in-out infinite;
}

@keyframes suggestion-marquee {
  0%, 15% {
    transform: translateX(0);
  }
  75%, 100% {
    transform: translateX(var(--marquee-distance, -50%));
  }
}

/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .suggestion-chip--scrolling .suggestion-chip__text {
    animation: none;
  }
}

/* Mobile: smaller */
@media (max-width: 375px) {
  .suggestion-chips {
    flex-wrap: nowrap;
    overflow-x: auto;
    padding-bottom: 12px; /* Extra space for scrollbar */
  }

  .suggestion-chip {
    font-size: 13px;
    padding: 5px 10px;
    max-width: 180px;
    flex-shrink: 0;
  }
}
</style>