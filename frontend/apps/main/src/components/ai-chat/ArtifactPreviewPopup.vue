<script setup lang="ts">
/**
 * DeerFlow ArtifactPreviewPopup 组件 — 移动端全屏预览
 *
 * 参考: frontend/src/components/workspace/artifacts/artifact-file-detail.tsx
 *
 * 功能:
 * - Vant Popup 全屏弹出层
 * - NavBar 头部（返回、复制、下载、新窗口打开）
 * - 预览类型切换（代码 vs 预览）
 * - 多种预览模式：
 *   - 代码：CodeBlock 高亮显示
 *   - Markdown：MarkdownContent 渲染
 *   - HTML：sandbox iframe（XSS 防护）
 *   - 图片：直接显示
 *   - PDF：iframe 或 force download
 *   - 未知：下载提示
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { Popup, NavBar, Button, Loading } from 'vant'
import { useI18n } from 'vue-i18n'
import IIcon from '@/components/IIcon.vue'
import CodeBlock from './CodeBlock.vue'
import MarkdownContent from './MarkdownContent.vue'
import CopyButton from '@/components/ai-chat/CopyButton.vue'
import {
  getFileName,
  getFileLanguage,
  isCodeFile,
  isMarkdownFile,
  isHtmlFile,
  isImageFile,
  isPdfFile,
} from '@/utils/ai-chat/fileType'
import { artifactDownloadUrl, artifactOpenUrl, artifactContentUrl } from '@/utils/ai-chat/artifactUrl'
import { useFamilyStore } from '@/stores/family'
import type { Artifact } from '@/types/agent-stream'

const { t } = useI18n()
const familyStore = useFamilyStore()

const props = defineProps<{
  show: boolean
  artifact: Artifact | null
  sessionId: string
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
}>()

// 预览模式切换
const viewMode = ref<'code' | 'preview'>('preview')

// 文件路径
const filepath = computed(() => props.artifact?.path || '')

// 内容加载状态
const contentRef = ref<string | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

// 内容缓存（5分钟 staleTime）- 使用 ref 确保每个组件实例独立
const contentCache = ref(new Map<string, { content: string; timestamp: number }>())
const STALE_TIME = 5 * 60 * 1000

// HTML iframe 高度自适应
const htmlFrameRef = ref<HTMLIFrameElement | null>(null)
const htmlFrameHeight = ref(600)

// 注入高度上报脚本到 HTML 内容，iframe 通过 postMessage 上报实际高度
const htmlSrcdoc = computed(() => {
  if (!contentRef.value) return ''
  // 拆分 <\/script> 避免 SFC 解析器误识别为脚本块结束
  const scriptClose = '<' + '/script>'
  const resizeScript = `<script>(function(){function sendHeight(){window.parent.postMessage({type:'numina-artifact-height',height:Math.max(document.documentElement.scrollHeight,document.body.scrollHeight,window.innerHeight)},'*')}window.addEventListener('load',sendHeight);new ResizeObserver(sendHeight).observe(document.body);new ResizeObserver(sendHeight).observe(document.documentElement)})();${scriptClose}`
  // 优先注入到 </head> 前，其次 </body> 前，最后直接前缀
  if (contentRef.value.includes('</head>')) {
    return contentRef.value.replace('</head>', resizeScript + '</head>')
  }
  if (contentRef.value.includes('<body>')) {
    return contentRef.value.replace('<body>', '<body>' + resizeScript)
  }
  return resizeScript + contentRef.value
})

// 监听 iframe postMessage 高度更新
function handleFrameMessage(event: MessageEvent) {
  if (event.data?.type === 'numina-artifact-height' && typeof event.data.height === 'number') {
    // 加上安全边距，确保不裁切
    htmlFrameHeight.value = Math.min(event.data.height + 16, 2000)
  }
}
if (typeof window !== 'undefined') {
  window.addEventListener('message', handleFrameMessage)
}
onUnmounted(() => {
  window.removeEventListener('message', handleFrameMessage)
})

async function loadContent() {
  if (!filepath.value || !props.sessionId) return

  const cacheKey = `${props.sessionId}:${filepath.value}`
  const cached = contentCache.value.get(cacheKey)
  if (cached && Date.now() - cached.timestamp < STALE_TIME) {
    contentRef.value = cached.content
    return
  }

  loading.value = true
  error.value = null

  try {
    // Use artifactContentUrl helper for correct path (uses /ai/sessions/ not /api/sessions/)
    const url = artifactContentUrl(filepath.value, props.sessionId)
    const familyId = familyStore.family?.id

    // P0: Guard - must have valid family context for tenant isolation
    if (!familyId) {
      throw new Error(t('errors.NO_FAMILY_CONTEXT'))
    }

    const response = await fetch(url, {
      headers: {
        'X-Family-Id': familyId,
      },
    })
    if (!response.ok) {
      throw new Error(t('aiArtifact.loadFailed'))
    }
    const result = await response.text()
    contentRef.value = result
    contentCache.value.set(cacheKey, { content: result, timestamp: Date.now() })
  } catch (e) {
    error.value = e instanceof Error ? e.message : t('aiArtifact.loadFailed')
  } finally {
    loading.value = false
  }
}

// 监听 artifact 变化加载内容
watch(
  [() => props.show, filepath],
  ([show, path]) => {
    if (show && path) {
      loadContent()
      // 默认预览模式
      viewMode.value = 'preview'
    }
  },
  { immediate: true },
)

// 文件类型判断
const isCode = computed(() => isCodeFile(filepath.value))
const isMarkdown = computed(() => isMarkdownFile(filepath.value))
const isHtml = computed(() => isHtmlFile(filepath.value))
const isImage = computed(() => isImageFile(filepath.value))
const isPdf = computed(() => isPdfFile(filepath.value))
const isUnknown = computed(
  () =>
    !isCode.value &&
    !isMarkdown.value &&
    !isHtml.value &&
    !isImage.value &&
    !isPdf.value,
)

// 代码高亮语言
const language = computed(() => getFileLanguage(filepath.value))

// 文件名
const filename = computed(() => getFileName(filepath.value))

// URL
const downloadUrl = computed(() =>
  props.artifact ? artifactDownloadUrl(filepath.value, props.sessionId) : '',
)
const openUrl = computed(() =>
  props.artifact ? artifactOpenUrl(filepath.value, props.sessionId) : '',
)

// NavBar 操作
function handleBack() {
  emit('update:show', false)
}

function handleDownload() {
  window.open(downloadUrl.value, '_blank', 'noopener,noreferrer')
}

async function handleOpenNewWindow() {
  const content = contentRef.value

  if (content) {
    // Use blob URL to bypass browser CSP — avoids script-src blocking
    // external CDN resources (e.g. Chart.js) and inline scripts in artifact HTML
    const blob = new Blob([content], { type: 'text/html;charset=utf-8' })
    const blobUrl = URL.createObjectURL(blob)
    window.open(blobUrl, '_blank', 'noopener,noreferrer')
    // Release blob after a delay (new tab loads synchronously via blob)
    setTimeout(() => URL.revokeObjectURL(blobUrl), 30_000)
  } else {
    window.open(openUrl.value, '_blank', 'noopener,noreferrer')
  }
}
</script>

<template>
  <Popup
    :show="show"
    position="bottom"
    :style="{ height: '100vh', width: '100%' }"
    round
    teleport="body"
    @update:show="emit('update:show', $event)"
  >
    <div class="artifact-preview-popup">
      <!-- NavBar 头部 -->
      <NavBar :title="filename" left-arrow clickable @click-left="handleBack">
        <template #right>
          <div class="nav-actions">
            <!-- 复制 -->
            <CopyButton
              v-if="contentRef"
              v-slot="{ copy }"
              :content="contentRef"
              success-key="toast.copied"
              fail-key="toast.copyFailed"
            >
              <Button size="small" plain @click="copy">
                <IIcon icon="lucide:copy" />
              </Button>
            </CopyButton>
            <!-- 下载 -->
            <Button size="small" plain @click="handleDownload">
              <IIcon icon="lucide:download" />
            </Button>
            <!-- 新窗口 -->
            <Button size="small" plain @click="handleOpenNewWindow">
              <IIcon icon="lucide:external-link" />
            </Button>
          </div>
        </template>
      </NavBar>

      <!-- 预览模式切换（仅代码文件） -->
      <div v-if="isCode" class="view-mode-tabs">
        <div
          class="view-mode-tab"
          :class="{ active: viewMode === 'preview' }"
          @click="viewMode = 'preview'"
        >
          <IIcon icon="lucide:eye" class="tab-icon" />
          {{ t('aiArtifact.viewModePreview') }}
        </div>
        <div
          class="view-mode-tab"
          :class="{ active: viewMode === 'code' }"
          @click="viewMode = 'code'"
        >
          <IIcon icon="lucide:code" class="tab-icon" />
          {{ t('aiArtifact.viewModeCode') }}
        </div>
      </div>

      <!-- 预览内容 -->
      <div class="preview-content">
        <!-- Loading -->
        <div v-if="loading" class="loading-state">
          <Loading size="24px" />
          <span>{{ t('aiArtifact.loadingContent') }}</span>
        </div>

        <!-- Error -->
        <div v-if="error" class="error-state">
          <IIcon icon="lucide:circle-x" />
          <span>{{ error }}</span>
          <Button size="small" type="primary" @click="loadContent">{{ t('aiArtifact.retry') }}</Button>
        </div>

        <!-- HTML sandbox iframe（viewMode=preview 时展示；高度自适应内容，外层滚动） -->
        <div v-if="!loading && !error && isHtml && contentRef && viewMode === 'preview'" class="html-preview">
          <iframe
            ref="htmlFrameRef"
            :srcdoc="htmlSrcdoc"
            sandbox="allow-scripts allow-forms"
            class="html-iframe"
            :style="{ height: htmlFrameHeight + 'px' }"
          />
        </div>

        <!-- 代码模式 -->
        <CodeBlock
          v-if="!loading && !error && viewMode === 'code' && contentRef"
          :language="language"
          :code="contentRef"
          :show-line-numbers="true"
          class="code-preview"
        />

        <!-- Markdown 预览 -->
        <MarkdownContent
          v-if="!loading && !error && isMarkdown && contentRef && viewMode === 'preview'"
          :content="contentRef"
          :is-loading="false"
          class="markdown-preview"
        />

        <!-- 图片预览 -->
        <div v-if="isImage && openUrl" class="image-preview">
          <img :src="openUrl" :alt="filename" class="preview-image" />
        </div>

        <!-- PDF 预览（iframe 或 force download） -->
        <div v-if="isPdf && openUrl" class="pdf-preview">
          <iframe :src="openUrl" class="pdf-iframe" />
          <!-- 移动端 PDF 可能无法 iframe，提供下载 -->
          <Button size="small" type="primary" block @click="handleDownload">
            {{ t('aiArtifact.downloadPdf') }}
          </Button>
        </div>

        <!-- 未知文件：下载提示 -->
        <div v-if="isUnknown" class="unknown-preview">
          <IIcon icon="lucide:file" class="unknown-icon" />
          <span class="unknown-text">{{ t('aiArtifact.unknownFileType') }}</span>
          <Button size="small" type="primary" @click="handleDownload">
            {{ t('aiArtifact.downloadFile') }}
          </Button>
        </div>
      </div>

      <!-- 底部 safe area -->
      <div class="safe-area-bottom" />
    </div>
  </Popup>
</template>

<style scoped>
.artifact-preview-popup {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

/* Truncate long NavBar title so right-side action buttons stay visible */
.artifact-preview-popup :deep(.van-nav-bar__title) {
  max-width: 50vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-actions {
  display: flex;
  gap: 8px;
}

.view-mode-tabs {
  display: flex;
  padding: 0 16px;
  background: var(--card-bg);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.view-mode-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 16px;
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
}

.view-mode-tab.active {
  color: var(--van-primary-color);
  border-bottom-color: var(--van-primary-color);
  font-weight: 500;
}

.tab-icon {
  width: 16px;
  height: 16px;
}

.preview-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.loading-state,
.error-state,
.unknown-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 32px;
  color: var(--text-secondary);
}

.code-preview {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 12px;
  overflow-x: auto;
}

.markdown-preview {
  color: var(--text-primary);
}

.html-preview,
.pdf-preview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.html-iframe,
.pdf-iframe {
  width: 100%;
  min-height: 60vh;
  border: none;
  border-radius: 12px;
  background: white;
  transition: height 0.15s ease;
}

.image-preview {
  display: flex;
  justify-content: center;
}

.preview-image {
  max-width: 100%;
  max-height: 80vh;
  border-radius: 12px;
}

.unknown-icon {
  width: 48px;
  height: 48px;
  color: var(--text-secondary);
}

.unknown-text {
  font-size: 14px;
}

.safe-area-bottom {
  height: env(safe-area-inset-bottom);
}

/* 375px */
@media (max-width: 375px) {
  .preview-content {
    padding: 12px;
  }

  .nav-actions {
    gap: 4px;
  }
}
</style>