import { marked, type MarkedOptions } from 'marked'
import DOMPurify from 'dompurify'

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

const MARKED_OPTIONS: MarkedOptions = {
  async: false,
  breaks: true,
  gfm: true,
}

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
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
  const preStripped = input
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<\/?(?:embed|object|iframe|img)\b[^>]*>/gi, '')
  let html: string
  try {
    html = marked.parse(preStripped, MARKED_OPTIONS) as string
  } catch {
    html = preStripped
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: [...ALLOWED_ATTR],
    FORBID_TAGS: ['embed', 'object', 'iframe', 'script', 'style', 'img'],
    ALLOW_DATA_ATTR: false,
  })
}
