<script setup lang="ts">
/**
 * TableActionBar - 操作栏（复制为 markdown / 下载 CSV）
 *
 * 参考 DeerFlow 截图：仅图标按钮，浮动在表格右上角（无文字标签）。
 * 由 MarkdownContent.vue 的锚点定位逻辑注入到表格容器内。
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
    <button
      class="tab-btn"
      type="button"
      :aria-label="t('aiChat.copyTableAsMarkdown')"
      :title="t('aiChat.copyTableAsMarkdown')"
      @click="onCopyMarkdown"
    >
      <svg v-if="!copied" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
      </svg>
      <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    </button>
    <button
      class="tab-btn"
      type="button"
      :aria-label="t('aiChat.downloadTable')"
      :title="t('aiChat.downloadTable')"
      @click="onDownloadCsv"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
/* DeerFlow 模式：仅图标，浮动在表格右上角 */
.table-action-bar {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
  z-index: 5;
  opacity: 1;
  transition: opacity 0.15s ease;
}

/* 桌面端（支持 hover）：默认半透明，hover 时完全不透明 */
@media (hover: hover) {
  .table-action-bar {
    opacity: 0.5;
  }

  :global(.table-wrapper:hover .table-action-bar) {
    opacity: 1;
  }
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  color: var(--text-secondary, #999);
  background: var(--card-bg, rgba(255, 255, 255, 0.9));
  border: 1px solid var(--border-color, rgba(0, 0, 0, 0.08));
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: var(--van-primary-color, #6366f1);
  border-color: var(--van-primary-color, #6366f1);
  background: var(--card-bg, rgba(255, 255, 255, 1));
}

.tab-btn:active {
  transform: scale(0.92);
}
</style>
