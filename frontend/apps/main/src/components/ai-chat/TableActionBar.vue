<script setup lang="ts">
/**
 * TableActionBar — 操作栏（复制为 markdown / 下载 CSV）
 *
 * 渲染在每个 markdown 表格上方，提供 R6 的两个操作按钮。
 */
import { ref } from 'vue'
import { showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import {
  htmlTableToMarkdown,
  htmlTableToCsv,
  downloadCsv,
  copyToClipboard,
} from '@/utils/ai-chat/tableUtils'

const props = defineProps<{
  tableHtml: string
}>()

const { t } = useI18n()
const copied = ref(false)

async function onCopyMarkdown() {
  const markdown = htmlTableToMarkdown(props.tableHtml)
  const ok = await copyToClipboard(markdown)
  if (ok) {
    copied.value = true
    showSuccessToast(t('aiChat.copiedSuccess'))
    setTimeout(() => { copied.value = false }, 1500)
  }
}

function onDownloadCsv() {
  const csv = htmlTableToCsv(props.tableHtml)
  downloadCsv(csv)
  showSuccessToast(t('aiChat.tableDownloaded'))
}
</script>

<template>
  <div class="table-action-bar">
    <button class="tab-btn" type="button" @click="onCopyMarkdown">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
      <span>{{ copied ? t('aiChat.copiedSuccess') : t('aiChat.copyTableAsMarkdown') }}</span>
    </button>
    <button class="tab-btn" type="button" @click="onDownloadCsv">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      <span>{{ t('aiChat.downloadTable') }}</span>
    </button>
  </div>
</template>

<style scoped>
.table-action-bar {
  display: flex;
  gap: 8px;
  margin: 8px 0 4px;
  flex-wrap: wrap;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text-secondary, #999);
  background: var(--card-bg, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.tab-btn:hover {
  color: var(--van-primary-color, #6366f1);
  border-color: var(--van-primary-color, #6366f1);
}

.tab-btn:active {
  transform: scale(0.96);
}
</style>
