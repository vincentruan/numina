import { describe, it, expect } from 'vitest'
import {
  htmlTableToMarkdown,
  htmlTableToCsv,
  escapeCsvField,
} from '@/utils/ai-chat/tableUtils'

describe('tableUtils — U5 table operations', () => {
  describe('htmlTableToMarkdown', () => {
    it('converts a simple HTML table to markdown', () => {
      const html = `
        <table>
          <tr><th>名称</th><th>销量</th></tr>
          <tr><td>BYD</td><td>100万</td></tr>
          <tr><td>Tesla</td><td>50万</td></tr>
        </table>
      `
      const md = htmlTableToMarkdown(html)
      expect(md).toContain('| 名称 | 销量 |')
      expect(md).toContain('| --- | --- |')
      expect(md).toContain('| BYD | 100万 |')
      expect(md).toContain('| Tesla | 50万 |')
    })

    it('returns empty string for no table', () => {
      expect(htmlTableToMarkdown('<div>no table</div>')).toBe('')
    })

    it('normalizes uneven column counts', () => {
      const html = `
        <table>
          <tr><th>A</th><th>B</th><th>C</th></tr>
          <tr><td>1</td></tr>
        </table>
      `
      const md = htmlTableToMarkdown(html)
      const lines = md.split('\n')
      // Second data row should have 3 columns
      expect(lines[2]).toBe('| 1 |  |  |')
    })
  })

  describe('htmlTableToCsv', () => {
    it('converts HTML table to CSV with BOM', () => {
      const html = `
        <table>
          <tr><th>名称</th><th>销量</th></tr>
          <tr><td>BYD</td><td>100</td></tr>
        </table>
      `
      const csv = htmlTableToCsv(html)
      expect(csv.startsWith('﻿')).toBe(true) // UTF-8 BOM
      expect(csv).toContain('名称,销量\r\n')
      expect(csv).toContain('BYD,100')
    })

    it('escapes fields with commas', () => {
      expect(escapeCsvField('hello,world')).toBe('"hello,world"')
    })

    it('escapes fields with quotes', () => {
      expect(escapeCsvField('say "hi"')).toBe('"say ""hi"""')
    })

    it('escapes fields with newlines', () => {
      expect(escapeCsvField('line1\nline2')).toBe('"line1\nline2"')
    })

    it('does not escape simple fields', () => {
      expect(escapeCsvField('simple')).toBe('simple')
      expect(escapeCsvField('123')).toBe('123')
    })

    it('handles CJK characters', () => {
      const html = `<table><tr><td>数鸣</td><td>资产</td></tr></table>`
      const csv = htmlTableToCsv(html)
      expect(csv).toContain('数鸣,资产')
    })

    it('returns empty string for no table', () => {
      expect(htmlTableToCsv('<div></div>')).toBe('')
    })
  })
})
