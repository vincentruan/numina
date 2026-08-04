<script setup lang="ts">
/**
 * U6: Suggestion chips (NOT pills) for follow-up prompts.
 *
 * Per Vant 4 guidelines: border-radius 4px for buttons/badges, NOT pill-shaped.
 * Templates like "查看{category}详情" with context-derived interpolation.
 *
 * Overflow chips with long text auto-scroll (marquee) for readability on mobile.
 * Each chip has a dismiss (X) button in the top-right corner.
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

// ── Dismiss: track removed chips by value ──
const dismissedChips = ref(new Set<string>())

const visibleSuggestions = computed(() => {
  if (dismissedChips.value.size === 0) return props.suggestions
  return props.suggestions.filter((s) => !dismissedChips.value.has(s))
})

function dismissChip(text: string) {
  dismissedChips.value.add(text)
  nextTick(() => measureOverflow())
}

// ─ Marquee: detect overflow chips and apply scroll animation ──
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
      const textEl = chip.querySelector('.suggestion-chip__text') as HTMLElement | null
      const text = textEl?.textContent ?? chip.textContent ?? ''
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
    v-if="visibleSuggestions.length > 0"
    ref="containerRef"
    class="suggestion-chips"
    :class="{ 'suggestion-chips--static': prefersReducedMotion }"
    role="group"
    :aria-label="t('aiChat.suggestionsAria')"
  >
    <button
      v-for="(text, idx) in visibleSuggestions"
      :key="text"
      class="suggestion-chip"
      :class="{ 'suggestion-chip--scrolling': overflowIdxs.has(idx) }"
      type="button"
      @click="handleClick(text)"
    >
      <span class="suggestion-chip__text">{{ text }}</span>
      <span
        class="suggestion-chip__dismiss"
        role="button"
        tabindex="0"
        :aria-label="t('aiChat.suggestionRemove')"
        @click.stop="dismissChip(text)"
        @keydown.enter.prevent="dismissChip(text)"
        @keydown.space.prevent="dismissChip(text)"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </span>
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
  padding: 6px 28px 6px 12px; /* extra right padding for dismiss button */
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

/* Dismiss button: positioned top-right inside chip */
.suggestion-chip__dismiss {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--text-secondary);
  opacity: 0;
  cursor: pointer;
  transition: opacity 0.15s, background 0.15s;
}

.suggestion-chip:hover .suggestion-chip__dismiss {
  opacity: 0.7;
}

.suggestion-chip__dismiss:hover {
  opacity: 1 !important;
  background: rgba(128, 128, 128, 0.15);
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
    padding: 5px 24px 5px 10px;
    max-width: 180px;
    flex-shrink: 0;
  }
}
</style>