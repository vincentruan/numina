<script setup lang="ts">
/**
 * Markdown 渲染组件
 *
 * 功能:
 * - markdown-it 解析 + DOMPurify sanitize
 * - shiki 双主题代码高亮（github-dark / github-light）
 * - 表格操作栏（复制为 markdown / 下载 CSV）
 *
 * 表格操作栏实现：
 * 直接在 DOM 上创建操作栏按钮元素（不使用 Vue 组件渲染），
 * 避免 v-html re-render 清除 Vue 管理的元素导致 vDOM 追踪断裂。
 * 每次 render 后（nextTick），injectTableActionBars 在每个 table-wrapper
 * 中注入操作栏按钮并绑定事件。v-html 更新时这些元素会被清除，
 * 下次 nextTick 会重新注入。
 */
import { ref, watch, onMounted, onUnmounted, shallowRef, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {
  htmlTableToMarkdown,
  htmlTableToCsv,
  downloadCsv,
  copyToClipboard,
} from '@/utils/ai-chat/tableUtils'
import { showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  content: string
  isLoading?: boolean
}>()

const { t } = useI18n()

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
})

/**
 * Shared singleton shiki highlighter (#11).
 */
type ShikiModule = typeof import('shiki')
type ShikiHighlighter = Awaited<ReturnType<ShikiModule['createHighlighter']>>
let highlighterPromise: Promise<ShikiHighlighter> | null = null
function getHighlighter(): Promise<ShikiHighlighter> {
  if (!highlighterPromise) {
    highlighterPromise = import('shiki').then((shiki) =>
      shiki.createHighlighter({
        themes: ['github-dark', 'github-light'],
        langs: ['python', 'javascript', 'typescript', 'html', 'css', 'json', 'bash', 'sql'],
      }),
    ).catch((err) => {
      highlighterPromise = null
      throw err
    })
  }
  return highlighterPromise
}

const highlighter = shallowRef<ShikiHighlighter | null>(null)
const rendererReady = ref(false)

const renderedContent = ref('')
const rootRef = ref<HTMLElement | null>(null)

interface TableBlock {
  html: string
  key: string
}
const tables = ref<TableBlock[]>([])

let isMounted = false

function hashString(s: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0
  }
  return h.toString(16)
}

async function loadHighlighter() {
  if (highlighter.value) return
  try {
    const hl = await getHighlighter()
    if (!isMounted) return
    highlighter.value = hl
    rendererReady.value = true
    rerender()
  } catch (err) {
    if (isMounted) console.error('Failed to load shiki highlighter:', err)
  }
}

function highlightCode(code: string, lang: string): string {
  const hl = highlighter.value
  if (!hl) {
    const escaped = md.utils.escapeHtml(code)
    return `<pre class="code-block-fallback"><code>${escaped}</code></pre>`
  }

  const language = lang && hl.getLoadedLanguages().includes(lang) ? lang : 'text'
  try {
    return hl.codeToHtml(code, {
      lang: language,
      themes: { light: 'github-light', dark: 'github-dark' },
    })
  } catch {
    const escaped = md.utils.escapeHtml(code)
    return `<pre><code>${escaped}</code></pre>`
  }
}

md.set({
  highlight: (str: string, lang: string): string => highlightCode(str, lang),
})

function extractTablesAndInjectAnchors(html: string): string {
  tables.value = []
  const tableRegex = /<table[^>]*>[\s\S]*?<\/table>/gi
  const matches: TableBlock[] = []
  let result = ''
  let lastIdx = 0
  let match: RegExpExecArray | null
  let idx = 0
  while ((match = tableRegex.exec(html)) !== null) {
    const tableHtml = match[0]
    const key = `table-${idx}-${hashString(tableHtml)}`
    matches.push({ html: tableHtml, key })
    result += html.slice(lastIdx, match.index)
    result += `<div class="table-wrapper" data-table-idx="${idx}">`
    result += tableHtml
    result += `</div>`
    lastIdx = match.index + tableHtml.length
    idx++
  }
  result += html.slice(lastIdx)

  if (matches.length === 0) return html
  tables.value = matches
  return result
}

function renderMarkdown(content: string): string {
  if (!content) return ''
  const raw = md.render(content)
  const sanitized = DOMPurify.sanitize(raw, {
    ADD_ATTR: ['class', 'style'],
  })
  return extractTablesAndInjectAnchors(sanitized)
}

function rerender() {
  if (!props.content) {
    renderedContent.value = ''
    tables.value = []
    return
  }
  renderedContent.value = renderMarkdown(props.content)
  nextTick(injectTableActionBars)
}

