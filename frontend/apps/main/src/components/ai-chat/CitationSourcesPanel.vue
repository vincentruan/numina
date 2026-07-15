<script setup lang="ts">
/**
 * CitationSourcesPanel component
 *
 * Reference: DeerFlow frontend/src/components/workspace/citations/citation-sources-panel.tsx
 *
 * Displays a collapsible list of citation sources used in the AI response.
 * Each source shows: index, title, domain, citation count, and external link.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast } from 'vant'
import type { CitationSource } from '@/utils/ai-chat/citations'
import { formatCitationMarkdownReference } from '@/utils/ai-chat/citations'

const { t } = useI18n()

const props = defineProps<{
  sources: CitationSource[]
}>()

const copiedIndex = ref<number | null>(null)

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./i, '')
  } catch {
    return url
  }
}

async function copySource(source: CitationSource, index: number) {
  const markdown = formatCitationMarkdownReference(source)
  try {
    await navigator.clipboard.writeText(markdown)
    copiedIndex.value = index
    showSuccessToast(t('aiChat.copiedSuccess'))
    setTimeout(() => {
      copiedIndex.value = null
    }, 2000)
  } catch {
    // Copy failed silently
  }
}
</script>

<template>
  <details v-if="sources.length > 0" class="citation-sources-panel">
    <summary class="citation-sources-summary">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
      </svg>
      <span class="citation-sources-title">
        {{ t('aiChat.usedSources', { count: sources.length }) }}
      </span>
    </summary>
    <ol class="citation-sources-list">
      <li
        v-for="(source, index) in sources"
        :key="source.id"
        class="citation-source-item"
      >
        <span class="citation-source-index">{{ index + 1 }}</span>
        <a
          :href="source.url"
          target="_blank"
          rel="noopener noreferrer"
          class="citation-source-link"
        >
          <div class="citation-source-info">
            <span class="citation-source-title">{{ source.title }}</span>
            <span class="citation-source-domain">{{ source.domain }}</span>
          </div>
          <span class="citation-source-count">
            {{ t('aiChat.citedTimes', { count: source.count }) }}
          </span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
        <button
          class="citation-source-copy"
          :title="t('aiChat.copyReference')"
          @click.prevent="copySource(source, index)"
        >
          <svg v-if="copiedIndex === index" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
        </button>
      </li>
    </ol>
  </details>
</template>

<style scoped>
.citation-sources-panel {
  margin-top: 12px;
  border: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  background: rgba(127, 127, 127, 0.04);
  font-size: 13px;
}

.citation-sources-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  user-select: none;
  color: var(--text-secondary, #999);
  transition: color 0.2s;
}

.citation-sources-summary:hover {
  color: var(--text-primary, #fff);
}

.citation-sources-summary::-webkit-details-marker {
  display: none;
}

.citation-sources-summary svg {
  flex-shrink: 0;
  color: var(--text-secondary, #999);
}

.citation-sources-title {
  font-weight: 500;
  color: var(--text-secondary, #999);
}

.citation-sources-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.08));
  max-height: 320px;
  overflow-y: auto;
}

.citation-source-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--van-border-color, rgba(255, 255, 255, 0.06));
}

.citation-source-item:last-child {
  border-bottom: none;
}

.citation-source-index {
  flex-shrink: 0;
  width: 20px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary, #999);
  font-size: 12px;
}

.citation-source-link {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 4px 8px;
  border-radius: 6px;
  text-decoration: none;
  transition: background 0.2s;
}

.citation-source-link:hover {
  background: rgba(127, 127, 127, 0.08);
}

.citation-source-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.citation-source-title {
  font-weight: 500;
  color: var(--text-primary, #fff);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-source-domain {
  font-size: 12px;
  color: var(--text-secondary, #999);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.citation-source-count {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-secondary, #999);
}

.citation-source-link svg {
  flex-shrink: 0;
  color: var(--text-secondary, #999);
}

.citation-source-copy {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary, #999);
  cursor: pointer;
  transition: all 0.2s;
}

.citation-source-copy:hover {
  background: rgba(127, 127, 127, 0.08);
  color: var(--text-primary, #fff);
}

/* Light theme */
:global([data-theme='light']) .citation-sources-panel {
  background: rgba(0, 0, 0, 0.02);
  border-color: rgba(0, 0, 0, 0.08);
}

:global([data-theme='light']) .citation-sources-list {
  border-color: rgba(0, 0, 0, 0.08);
}

:global([data-theme='light']) .citation-source-item {
  border-color: rgba(0, 0, 0, 0.06);
}

:global([data-theme='light']) .citation-source-link:hover {
  background: rgba(0, 0, 0, 0.04);
}

:global([data-theme='light']) .citation-source-copy:hover {
  background: rgba(0, 0, 0, 0.04);
}
</style>
