<script setup lang="ts">
/**
 * Markdown 渲染组件
 *
 * 功能:
 * - markdown-it 解析 + DOMPurify sanitize
 * - shiki 双主题代码高亮（github-dark / github-light）
 * - 表格操作栏（复制为 markdown / 下载 CSV）
 */
import { ref, watch, onMounted, onUnmounted, shallowRef } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import TableActionBar from './TableActionBar.vue'

const props = defineProps<{
  content: string
  isLoading?: boolean
}>()

// markdown-it 实例
const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

// shiki 高亮器（shallowRef 避免深层响应式开销）
const highlighter = shallowRef<import('shiki').Highlighter | null>(null)
const rendererReady = ref(false)

// 渲染结果
const renderedContent = ref('')

// 表格数据（用于操作栏）
interface TableBlock {
  html: string
  key: string
}
const tables = ref<TableBlock[]>([])

// 异步加载 shiki 高亮器
async function loadHighlighter() {
  if (highlighter.value) return
  try {
    const shiki = await import('shiki')
    const hl = await shiki.createHighlighter({
      themes: ['github-dark', 'github-light'],
      langs: ['python', 'javascript', 'typescript', 'html', 'css', 'json', 'bash', 'sql'],
    })
    highlighter.value = hl
    rendererReady.value = true
    rerender()
  } catch (err) {
    console.error('Failed to load shiki highlighter:', err)
  }
}

// 转换 shiki 高亮的 HTML 为当前主题（双主题模式输出两个 pre，CSS 控制显隐）
function applyDualTheme(codeHtml: string): string {
  // shiki 双主题输出格式：<pre class="shiki shiki-themes github-dark github-light">
  // 由 shiki 自动处理，这里直接返回
  return codeHtml
}

// 使用 shiki 高亮代码块
function highlightCode(code: string, lang: string): string {
  const hl = highlighter.value
  if (!hl) {
    // Fallback: plain code block
    const escaped = md.utils.escapeHtml(code)
    return `<pre class="code-block-fallback"><code>${escaped}</code></pre>`
  }

  const language = lang && hl.getLoadedLanguages().includes(lang) ? lang : 'text'
  try {
    // 双主题模式：同时输出两个主题的样式，由 CSS class 切换
    const html = hl.codeToHtml(code, {
      lang: language,
      themes: { light: 'github-light', dark: 'github-dark' },
    })
    return applyDualTheme(html)
  } catch {
    const escaped = md.utils.escapeHtml(code)
    return `<pre><code>${escaped}</code></pre>`
  }
}

// 配置 markdown-it 代码高亮
md.set({
  highlight: (str: string, lang: string): string => highlightCode(str, lang),
})

// 提取表格 HTML 用于操作栏注入
function extractTablesAndInjectActionBar(html: string): string {
  tables.value = []
  const tableRegex = /<table[^>]*>[\s\S]*?<\/table>/gi
  const matches: TableBlock[] = []
  let match: RegExpExecArray | null
  let idx = 0
  while ((match = tableRegex.exec(html)) !== null) {
    const tableHtml = match[0]
    const key = `table-${idx}-${Date.now()}`
    matches.push({ html: tableHtml, key })
    idx++
  }

  if (matches.length === 0) return html

  tables.value = matches
  return html
}

// 渲染函数
function renderMarkdown(content: string): string {
  if (!content) return ''
  const raw = md.render(content)
  const sanitized = DOMPurify.sanitize(raw, {
    ADD_ATTR: ['class', 'style'],
  })
  return extractTablesAndInjectActionBar(sanitized)
}

function rerender() {
  if (!props.content) {
    renderedContent.value = ''
    return
  }
  renderedContent.value = renderMarkdown(props.content)
}

// 监听内容变化
watch(
  () => props.content,
  () => rerender(),
  { immediate: true }
)

// shiki 加载完成后重新渲染
watch(rendererReady, (ready) => {
  if (ready) rerender()
})

onMounted(() => {
  loadHighlighter()
  rerender()
})

onUnmounted(() => {
  highlighter.value = null
})
</script>

<template>
  <div class="markdown-content">
    <!-- Loading skeleton -->
    <template v-if="isLoading">
      <van-skeleton :row="3" animated />
    </template>

    <!-- 渲染内容 -->
    <!-- eslint-disable vue/no-v-html -- sanitized by DOMPurify -->
    <div class="markdown-body" v-html="renderedContent" />
    <!-- eslint-enable vue/no-v-html -->

    <!-- 表格操作栏（在每个表格上方渲染） -->
    <template v-if="tables.length > 0">
      <div
        v-for="table in tables"
        :key="table.key"
        class="table-action-slot"
      >
        <TableActionBar :table-html="table.html" />
      </div>
    </template>
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
  background: rgba(127, 127, 127, 0.12);
  border-radius: 4px;
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
  font-size: 13px;
}

/* shiki 双主题代码块样式 */
.markdown-body :deep(.shiki) {
  margin: 12px 0;
  border-radius: 8px;
  overflow-x: auto;
  padding: 12px;
}

/* 双主题：默认显示当前主题，另一个隐藏 */
.markdown-body :deep(.shiki.github-dark) {
  display: var(--shiki-dark-display, block);
}

.markdown-body :deep(.shiki.github-light) {
  display: var(--shiki-light-display, block);
}

/* 暗色模式下 */
:global([data-theme='dark']) .markdown-body :deep(.shiki.github-dark) {
  display: block;
}

:global([data-theme='dark']) .markdown-body :deep(.shiki.github-light) {
  display: none;
}

/* 亮色模式下 */
:global([data-theme='light']) .markdown-body :deep(.shiki.github-dark) {
  display: none;
}

:global([data-theme='light']) .markdown-body :deep(.shiki.github-light) {
  display: block;
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
  display: block;
  overflow-x: auto;
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
