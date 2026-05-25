<template>
  <!-- eslint-disable-next-line vue/no-v-html -- sanitized via userMarkdownSanitizer -->
  <div class="ai-user-bubble" v-html="renderedContent" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeUserMarkdown } from '@/utils/userMarkdownSanitizer'

const props = defineProps<{
  content: string
}>()

const renderedContent = computed(() => sanitizeUserMarkdown(props.content))
</script>

<style scoped>
.ai-user-bubble {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

.ai-user-bubble :deep(p) {
  margin: 0 0 4px;
}

.ai-user-bubble :deep(p:last-child) {
  margin-bottom: 0;
}

.ai-user-bubble :deep(strong),
.ai-user-bubble :deep(b) {
  font-weight: 600;
  color: var(--text-primary);
}

.ai-user-bubble :deep(em),
.ai-user-bubble :deep(i) {
  font-style: italic;
}

.ai-user-bubble :deep(code) {
  background: var(--bg-secondary);
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.ai-user-bubble :deep(a) {
  color: var(--color-action-blue);
  text-decoration: underline;
}

.ai-user-bubble :deep(a:hover) {
  opacity: 0.8;
}
</style>
