/**
 * Markdown rendering with XSS sanitization for AI-generated content.
 *
 * Pattern: mirrors main app's `userMarkdownSanitizer.ts` — uses `marked` for
 * markdown→HTML conversion and a scoped `DOMPurify` instance for sanitization.
 * The scoped instance prevents hook leakage to other sanitize call sites.
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Configure marked once at module load
marked.use({ breaks: true, gfm: true })

const ALLOWED_TAGS = [
  'p',
  'br',
  'strong',
  'b',
  'em',
  'i',
  'code',
  'pre',
  'a',
  'ul',
  'ol',
  'li',
  'blockquote',
  'h1',
  'h2',
  'h3',
  'h4',
] as const

const ALLOWED_ATTR = [
  'href',
  'target',
  'rel',
] as const

// Scoped DOMPurify instance — prevents hook leakage to other call sites
const purify = DOMPurify(window)

purify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    const href = node.getAttribute('href') ?? ''
    const lower = href.trim().toLowerCase()
    if (
      lower.startsWith('javascript:') ||
      lower.startsWith('data:') ||
      lower.startsWith('vbscript:')
    ) {
      node.removeAttribute('href')
    }
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

/**
 * Render markdown content to sanitized HTML safe for `v-html` binding.
 *
 * @param content - Raw markdown string (typically AI-generated)
 * @returns Sanitized HTML string
 */
export function renderMarkdown(content: string): string {
  if (!content) return ''
  let html: string
  try {
    html = marked.parse(content, { async: false }) as string
  } catch {
    return content
  }
  return purify.sanitize(html, {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: [...ALLOWED_ATTR],
    FORBID_TAGS: ['script', 'style', 'img', 'iframe', 'embed', 'object'],
    ALLOW_DATA_ATTR: false,
  })
}
