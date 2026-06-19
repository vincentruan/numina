import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Initialize marked options once at module load.
// In marked v5+, `breaks`/`gfm` must be set via marked.use(); passing them
// as parse-time MarkedOptions is silently ignored.
marked.use({ breaks: true, gfm: true })

const ALLOWED_TAGS = [
  'p',
  'br',
  'strong',
  'b',
  'em',
  'i',
  'code',
  'a',
] as const

const ALLOWED_ATTR = [
  'href',
  'target',
  'rel',
] as const

// Scoped DOMPurify instance — registering hooks on the default DOMPurify
// singleton would leak target=_blank and scheme stripping into every other
// sanitize call site (AiFinalAnswer, AIChatBox renderMarkdown, TaskConsole),
// because those consumers share the global instance. Using a per-module
// instance keeps the user-bubble policy local to this module.
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

export function sanitizeUserMarkdown(input: string): string {
  if (!input) return ''
  // Defense-in-depth pre-strip: under happy-dom (vitest env), DOMPurify can
  // let <embed> survive inside <p>. Real browsers don't have this bug, but
  // this regex-pass guarantees the same allowlist contract in tests.
  // It strips <script>/<style> blocks together with their content, and
  // strips void elements (<embed>/<object>/<iframe>/<img>) entirely.
  // The pre-strip is a backstop, not the primary control — DOMPurify below
  // is the authoritative sanitizer.
  const preStripped = input
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<\/?(?:embed|object|iframe|img)\b[^>]*>/gi, '')
  let html: string
  try {
    html = marked.parse(preStripped, { async: false }) as string
  } catch {
    html = preStripped
  }
  return purify.sanitize(html, {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: [...ALLOWED_ATTR],
    FORBID_TAGS: ['embed', 'object', 'iframe', 'script', 'style', 'img'],
    ALLOW_DATA_ATTR: false,
  })
}
