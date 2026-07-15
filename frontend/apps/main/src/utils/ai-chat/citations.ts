/**
 * Citation extraction utilities
 *
 * Reference: DeerFlow frontend/src/core/citations/sources.ts
 *
 * Extracts [citation: title](url) patterns from markdown and groups them
 * by URL for the sources summary panel.
 */

export interface CitationOccurrence {
  index: number
  title: string
}

export interface CitationSource {
  id: string
  title: string
  url: string
  domain: string
  count: number
  occurrences: CitationOccurrence[]
}

// Non-consuming lookbehind (?<!!) skips image links (![citation:...])
// URL sub-pattern handles balanced parentheses in URLs like /Foo_(a)_(b)
const CITATION_LINK_RE =
  /(?<!!)\[citation:\s*([^\]]+?)\]\((https?:\/\/(?:[^\s()]|\([^\s()]*\))+)\)/gi

const GENERIC_CITATION_TITLES = new Set(['source', '来源'])

/**
 * Extract citation sources from markdown content.
 * Groups by URL, counts occurrences.
 */
export function extractCitationSources(markdown: string): CitationSource[] {
  if (!markdown) return []

  const searchable = maskCode(markdown)
  const sourcesByUrl = new Map<string, CitationSource>()

  for (const match of searchable.matchAll(CITATION_LINK_RE)) {
    const rawTitle = (match[1] ?? '').trim()
    const rawUrl = match[2] ?? ''
    const url = normalizeUrl(rawUrl)
    if (!url) continue

    const domain = extractDomain(url)
    const title = normalizeTitle(rawTitle, domain)
    const index = match.index ?? 0
    const existing = sourcesByUrl.get(url)

    if (existing) {
      existing.count += 1
      existing.occurrences.push({ index, title })
      continue
    }

    sourcesByUrl.set(url, {
      id: url,
      title,
      url,
      domain,
      count: 1,
      occurrences: [{ index, title }],
    })
  }

  return Array.from(sourcesByUrl.values())
}

export function formatCitationMarkdownReference(source: CitationSource): string {
  return `[${source.title}](${source.url})`
}

function normalizeTitle(title: string, domain: string): string {
  const compact = title.replace(/\s+/g, ' ').trim()
  if (!compact || GENERIC_CITATION_TITLES.has(compact.toLowerCase())) {
    return domain
  }
  return compact
}

function normalizeUrl(value: string): string | null {
  try {
    const url = new URL(value)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null
    return url.href
  } catch {
    return null
  }
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./i, '')
  } catch {
    return url
  }
}

// Blank out code regions so example citations inside code aren't scraped
function maskCode(markdown: string): string {
  return maskInlineCode(maskFencedCodeBlocks(markdown))
}

function maskFencedCodeBlocks(markdown: string): string {
  return markdown.replace(
    /(^|\n)(`{3,}|~{3,})[^\n]*(?:\n[\s\S]*?\n\2[^\n]*(?=\n|$)|[\s\S]*$)/g,
    maskKeepingNewlines,
  )
}

function maskInlineCode(markdown: string): string {
  return markdown.replace(/(`+)[\s\S]*?\1/g, maskKeepingNewlines)
}

function maskKeepingNewlines(block: string): string {
  return block.replace(/[^\n]/g, ' ')
}
