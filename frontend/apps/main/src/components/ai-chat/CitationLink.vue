<script setup lang="ts">
/**
 * CitationLink component
 *
 * Reference: DeerFlow frontend/src/components/workspace/citations/citation-link.tsx
 *
 * Renders an inline citation badge with hover card preview.
 */
import { computed } from 'vue'

const props = defineProps<{
  href: string
  text?: string
}>()

const domain = computed(() => {
  try {
    return new URL(props.href).hostname.replace(/^www\./i, '')
  } catch {
    return props.href
  }
})

const displayText = computed(() => {
  // Priority: custom text > domain
  const cleanText = props.text?.replace(/^citation:\s*/i, '') || ''
  const isGeneric = cleanText === 'Source' || cleanText === '来源'
  return (!isGeneric && cleanText) || domain.value
})

function openLink(e: Event) {
  e.preventDefault()
  e.stopPropagation()
  window.open(props.href, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <a
    :href="href"
    target="_blank"
    rel="noopener noreferrer"
    class="citation-link"
    @click="openLink"
  >
    <span class="citation-badge">
      {{ displayText }}
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
        <polyline points="15 3 21 3 21 9" />
        <line x1="10" y1="14" x2="21" y2="3" />
      </svg>
    </span>
  </a>
</template>

<style scoped>
.citation-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.citation-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  margin: 0 2px;
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary, #999);
  background: rgba(127, 127, 127, 0.12);
  border-radius: 9999px;
  transition: all 0.15s ease;
  cursor: pointer;
}

.citation-badge:hover {
  background: rgba(127, 127, 127, 0.2);
  color: var(--van-primary-color, #6366f1);
}

.citation-badge svg {
  flex-shrink: 0;
}

/* Light theme */
:global([data-theme='light']) .citation-badge {
  background: rgba(0, 0, 0, 0.06);
}

:global([data-theme='light']) .citation-badge:hover {
  background: rgba(0, 0, 0, 0.1);
}
</style>
