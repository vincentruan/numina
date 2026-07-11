<script setup lang="ts">
/**
 * ChainOfThoughtSearchResults 组件
 *
 * 参考 DeerFlow chain-of-thought.tsx:
 * - ChainOfThoughtSearchResults: flex flex-wrap items-center gap-2
 * - ChainOfThoughtSearchResult: Badge variant="secondary" gap-1 px-2 py-0.5 text-xs
 *
 * 用于 web_search / image_search / web_fetch 工具的结果展示。
 * 结果以 Badge 药丸样式水平排列，点击在新标签页打开。
 */

interface SearchResult {
  url: string
  title?: string
  snippet?: string
}

const props = defineProps<{
  results: SearchResult[]
}>()

function openResult(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <!-- DeerFlow pattern: flex flex-wrap items-center gap-2 -->
  <div class="search-results">
    <a
      v-for="(result, idx) in props.results"
      :key="`${result.url}-${idx}`"
      :href="result.url"
      target="_blank"
      rel="noopener noreferrer"
      class="search-badge"
      @click.prevent="openResult(result.url)"
    >
      {{ result.title || result.url }}
    </a>
  </div>
</template>

<style scoped>
/* DeerFlow ChainOfThoughtSearchResults: flex flex-wrap items-center gap-2 overflow-x-hidden */
.search-results {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px; /* DeerFlow gap-2 */
  overflow-x: hidden;
  padding-top: 4px;
}

/* DeerFlow ChainOfThoughtSearchResult: Badge variant="secondary" gap-1 px-2 py-0.5 text-xs font-normal */
.search-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px; /* DeerFlow gap-1 */
  padding: 2px 8px; /* DeerFlow py-0.5 px-2 */
  font-size: 12px; /* DeerFlow text-xs */
  font-weight: 400; /* DeerFlow font-normal */
  color: var(--text-secondary);
  background: var(--bg-secondary, rgba(127, 127, 127, 0.12));
  border-radius: 9999px; /* Badge rounded-full */
  text-decoration: none;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: all 0.15s ease;
  cursor: pointer;
}

.search-badge:hover {
  background: var(--bg-secondary-hover, rgba(127, 127, 127, 0.2));
  color: var(--van-primary-color);
}

/* 375px */
@media (max-width: 375px) {
  .search-badge {
    font-size: 11px;
    max-width: 180px;
  }
}
</style>
