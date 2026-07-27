<template>
  <van-popup
    :show="visible"
    position="bottom"
    :style="{ height: '80%', borderRadius: '16px 16px 0 0' }"
    closeable
    close-icon-position="top-right"
    @update:show="onUpdateShow"
  >
    <div class="markdown-preview">
      <div class="preview-header">
        <h3 class="preview-title">{{ t('aiReport.markdownPreview') }}</h3>
        <span class="preview-meta">{{ filename }} · {{ formatSize(fileSize) }}</span>
      </div>
      <!-- eslint-disable vue/no-v-html -->
      <div class="preview-content" v-html="renderedContent" />
      <div class="preview-footer">
        <van-button type="primary" size="small" @click="onDownload">
          <van-icon name="down" class="download-icon" />
          {{ t('aiReport.downloadReport') }}
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const PURIFY_CONFIG = {
  USE_PROFILES: { html: true },
  ALLOW_DATA_ATTR: false,
} as const

const { t } = useI18n()

interface Props {
  content: string
  filename: string
  fileSize: number
  visible: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const renderedContent = computed(() => {
  if (!props.content) return ''
  const raw = marked.parse(props.content, { async: false }) as string
  return DOMPurify.sanitize(raw, PURIFY_CONFIG)
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function onUpdateShow(value: boolean) {
  emit('update:visible', value)
}

function onDownload() {
  const blob = new Blob([props.content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = props.filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.markdown-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
}
.preview-header {
  padding-bottom: 12px;
  border-bottom: 1px solid var(--separator);
  margin-bottom: 12px;
}
.preview-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px;
}
.preview-meta {
  font-size: 12px;
  color: var(--text-secondary);
}
.preview-content {
  flex: 1;
  overflow-y: auto;
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.7;
  padding: 0 4px;
  :deep(h1) {
    font-size: 20px;
    font-weight: 700;
    margin: 16px 0 12px;
    color: var(--text-primary);
  }
  :deep(h2) {
    font-size: 18px;
    font-weight: 600;
    margin: 14px 0 10px;
    color: var(--text-primary);
  }
  :deep(h3) {
    font-size: 16px;
    font-weight: 600;
    margin: 12px 0 8px;
    color: var(--text-primary);
  }
  :deep(p) {
    margin: 0 0 10px;
  }
  :deep(strong) {
    font-weight: 600;
  }
  :deep(ul), :deep(ol) {
    margin: 8px 0;
    padding-left: 20px;
  }
  :deep(li) {
    margin: 4px 0;
  }
  :deep(code) {
    background: var(--bg-secondary);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
  }
  :deep(pre) {
    background: var(--bg-secondary);
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 10px 0;
  }
  :deep(blockquote) {
    border-left: 3px solid var(--color-primary);
    margin: 10px 0;
    padding-left: 12px;
    color: var(--text-secondary);
  }
  :deep(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
  }
  :deep(th), :deep(td) {
    border: 1px solid var(--separator);
    padding: 8px 12px;
    text-align: left;
  }
  :deep(th) {
    background: var(--bg-secondary);
    font-weight: 600;
  }
  :deep(hr) {
    border: none;
    height: 1px;
    background: var(--separator);
    margin: 16px 0;
  }
}
.preview-footer {
  padding-top: 12px;
  border-top: 1px solid var(--separator);
  display: flex;
  justify-content: center;
}
.download-icon {
  margin-right: 4px;
}
</style>