<template>
  <div class="empty-state">
    <div class="empty-state__illustration" aria-hidden="true" v-html="illustrationSvg" />
    <p class="empty-state__text">{{ text }}</p>
    <router-link v-if="actionText && actionTo" :to="actionTo" class="empty-state__btn">
      {{ actionText }}
    </router-link>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  /** Raw SVG string (inline) or a URL path to an SVG asset */
  illustration: string
  /** i18n-resolved message text */
  text: string
  /** Optional button label — no button rendered if omitted */
  actionText?: string
  /** Router path for the action button */
  actionTo?: string
}>()

/**
 * If `illustration` looks like a URL (starts with / or http), wrap it in an
 * <img> tag so the SVG is loaded as an external resource.  Otherwise treat it
 * as raw SVG markup and inject it directly so `currentColor` inherits from CSS.
 */
const illustrationSvg = computed(() => {
  const src = props.illustration
  if (src.startsWith('/') || src.startsWith('http')) {
    return `<img src="${src}" width="120" height="120" alt="" />`
  }
  return src
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px var(--space-lg);
  text-align: center;
  color: var(--color-muted-soft);
}

.empty-state__illustration {
  width: 120px;
  height: 120px;
  margin-bottom: var(--space-lg);
  color: var(--color-muted-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Ensure injected SVG fills the container */
.empty-state__illustration :deep(svg) {
  width: 120px;
  height: 120px;
}

.empty-state__illustration :deep(img) {
  width: 120px;
  height: 120px;
  object-fit: contain;
}

.empty-state__text {
  font-family: Inter, sans-serif;
  font-size: 15px;
  color: var(--color-muted-soft);
  margin: 0 0 var(--space-lg);
  line-height: 1.5;
  max-width: 240px;
}

.empty-state__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 44px;
  padding: 0 var(--space-xl);
  background: var(--color-brand-peach);
  color: var(--color-ink);
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: transform 0.1s;
}

.empty-state__btn:active {
  transform: scale(0.97);
}
</style>
