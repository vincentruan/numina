<script setup lang="ts">
/**
 * ChainOfThoughtSearchResults 组件
 *
 * 用于 web_search / image_search 工具的结果展示
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import IIcon from '@/components/IIcon.vue'

const { t } = useI18n()

interface SearchResult {
  url: string
  title?: string
  snippet?: string
}

const props = defineProps<{
  results: SearchResult[]
  maxVisible?: number
}>()

const expanded = ref(false)
const visibleResults = computed(() =>
  expanded.value ? props.results : props.results.slice(0, props.maxVisible || 3),
)
const hiddenCount = computed(() => props.results.length - visibleResults.value.length)

function openResult(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
}
</script>

<template>
  <div class="search-results">
    <div
      v-for="(result, idx) in visibleResults"
      :key="`${result.url}-${idx}`"
      class="result-item"
      @click="openResult(result.url)"
    >
      <IIcon icon="external-link" class="result-icon" />
      <span class="result-title">{{ result.title || result.url }}</span>
    </div>

    <!-- 展开/折叠 -->
    <button
      v-if="hiddenCount > 0"
      class="expand-btn"
      @click="expanded = !expanded"
    >
      {{ expanded ? t('aiChat.collapse') : t('aiChat.moreResults', { count: hiddenCount }) }}
    </button>
  </div>
</template>

<style scoped>
.search-results {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: var(--bg-primary);
  border-radius: 6px;
  margin-left: 24px;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.2s;
}

.result-item:hover {
  background: var(--card-bg);
}

.result-icon {
  width: 12px;
  height: 12px;
  color: var(--van-primary-color);
}

.result-title {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.expand-btn {
  padding: 4px 8px;
  font-size: 12px;
  color: var(--van-primary-color);
  background: transparent;
  border: none;
  cursor: pointer;
}

/* 375px */
@media (max-width: 375px) {
  .result-title {
    font-size: 12px;
    max-width: 160px;
  }
}
</style>