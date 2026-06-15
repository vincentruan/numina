<script setup lang="ts">
/**
 * Markdown 渲染组件
 *
 * 功能:
 * - marked 解析 + DOMPurify sanitize
 * - 节流渲染避免长内容卡顿
 * - Loading 状态骨架屏
 */
import { ref, watch, onMounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{
  content: string
  isLoading?: boolean
}>()

// Configure marked
marked.use({ breaks: true })

// 渲染结果
const renderedContent = ref('')

// 节流渲染（长内容分批渲染）
const isRendering = ref(false)

// 内容长度阈值（超过则节流）
const THRESHOLD = 5000

// 渲染函数
function renderMarkdown(content: string): string {
  if (!content) return ''
  return DOMPurify.sanitize(marked.parse(content) as string)
}

// 监听内容变化
watch(
  () => props.content,
  (content) => {
    if (!content) {
      renderedContent.value = ''
      return
    }

    // 短内容直接渲染
    if (content.length < THRESHOLD) {
      renderedContent.value = renderMarkdown(content)
      return
    }

    // 长内容节流渲染
    isRendering.value = true
    // 先渲染前 2000 字符
    const firstChunk = content.slice(0, 2000)
    renderedContent.value = renderMarkdown(firstChunk)

    // 延迟渲染剩余内容
    setTimeout(() => {
      renderedContent.value = renderMarkdown(content)
      isRendering.value = false
    }, 100)
  },
  { immediate: true }
)

onMounted(() => {
  if (props.content && props.content.length < THRESHOLD) {
    renderedContent.value = renderMarkdown(props.content)
  }
})
</script>

<template>
  <div class="markdown-content">
    <!-- Loading skeleton -->
    <template v-if="isLoading">
      <Skeleton :row="3" animated />
    </template>

    <!-- 渲染内容 -->
    <!-- eslint-disable vue/no-v-html -- sanitized by DOMPurify -->
    <div
      v-else
      class="markdown-body"
      :class="{ rendering: isRendering }"
      v-html="renderedContent"
    />
    <!-- eslint-enable vue/no-v-html -->
  </div>
</template>

<style scoped>
.markdown-content {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
}

.markdown-body {
  word-break: break-word;
}

.markdown-body.rendering {
  opacity: 0.7;
}

/* Markdown 元素样式 */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 16px 0 8px;
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-body :deep(h1) {
  font-size: 20px;
}

.markdown-body :deep(h2) {
  font-size: 18px;
}

.markdown-body :deep(h3) {
  font-size: 16px;
}

.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
}

.markdown-body :deep(code) {
  font-family: 'SF Mono', Monaco, 'Courier New', monospace;
  font-size: 13px;
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  padding: 12px;
  background: var(--card-bg);
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
}

.markdown-body :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 3px solid var(--van-primary-color);
  background: rgba(129, 140, 248, 0.08);
  color: var(--text-secondary);
}

.markdown-body :deep(a) {
  color: var(--van-primary-color);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: 12px 0;
  border-collapse: collapse;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--card-bg);
  font-weight: 600;
}

/* Dark mode adjustments */
@media (prefers-color-scheme: dark) {
  .markdown-body :deep(code) {
    background: rgba(255, 255, 255, 0.08);
  }
}

/* 375px */
@media (max-width: 375px) {
  .markdown-content {
    font-size: 14px;
  }

  .markdown-body :deep(h1) {
    font-size: 18px;
  }

  .markdown-body :deep(h2) {
    font-size: 16px;
  }

  .markdown-body :deep(h3) {
    font-size: 15px;
  }

  .markdown-body :deep(code) {
    font-size: 12px;
  }
}
</style>