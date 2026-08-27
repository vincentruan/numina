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
import { ref, computed, watch } from 'vue'
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
      // 重置 viewMode
      viewMode.value = isCodeFile(path) ? 'code' : 'preview'
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
  window.open(downloadUrl.value, '_blank')
}

function handleOpenNewWindow() {
  window.open(openUrl.value, '_blank')
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
      <div v-if="isCode" class="view-mode-toggle">
        <Button
          size="small"
          :type="viewMode === 'code' ? 'primary' : 'default'"
          @click="viewMode = 'code'"
        >
          {{ t('aiArtifact.viewModeCode') }}
        </Button>
        <Button
          size="small"
          :type="viewMode === 'preview' ? 'primary' : 'default'"
          @click="viewMode = 'preview'"
        >
          {{ t('aiArtifact.viewModePreview') }}
        </Button>
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
          <IIcon icon="lucide:x-circle" />
          <span>{{ error }}</span>
          <Button size="small" type="primary" @click="loadContent">{{ t('aiArtifact.retry') }}</Button>
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

        <!-- HTML sandbox iframe -->
        <div v-if="!loading && !error && isHtml && contentRef" class="html-preview">
          <iframe :srcdoc="contentRef" sandbox="allow-scripts allow-forms" class="html-iframe" />
        </div>

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

.view-mode-toggle {
  padding: 8px 16px;
  background: var(--card-bg);
  display: flex;
  gap: 8px;
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
  height: 60vh;
  border: none;
  border-radius: 12px;
  background: white;
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