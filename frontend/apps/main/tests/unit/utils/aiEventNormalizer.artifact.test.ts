import { describe, it, expect } from 'vitest'
import { extractArtifactFromStep } from '@/utils/aiEventNormalizer'
import type { ProcessStep } from '@/types/agent-stream'

describe('extractArtifactFromStep', () => {
  // Helper to create a tool_call step
  function makeToolStep(
    id: string,
    name: string,
    status: 'pending' | 'running' | 'done' | 'error',
    overrides?: Partial<Extract<ProcessStep, { type: 'tool_call' }>>,
  ): ProcessStep {
    return {
      type: 'tool_call',
      id,
      name,
      displayName: name,
      icon: '⚙️',
      args: {},
      status,
      ...overrides,
    }
  }

  describe('exclusion cases', () => {
    it('returns null for reasoning step', () => {
      const step: ProcessStep = {
        type: 'reasoning',
        id: 'reasoning-1',
        content: 'Thinking...',
        status: 'done',
      }
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for subagent step', () => {
      const step: ProcessStep = {
        type: 'subagent',
        id: 'subagent-1',
        taskId: 'task-1',
        status: 'done',
      }
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for artifact step', () => {
      const step: ProcessStep = {
        type: 'artifact',
        id: 'artifact-1',
        title: 'Report',
      }
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for progress step', () => {
      const step: ProcessStep = {
        type: 'progress',
        id: 'progress-1',
        title: 'Working',
        status: 'running',
      }
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for write_todos tool', () => {
      const step = makeToolStep('tool-1', 'write_todos', 'done', {
        resultSummary: 'Todos updated',
      })
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for tool_call with status pending', () => {
      const step = makeToolStep('tool-1', 'web_search', 'pending', {
        resultSummary: 'https://example.com',
      })
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for tool_call with status running', () => {
      const step = makeToolStep('tool-1', 'web_search', 'running', {
        resultSummary: 'https://example.com',
      })
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for tool_call with status error', () => {
      const step = makeToolStep('tool-1', 'web_search', 'error', {
        resultSummary: 'https://example.com',
      })
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null for done tool_call without resultSummary', () => {
      const step = makeToolStep('tool-1', 'web_search', 'done')
      expect(extractArtifactFromStep(step)).toBeNull()
    })
  })

  describe('URL extraction', () => {
    it('extracts link artifact from resultSummary with URL', () => {
      const step = makeToolStep('tool-1', 'web_search', 'done', {
        resultSummary: 'Found result at https://example.com/page',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).not.toBeNull()
      expect(artifact).toMatchObject({
        id: 'artifact-tool-1',
        title: 'web_search',
        url: 'https://example.com/page',
        kind: 'link',
        sourceStepId: 'tool-1',
      })
      expect(artifact?.generatedAt).toBeDefined()
    })

    it('extracts image artifact from resultSummary with image URL (png)', () => {
      const step = makeToolStep('tool-2', 'image_gen', 'done', {
        resultSummary: 'Generated image: https://example.com/image.png',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).not.toBeNull()
      expect(artifact).toMatchObject({
        id: 'artifact-tool-2',
        title: 'image_gen',
        url: 'https://example.com/image.png',
        kind: 'image',
        sourceStepId: 'tool-2',
      })
    })

    it('extracts image artifact from resultSummary with image URL (jpg)', () => {
      const step = makeToolStep('tool-3', 'image_gen', 'done', {
        resultSummary: 'Image saved to https://example.com/photo.jpg',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        kind: 'image',
        url: 'https://example.com/photo.jpg',
      })
    })

    it('extracts image artifact from resultSummary with image URL (jpeg)', () => {
      const step = makeToolStep('tool-4', 'image_gen', 'done', {
        resultSummary: 'Photo at https://example.com/pic.jpeg?size=large',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        kind: 'image',
        url: 'https://example.com/pic.jpeg?size=large',
      })
    })

    it('extracts image artifact from resultSummary with image URL (gif)', () => {
      const step = makeToolStep('tool-5', 'image_gen', 'done', {
        resultSummary: 'Animation: https://example.com/anim.gif',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        kind: 'image',
        url: 'https://example.com/anim.gif',
      })
    })

    it('extracts image artifact from resultSummary with image URL (svg)', () => {
      const step = makeToolStep('tool-6', 'chart_gen', 'done', {
        resultSummary: 'Chart: https://example.com/chart.svg',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        kind: 'image',
        url: 'https://example.com/chart.svg',
      })
    })

    it('extracts first URL when multiple URLs present', () => {
      const step = makeToolStep('tool-7', 'multi_search', 'done', {
        resultSummary: 'Results: https://first.com and https://second.com',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        url: 'https://first.com',
        kind: 'link',
      })
    })

    it('uses displayName for title when available', () => {
      const step = makeToolStep('tool-8', 'web_search', 'done', {
        displayName: 'Web Search',
        resultSummary: 'Found: https://example.com',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        title: 'Web Search',
      })
    })
  })

  describe('file path extraction', () => {
    it('extracts file artifact from resultSummary with .txt path', () => {
      const step = makeToolStep('tool-1', 'file_writer', 'done', {
        resultSummary: 'Saved to /path/to/file.txt',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).not.toBeNull()
      expect(artifact).toMatchObject({
        id: 'artifact-tool-1',
        title: 'file_writer',
        path: '/path/to/file.txt',
        kind: 'file',
        sourceStepId: 'tool-1',
      })
      expect(artifact?.generatedAt).toBeDefined()
    })

    it('extracts file artifact from resultSummary with .csv path', () => {
      const step = makeToolStep('tool-2', 'data_export', 'done', {
        resultSummary: 'Exported to /data/export.csv',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        path: '/data/export.csv',
        kind: 'file',
      })
    })

    it('extracts file artifact from resultSummary with .json path', () => {
      const step = makeToolStep('tool-3', 'json_export', 'done', {
        resultSummary: 'Output: /tmp/result.json',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        path: '/tmp/result.json',
        kind: 'file',
      })
    })

    it('extracts file artifact from resultSummary with .md path', () => {
      const step = makeToolStep('tool-4', 'markdown_gen', 'done', {
        resultSummary: 'Generated /docs/report.md',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        path: '/docs/report.md',
        kind: 'file',
      })
    })

    it('extracts file artifact from resultSummary with .pdf path', () => {
      const step = makeToolStep('tool-5', 'pdf_gen', 'done', {
        resultSummary: 'PDF saved: /files/document.pdf',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        path: '/files/document.pdf',
        kind: 'file',
      })
    })

    it('extracts file artifact from resultSummary with .xlsx path', () => {
      const step = makeToolStep('tool-6', 'excel_gen', 'done', {
        resultSummary: 'Spreadsheet: /data/table.xlsx',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        path: '/data/table.xlsx',
        kind: 'file',
      })
    })

    it('extracts file artifact from resultSummary with .docx path', () => {
      const step = makeToolStep('tool-7', 'doc_gen', 'done', {
        resultSummary: 'Document at /files/report.docx',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        path: '/files/report.docx',
        kind: 'file',
      })
    })
  })

  describe('data extraction', () => {
    it('extracts data artifact when step.data is object', () => {
      const step = makeToolStep('tool-1', 'data_processor', 'done', {
        resultSummary: 'Processed data',
        data: { rows: 100, columns: 5 },
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).not.toBeNull()
      expect(artifact).toMatchObject({
        id: 'artifact-tool-1',
        title: 'data_processor',
        kind: 'data',
        sourceStepId: 'tool-1',
      })
      expect(artifact?.generatedAt).toBeDefined()
    })

    it('extracts data artifact when step.data is array', () => {
      const step = makeToolStep('tool-2', 'list_gen', 'done', {
        resultSummary: 'Generated list',
        data: [1, 2, 3, 4, 5],
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        kind: 'data',
      })
    })

    it('returns null when step.data is primitive (not object)', () => {
      const step = makeToolStep('tool-3', 'calculator', 'done', {
        resultSummary: 'Result: 42',
        data: 42,
      })
      expect(extractArtifactFromStep(step)).toBeNull()
    })

    it('returns null when step.data is string', () => {
      const step = makeToolStep('tool-4', 'text_gen', 'done', {
        resultSummary: 'Generated text',
        data: 'some text',
      })
      expect(extractArtifactFromStep(step)).toBeNull()
    })
  })

  describe('priority and fallback', () => {
    it('prioritizes URL extraction over data', () => {
      const step = makeToolStep('tool-1', 'api_call', 'done', {
        resultSummary: 'Result: https://example.com/api',
        data: { status: 'ok' },
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        kind: 'link',
        url: 'https://example.com/api',
      })
    })

    it('prioritizes URL extraction over file path', () => {
      const step = makeToolStep('tool-2', 'mixed', 'done', {
        resultSummary: 'Saved to https://example.com/file.txt and /local/file.txt',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact).toMatchObject({
        kind: 'link', // URL takes priority
        url: 'https://example.com/file.txt',
      })
    })
  })

  describe('generatedAt timestamp', () => {
    it('generates valid ISO timestamp', () => {
      const step = makeToolStep('tool-1', 'web_search', 'done', {
        resultSummary: 'https://example.com',
      })
      const artifact = extractArtifactFromStep(step)
      expect(artifact?.generatedAt).toBeDefined()

      // Should be valid ISO string
      const date = new Date(artifact!.generatedAt!)
      expect(date.toISOString()).toBe(artifact!.generatedAt)
    })
  })

  describe('duplicate prevention', () => {
    it('same step.id produces same artifact.id', () => {
      const step1 = makeToolStep('tool-1', 'web_search', 'done', {
        resultSummary: 'https://example.com',
      })
      const step2 = makeToolStep('tool-1', 'web_search', 'done', {
        resultSummary: 'https://example.com',
      })

      const artifact1 = extractArtifactFromStep(step1)
      const artifact2 = extractArtifactFromStep(step2)

      expect(artifact1?.id).toBe(artifact2?.id)
    })

    it('different step.id produces different artifact.id', () => {
      const step1 = makeToolStep('tool-1', 'web_search', 'done', {
        resultSummary: 'https://example.com',
      })
      const step2 = makeToolStep('tool-2', 'web_search', 'done', {
        resultSummary: 'https://example.com',
      })

      const artifact1 = extractArtifactFromStep(step1)
      const artifact2 = extractArtifactFromStep(step2)

      expect(artifact1?.id).not.toBe(artifact2?.id)
    })
  })
})