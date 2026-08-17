/**
 * Shared markdown sanitization config for LLM-generated HTML.
 *
 * Used by AIReportPage (indicator narratives, full report markdown) and
 * DashboardNarrativeCard (monthly insight narrative). Both consume
 * markdown rendered by `marked` and need to allow standard HTML tags
 * (headings, lists, emphasis, tables, links, code blocks, etc.) while
 * stripping scripts, event handlers, and data attributes.
 *
 * S1 fix: single source of truth so the two consumers stay in sync.
 */
import DOMPurify from 'dompurify'

/**
 * Permissive markdown-sanitize config. Allows standard HTML produced by
 * `marked` (headings, lists, tables, code, links, emphasis) while blocking
 * XSS vectors.
 *
 * `USE_PROFILES: { html: true }` enables the DOMPurify built-in HTML profile
 * (standard tags + attributes). `ALLOW_DATA_ATTR: false` strips data-* attrs
 * (not needed for rendered markdown, and they can leak metadata).
 */
export const MARKDOWN_PURIFY_CONFIG = {
  USE_PROFILES: { html: true },
  ALLOW_DATA_ATTR: false,
} as const

/**
 * Sanitize a markdown string rendered to HTML by `marked`. Returns safe HTML
 * suitable for `v-html` binding.
 *
 * Convenience wrapper so consumers don't need to import DOMPurify + the
 * config separately.
 */
export function sanitizeMarkdown(html: string): string {
  return DOMPurify.sanitize(html, MARKDOWN_PURIFY_CONFIG)
}
