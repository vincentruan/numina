<template>
  <div class="report-card">
    <div class="card-header">
      <div class="card-title-row">
        <van-icon :name="icon" class="card-icon" aria-hidden="true" />
        <span class="card-title">{{ title }}</span>
      </div>
      <ReportScoreBadge :score="score" :max="5" />
    </div>
    <!-- eslint-disable vue/no-v-html -->
    <div class="card-narrative" v-html="renderedNarrative" />
    <div v-if="suggestions?.length" class="card-suggestions">
      <div class="suggestions-header">
        <van-icon name="bulb-o" class="suggestions-icon" aria-hidden="true" />
        <span>{{ t('aiReport.suggestions') }}</span>
      </div>
      <ul class="suggestions-list">
        <li v-for="(item, idx) in suggestions" :key="idx">{{ item }}</li>
      </ul>
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useI18n } from 'vue-i18n'
import ReportScoreBadge from './ReportScoreBadge.vue'

const { t } = useI18n()

const ASSISTANT_PURIFY_CONFIG = {
  USE_PROFILES: { html: true },
  ALLOW_DATA_ATTR: false,
} as const

const props = defineProps<{
  icon: string
  title: string
  score: number
  narrative: string
  suggestions?: string[]
}>()

const renderedNarrative = computed(() => {
  if (!props.narrative) return ''
  const raw = marked.parse(props.narrative, { async: false }) as string
  return DOMPurify.sanitize(raw, ASSISTANT_PURIFY_CONFIG)
})
</script>

<style scoped>
.report-card {
  background: var(--bg-primary, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-icon {
  font-size: 20px;
  color: var(--van-primary-color);
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.card-narrative {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0;
  :deep(p) {
    margin: 0 0 8px;
    &:last-child { margin-bottom: 0; }
  }
  :deep(strong) {
    color: var(--text-primary);
    font-weight: 600;
  }
  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 6px 0;
    font-size: 12px;
  }
  :deep(th),
  :deep(td) {
    padding: 4px 6px;
    text-align: left;
    border-bottom: 1px solid var(--separator);
  }
  :deep(th) {
    font-weight: 600;
    color: var(--text-primary);
  }
  :deep(ul),
  :deep(ol) {
    margin: 4px 0;
    padding-left: 18px;
  }
  :deep(li) {
    margin: 3px 0;
  }
  :deep(ol li) {
    margin: 2px 0;
  }
  :deep(code) {
    background: var(--bg-secondary);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
  }
}
.card-suggestions {
  margin-top: 10px;
  border-top: 1px solid var(--separator);
  padding-top: 10px;
}
.suggestions-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--van-primary-color);
  margin-bottom: 6px;
}
.suggestions-icon {
  font-size: 16px;
}
.suggestions-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.suggestions-list li {
  margin: 3px 0;
}
</style>
