import { describe, it, expect } from 'vitest'
import { sanitizeUserMarkdown } from '@/utils/userMarkdownSanitizer'

describe('sanitizeUserMarkdown — allowed inline content', () => {
  it('returns empty string for empty input', () => {
    expect(sanitizeUserMarkdown('')).toBe('')
  })

  it('preserves plain text', () => {
    expect(sanitizeUserMarkdown('hello world')).toContain('hello world')
  })

  it('renders bold, italic, and inline code', () => {
    const out = sanitizeUserMarkdown('**bold** *italic* `code`')
    expect(out).toContain('<strong>bold</strong>')
    expect(out).toMatch(/<em>italic<\/em>/)
    expect(out).toContain('<code>code</code>')
  })

  it('preserves single line break with breaks:true', () => {
    const out = sanitizeUserMarkdown('line one\nline two')
    expect(out).toContain('<br')
  })

  it('renders autolinks with target=_blank rel=noopener noreferrer', () => {
    const out = sanitizeUserMarkdown('see https://example.com')
    expect(out).toContain('href="https://example.com"')
    expect(out).toContain('target="_blank"')
    expect(out).toContain('rel="noopener noreferrer"')
  })
})

describe('sanitizeUserMarkdown — XSS allowlist enforcement', () => {
  it('strips <script> tags', () => {
    const out = sanitizeUserMarkdown('<script>alert(1)</script>')
    expect(out).not.toContain('<script')
    expect(out).not.toContain('alert(1)')
  })

  it('strips <iframe>', () => {
    const out = sanitizeUserMarkdown('<iframe src="https://evil.example"></iframe>')
    expect(out).not.toContain('<iframe')
  })

  it('strips <img> with onerror', () => {
    const out = sanitizeUserMarkdown('<img src=x onerror=alert(1)>')
    expect(out).not.toContain('<img')
    expect(out).not.toContain('onerror')
  })

  it('strips inline event handlers', () => {
    const out = sanitizeUserMarkdown('<a href="https://example.com" onclick="alert(1)">x</a>')
    expect(out).not.toContain('onclick')
  })

  it('strips javascript: URL in markdown link', () => {
    const out = sanitizeUserMarkdown('[xss](javascript:alert(1))')
    expect(out).not.toContain('javascript:')
  })

  it('strips data: URL in markdown link', () => {
    const out = sanitizeUserMarkdown('[xss](data:text/html,<script>alert(1)</script>)')
    expect(out).not.toContain('data:')
  })

  it('strips vbscript: URL', () => {
    const out = sanitizeUserMarkdown('<a href="vbscript:msgbox(1)">click</a>')
    expect(out).not.toContain('vbscript:')
  })

  it('strips <style> blocks', () => {
    const out = sanitizeUserMarkdown('<style>body{display:none}</style>hi')
    expect(out).not.toContain('<style')
  })

  it('strips <object> and <embed>', () => {
    const out = sanitizeUserMarkdown('<object data="evil.swf"></object><embed src="evil.swf">')
    expect(out).not.toContain('<object')
    expect(out).not.toContain('<embed')
  })

  it('strips block-level Markdown to plain or empty', () => {
    const headingOut = sanitizeUserMarkdown('# Heading')
    expect(headingOut).not.toContain('<h1')
    expect(headingOut).not.toContain('<h2')

    const codeBlockOut = sanitizeUserMarkdown('```\ncode block\n```')
    expect(codeBlockOut).not.toContain('<pre')

    const tableOut = sanitizeUserMarkdown('| a | b |\n|---|---|\n| 1 | 2 |')
    expect(tableOut).not.toContain('<table')

    const blockquoteOut = sanitizeUserMarkdown('> quoted')
    expect(blockquoteOut).not.toContain('<blockquote')

    const hrOut = sanitizeUserMarkdown('---')
    expect(hrOut).not.toContain('<hr')
  })
})

describe('sanitizeUserMarkdown — edge cases', () => {
  it('strips uppercase/mixed-case <SCRIPT> tags', () => {
    const out = sanitizeUserMarkdown('<SCRIPT>alert(1)</SCRIPT>')
    expect(out.toLowerCase()).not.toContain('<script')
    expect(out).not.toContain('alert(1)')
  })

  it('strips <script> with attribute payload', () => {
    const out = sanitizeUserMarkdown('<script src="//evil.example/x.js"></script>')
    expect(out).not.toContain('<script')
    expect(out).not.toContain('evil.example')
  })

  it('strips javascript: with whitespace and case variation in href', () => {
    const out = sanitizeUserMarkdown('<a href="  JaVaScRiPt:alert(1)">x</a>')
    expect(out.toLowerCase()).not.toContain('javascript:')
  })

  it('keeps inline strong nested in code-text without leaking HTML', () => {
    const out = sanitizeUserMarkdown('`<b>not bold</b>` and **bold**')
    expect(out).toContain('&lt;b&gt;not bold&lt;/b&gt;')
    expect(out).toContain('<strong>bold</strong>')
  })

  it('does not double-escape ampersands in plain text', () => {
    const out = sanitizeUserMarkdown('Tom & Jerry')
    expect(out).toContain('Tom &amp; Jerry')
    expect(out).not.toContain('&amp;amp;')
  })
})
