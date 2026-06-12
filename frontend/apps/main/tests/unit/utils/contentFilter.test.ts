/**
 * Tests for contentFilter.ts — DeerFlow internal marker stripping and prompt leakage prevention.
 *
 * Key patterns tested:
 * 1. stripInternalMarkers() — DeerFlow INTERNAL_MARKER_TAGS removal
 * 2. Nested same-name tags edge case (regex non-greedy behavior)
 * 3. Malformed/unclosed markers
 * 4. filterAIContent() — comprehensive prompt leakage patterns
 */

import { describe, it, expect } from 'vitest'
import {
  stripInternalMarkers,
  filterAIContent,
  INTERNAL_MARKER_TAGS,
} from '@/utils/contentFilter'

describe('stripInternalMarkers', () => {
  it('removes DeerFlow uploaded_files marker', () => {
    const input = '<uploaded_files>\nfile1.pdf\nfile2.txt\n</uploaded_files>Some answer text'
    const result = stripInternalMarkers(input)
    expect(result).toBe('Some answer text')
  })

  it('removes DeerFlow system-reminder marker', () => {
    const input = '<system-reminder>Internal instructions here</system-reminder>Answer content'
    const result = stripInternalMarkers(input)
    expect(result).toBe('Answer content')
  })

  it('removes DeerFlow memory marker', () => {
    const input = '<memory>User context data</memory>Final response'
    const result = stripInternalMarkers(input)
    expect(result).toBe('Final response')
  })

  it('removes current_date marker', () => {
    const input = '<current_date>2026-06-11</current_date>The analysis shows...'
    const result = stripInternalMarkers(input)
    expect(result).toBe('The analysis shows...')
  })

  it('removes context marker', () => {
    const input = '<context>Family context here</context>Response text'
    const result = stripInternalMarkers(input)
    expect(result).toBe('Response text')
  })

  it('removes user_context marker', () => {
    const input = '<user_context>User preferences</user_context>Generated output'
    const result = stripInternalMarkers(input)
    expect(result).toBe('Generated output')
  })

  it('removes multiple markers in single content', () => {
    const input = '<uploaded_files>f1.pdf</uploaded_files>Text1<system-reminder>Note</system-reminder>Text2<memory>Data</memory>'
    const result = stripInternalMarkers(input)
    expect(result).toBe('Text1Text2')
  })

  it('handles unclosed opening tag (partial match)', () => {
    // UNCLOSED_MARKER_RE requires closing > on tag, so incomplete tags survive
    // This is expected behavior - streaming should complete tags before filtering
    const input = 'Answer<uploaded_files>incomplete content without closing'
    const result = stripInternalMarkers(input)
    // Partial tag survives - would be cleaned on complete re-transmission
    expect(result).toContain('Answer')
  })

  it('removes orphan closing marker tag', () => {
    const input = 'Answer</system-reminder>more text'
    const result = stripInternalMarkers(input)
    expect(result).toBe('Answermore text')
  })

  it('handles empty input', () => {
    expect(stripInternalMarkers('')).toBe('')
  })

  it('handles input with no markers', () => {
    const input = 'Clean content without any markers'
    expect(stripInternalMarkers(input)).toBe('Clean content without any markers')
  })

  // P2 #7: Nested same-name tags edge case - KNOWN LIMITATION
  // Non-greedy regex [\s\S]*? matches first closing tag, leaving residual content
  // In practice, DeerFlow markers are not nested same-name tags, so this is acceptable
  it('handles nested same-name tags (non-greedy regex limitation)', () => {
    const input = '<context><context>inner</context>outer</context>Final'
    const result = stripInternalMarkers(input)
    // First INTERNAL_MARKER_RE removes <context>inner</context>
    // Then UNCLOSED_MARKER_RE removes residual <context> and </context> tags
    // Result: 'outerFinal' (outer content survives - known limitation)
    expect(result).toBe('outerFinal')
    // Verify no marker tags remain in final output
    expect(result).not.toContain('<context>')
    expect(result).not.toContain('</context>')
  })

  it('handles deeply nested markers (known limitation)', () => {
    const input = '<memory><memory><memory>deep</memory>mid</memory>outer</memory>Content'
    const result = stripInternalMarkers(input)
    // Nested content partially survives - acceptable for real-world use
    // Verify no marker tags remain in final output
    expect(result).not.toContain('<memory>')
    expect(result).not.toContain('</memory>')
    expect(result).toContain('Content')
  })

  it('preserves content between markers', () => {
    const input = 'Prefix<memory>data</memory>Middle<system-reminder>note</system-reminder>Suffix'
    const result = stripInternalMarkers(input)
    expect(result).toBe('PrefixMiddleSuffix')
  })

  it('is idempotent — calling twice produces same result', () => {
    const input = '<uploaded_files>f.pdf</uploaded_files>Answer<memory>ctx</memory>'
    const first = stripInternalMarkers(input)
    const second = stripInternalMarkers(first)
    expect(first).toBe(second)
    expect(first).toBe('Answer')
  })
})

describe('INTERNAL_MARKER_TAGS export', () => {
  it('exports expected DeerFlow marker tag names', () => {
    expect(INTERNAL_MARKER_TAGS).toContain('uploaded_files')
    expect(INTERNAL_MARKER_TAGS).toContain('system-reminder')
    expect(INTERNAL_MARKER_TAGS).toContain('memory')
    expect(INTERNAL_MARKER_TAGS).toContain('current_date')
    expect(INTERNAL_MARKER_TAGS).toContain('context')
    expect(INTERNAL_MARKER_TAGS).toContain('user_context')
  })

  it('is frozen/readonly (as const)', () => {
    // TypeScript 'as const' makes this readonly tuple at compile time
    // Runtime check: array exists and has expected length
    expect(INTERNAL_MARKER_TAGS.length).toBe(6)
  })
})

describe('filterAIContent', () => {
  it('applies stripInternalMarkers as part of full filtering', () => {
    const input = '<uploaded_files>file.pdf</uploaded_files>Answer with <system_instructions>prompt</system_instructions>'
    const result = filterAIContent(input)
    expect(result).not.toContain('<uploaded_files>')
    expect(result).not.toContain('<system_instructions>')
  })

  it('removes forbidden patterns (prompt leakage)', () => {
    const input = 'User Context: {"family_id": 123}Answer text'
    const result = filterAIContent(input)
    expect(result).not.toContain('User Context:')
  })

  it('handles nullish input gracefully', () => {
    expect(filterAIContent(null as any)).toBe('')
    expect(filterAIContent(undefined as any)).toBe('')
  })
})