// SVG icons for table action bar buttons
const COPY_ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`
const CHECK_ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>`
const DOWNLOAD_ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`

/**
 * 创建表格操作栏 DOM 元素并注入到对应 table-wrapper 中。
 *
 * 不使用 Vue 组件渲染（避免 v-html re-render 清除 Vue 管理的元素导致 vDOM 追踪断裂）。
 * 直接创建原生 DOM 元素并绑定事件，v-html 更新时这些元素会被清除，
 * 下次 nextTick 会重新注入。
 */
function injectTableActionBars() {
  if (!isMounted) return
  const root = rootRef.value
  if (!root) return

  tables.value.forEach((table, idx) => {
    const wrapper = root.querySelector<HTMLElement>(`.table-wrapper[data-table-idx="${idx}"]`)
    if (!wrapper) return
    // Skip if already injected
    if (wrapper.querySelector('.table-action-bar')) return

    const bar = document.createElement('div')
    bar.className = 'table-action-bar'

    // Copy markdown button
    const copyBtn = document.createElement('button')
    copyBtn.className = 'tab-btn'
    copyBtn.type = 'button'
    copyBtn.setAttribute('aria-label', t('aiChat.copyTableAsMarkdown'))
    copyBtn.setAttribute('title', t('aiChat.copyTableAsMarkdown'))
    copyBtn.innerHTML = COPY_ICON
    copyBtn.addEventListener('click', async () => {
      const markdown = htmlTableToMarkdown(table.html)
      const ok = await copyToClipboard(markdown)
      if (ok) {
        copyBtn.innerHTML = CHECK_ICON
        showSuccessToast(t('aiChat.copiedSuccess'))
        setTimeout(() => { copyBtn.innerHTML = COPY_ICON }, 1500)
      }
    })

    // Download CSV button
    const downloadBtn = document.createElement('button')
    downloadBtn.className = 'tab-btn'
    downloadBtn.type = 'button'
    downloadBtn.setAttribute('aria-label', t('aiChat.downloadTable'))
    downloadBtn.setAttribute('title', t('aiChat.downloadTable'))
    downloadBtn.innerHTML = DOWNLOAD_ICON
    downloadBtn.addEventListener('click', () => {
      const csv = htmlTableToCsv(table.html)
      downloadCsv(csv)
      showSuccessToast(t('aiChat.tableDownloaded'))
    })

    bar.appendChild(copyBtn)
    bar.appendChild(downloadBtn)
    wrapper.appendChild(bar)
  })
}

const RENDER_DEBOUNCE_MS = 60
let renderTimer: ReturnType<typeof setTimeout> | null = null

function scheduleRender() {
  if (renderTimer !== null) clearTimeout(renderTimer)
  renderTimer = setTimeout(() => {
    renderTimer = null
    rerender()
  }, RENDER_DEBOUNCE_MS)
}

function flushNow() {
  if (renderTimer !== null) {
    clearTimeout(renderTimer)
    renderTimer = null
  }
  rerender()
}

watch(
  () => props.content,
  () => scheduleRender(),
  { immediate: true }
)

watch(
  () => props.isLoading,
  (loading, prev) => {
    if (prev && !loading) {
      flushNow()
    }
  }
)

watch(rendererReady, (ready) => {
  if (ready) rerender()
})

onMounted(() => {
  isMounted = true
  loadHighlighter()
  rerender()
})

onUnmounted(() => {
  isMounted = false
  if (renderTimer !== null) {
    clearTimeout(renderTimer)
    renderTimer = null
  }
  highlighter.value = null
})
</script>

<template>
  <div ref="rootRef" class="markdown-content">
    <!-- Loading skeleton -->
    <template v-if="isLoading">
      <van-skeleton :row="3" animated />
    </template>

    <!-- 渲染内容（表格锚点 div 在 v-html 内，挂载后由 injectTableActionBars 注入操作栏） -->
    <!-- eslint-disable vue/no-v-html -- sanitized by DOMPurify -->
    <div class="markdown-body" v-html="renderedContent" />
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

.markdown-body :deep(.shiki) {
  margin: 12px 0;
  border-radius: 8px;
  overflow-x: auto;
  padding: 12px;
}

.markdown-body :deep(.shiki.github-dark) {
  display: var(--shiki-dark-display, block);
}

.markdown-body :deep(.shiki.github-light) {
  display: var(--shiki-light-display, block);
}

:global([data-theme='dark']) {
  --shiki-dark-display: block;
  --shiki-light-display: none;
}

:global([data-theme='light']) {
  --shiki-dark-display: none;
  --shiki-light-display: block;
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

.markdown-body :deep(.table-wrapper) {
  position: relative;
  margin: 12px 0;
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

/* Table action bar - injected via DOM (not Vue v-for) to avoid v-html re-render conflicts */
.markdown-body :deep(.table-action-bar) {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
  z-index: 5;
  opacity: 1;
  transition: opacity 0.15s ease;
}

@media (hover: hover) {
  .markdown-body :deep(.table-action-bar) {
    opacity: 0.5;
  }

  :global(.table-wrapper:hover .table-action-bar) {
    opacity: 1;
  }
}

.markdown-body :deep(.tab-btn) {
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

.markdown-body :deep(.tab-btn:hover) {
  color: var(--van-primary-color, #6366f1);
  border-color: var(--van-primary-color, #6366f1);
}

.markdown-body :deep(.tab-btn:active) {
  transform: scale(0.92);
}

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
