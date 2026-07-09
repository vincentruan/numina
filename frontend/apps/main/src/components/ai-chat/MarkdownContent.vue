<script setup lang="ts">
/**
 * Markdown 渲染组件
 *
 * 功能:
 * - markdown-it 解析 + DOMPurify sanitize
 * - shiki 双主题代码高亮（github-dark / github-light）
 * - 表格操作栏（复制为 markdown / 下载 CSV）
 */
import { ref, watch, onMounted, onUnmounted, shallowRef, nextTick } from 'vue'
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

/**
 * Shared singleton shiki highlighter (#11).
 * MarkdownContent mounts once per assistant message; creating a highlighter per
 * instance re-runs the expensive WASM/oniguruma init N times. This module-level
 * promise is shared across all instances — created once, awaited by all.
 * On failure the promise resets so a retry is possible.
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
      // Reset so a later mount can retry instead of being stuck on a rejected promise.
      highlighterPromise = null
      throw err
    })
  }
  return highlighterPromise
}

// Per-instance ref mirroring the shared singleton (read by highlightCode).
const highlighter = shallowRef<ShikiHighlighter | null>(null)
const rendererReady = ref(false)

// 渲染结果
const renderedContent = ref('')

// 组件根元素 ref（避免 document.querySelector 命中其他 MarkdownContent 实例）
const rootRef = ref<HTMLElement | null>(null)

// 表格数据（用于操作栏）—— key 由表格内容哈希派生，渲染期保持稳定。
interface TableBlock {
  html: string
  key: string
}
const tables = ref<TableBlock[]>([])

// Track mounted state so async shiki load doesn't write to stale refs after unmount (#13).
let isMounted = false

// 简单字符串哈希（FNV-1a）用于稳定的 v-for key，避免 Date.now() 每次渲染变化导致重挂载。
function hashString(s: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0
  }
  return h.toString(16)
}

// 异步加载 shiki 高亮器（共享单例）
async function loadHighlighter() {
  if (highlighter.value) return
  try {
    const hl = await getHighlighter()
    // #13: 如果组件在 await 期间卸载，不要写已失效的 ref 或触发 rerender。
    if (!isMounted) return
    highlighter.value = hl
    rendererReady.value = true
    rerender()
  } catch (err) {
    if (isMounted) console.error('Failed to load shiki highlighter:', err)
  }
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
    return hl.codeToHtml(code, {
      lang: language,
      themes: { light: 'github-light', dark: 'github-dark' },
    })
  } catch {
    const escaped = md.utils.escapeHtml(code)
    return `<pre><code>${escaped}</code></pre>`
  }
}

// 配置 markdown-it 代码高亮
md.set({
  highlight: (str: string, lang: string): string => highlightCode(str, lang),
})

// Use .table-wrapper to wrap tables (reference: DeerFlow screenshot with action bar floating top-right).
// Each table is wrapped in a position:relative .table-wrapper,
// after mount TableActionBar (absolute top-right) is moved into the wrapper,
// making icon buttons stick to the table's top-right corner. Use content-based stable key (#10).
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
    // Stable key: table content hash + index, key stays same when content doesn't change.
    const key = `table-${idx}-${hashString(tableHtml)}`
    matches.push({ html: tableHtml, key })
    // Wrap table with .table-wrapper (action bar will be moved into wrapper later)
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

// 渲染函数
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
  // 渲染后把操作栏移动到锚点位置（nextTick 确保 DOM 已更新）。
  nextTick(positionActionBars)
}

/**
 * 将每个 TableActionBar 元素移动到其 .table-wrapper 容器内。
 * wrapper 由 data-table-idx 标记，与 tables 数组索引一一对应。
 * TableActionBar 使用 position:absolute 定位到 wrapper 的右上角。
 *
 * 注意：必须使用组件自身的 rootRef，不能用 document.querySelector('.markdown-content')，
 * 因为页面上可能同时存在多个 MarkdownContent 实例（多轮对话），全局查询会命中
 * 第一个实例（可能没有表格），导致后续实例的表格操作栏无法被移入 wrapper。
 */
function positionActionBars() {
  if (!isMounted) return
  const root = rootRef.value
  if (!root) return
  const wrappers = root.querySelectorAll<HTMLElement>('.table-wrapper')
  const bars = root.querySelectorAll<HTMLElement>('.table-action-bar-wrapper')
  wrappers.forEach((wrapper, idx) => {
    const bar = bars[idx]
    if (!bar) return
    // 将操作栏移入 wrapper（TableActionBar absolute 定位到右上角）
    if (bar.parentElement !== wrapper) {
      wrapper.appendChild(bar)
    } else if (!wrapper.contains(bar)) {
      wrapper.appendChild(bar)
    }
  })
}

// 防抖渲染 (#5)：流式输出时每个 token 都会触发 watch，但全量重解析 md.render
// + DOMPurify + 表格提取是 O(n) 的；不做防抖会导致 O(n²) 的重复解析。
// 用 ~60ms 防抖把多个快速 chunk 合并为一次渲染，并在流结束时强制刷新。
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

// 监听内容变化（防抖）
watch(
  () => props.content,
  () => scheduleRender(),
  { immediate: true }
)

// isLoading 从 true 变 false 表示流结束，强制刷新一次确保最终内容渲染完整。
watch(
  () => props.isLoading,
  (loading, prev) => {
    if (prev && !loading) {
      // 流结束：确保最后一次渲染包含完整内容。
      flushNow()
    }
  }
)

// shiki 加载完成后重新渲染
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
  // 清理防抖计时器，避免卸载后写入失效 ref。
  if (renderTimer !== null) {
    clearTimeout(renderTimer)
    renderTimer = null
  }
  // 不清空共享单例 highlighterPromise（跨实例共享）；
  // 仅清理本实例的 ref 引用。
  highlighter.value = null
})
</script>

<template>
  <div ref="rootRef" class="markdown-content">
    <!-- Loading skeleton -->
    <template v-if="isLoading">
      <van-skeleton :row="3" animated />
    </template>

    <!-- 渲染内容（表格锚点 div 在 v-html 内，挂载后由 positionActionBars 注入操作栏） -->
    <!-- eslint-disable vue/no-v-html -- sanitized by DOMPurify -->
    <div class="markdown-body" v-html="renderedContent" />
    <!-- eslint-enable vue/no-v-html -->

    <!-- 表格操作栏：初始渲染为隐藏源节点，nextTick 后移动到对应锚点 (#6) -->
    <template v-if="tables.length > 0">
      <div
        v-for="(table, idx) in tables"
        :key="table.key"
        class="table-action-bar-wrapper"
        :data-table-idx="idx"
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

/* 暗色/亮色模式下切换 shiki 双主题代码块可见性。
   注意：不能用 :global([data-theme]) .markdown-body :deep(.shiki.xxx) 组合——
   Vue scoped CSS 编译器会丢弃 :global() 之后的 scoped 部分，只留下
   [data-theme='dark'] { display: none; } 这样的全局规则，直接匹配 <html>
   元素并隐藏整个页面（blank page bug）。改用 CSS 变量：在 :global([data-theme])
   上设置变量（仅设变量不会隐藏元素），由上面 scoped 的 .shiki 规则消费。 */
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
  display: block;
  overflow-x: auto;
}

/* DeerFlow 模式：表格包裹容器，为操作栏 absolute 定位提供参照 */
.markdown-body :deep(.table-wrapper) {
  position: relative;
  margin: 12px 0;
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
