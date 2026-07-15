/**
 * Shiki highlighter singleton.
 *
 * 为什么独立模块 + globalThis 双保险：
 * - 独立模块：所有 import 方共享同一份实例（tree-shaking 友好）。
 * - globalThis 缓存：Vite HMR 重新执行模块时会重置模块级变量，
 *   但 globalThis 上的引用在页面生命周期内持久存在，避免
 *   "N instances have been created" 的告警。
 */

export type ShikiModule = typeof import('shiki')
export type ShikiHighlighter = Awaited<ReturnType<ShikiModule['createHighlighter']>>

const GLOBAL_KEY = '__numina_shiki_highlighter__' as const

declare global {
  // eslint-disable-next-line no-var
  var __numina_shiki_highlighter__: Promise<ShikiHighlighter> | undefined
}

let highlighterPromise: Promise<ShikiHighlighter> | null =
  globalThis[GLOBAL_KEY] ?? null

export function getHighlighter(): Promise<ShikiHighlighter> {
  if (!highlighterPromise) {
    highlighterPromise = import('shiki')
      .then((shiki) =>
        shiki.createHighlighter({
          themes: ['github-dark', 'github-light'],
          langs: [
            'python',
            'javascript',
            'typescript',
            'html',
            'css',
            'json',
            'bash',
            'sql',
          ],
        }),
      )
      .catch((err) => {
        // 失败时清空，下次调用重试
        highlighterPromise = null
        globalThis[GLOBAL_KEY] = undefined
        throw err
      })
    globalThis[GLOBAL_KEY] = highlighterPromise
  }
  return highlighterPromise
}

/**
 * 释放 highlighter 实例（主要用于测试）。
 * 普通页面生命周期内不需要调用。
 */
export function disposeHighlighter(): void {
  if (highlighterPromise) {
    highlighterPromise
      .then((hl) => hl.dispose())
      .catch(() => {
        /* ignore */
      })
    highlighterPromise = null
    globalThis[GLOBAL_KEY] = undefined
  }
}
