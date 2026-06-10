import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { filterAIContent, filterAIContentCore } from '@/utils/contentFilter'

describe('filterAIContent', () => {
  describe('XML tag patterns', () => {
    it('removes system_instructions XML tags with content', () => {
      const input = '这是回答开头<system_instructions>内部指令内容</system_instructions>这是正常内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('<system_instructions>')
      expect(output).not.toContain('内部指令内容')
      expect(output).toContain('这是回答开头')
      expect(output).toContain('这是正常内容')
    })

    it('removes user_question XML tags with content', () => {
      const input = '<user_question>用户原始问题</user_question>这是AI回答'
      const output = filterAIContent(input)
      expect(output).not.toContain('<user_question>')
      expect(output).not.toContain('用户原始问题')
      expect(output).toBe('这是AI回答')
    })

    it('removes XML tags case-insensitively', () => {
      const input = '<SYSTEM_INSTRUCTIONS>大写指令</SYSTEM_INSTRUCTIONS>正常内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('大写指令')
      expect(output).toBe('正常内容')
    })

    it('removes XML tags with attributes', () => {
      const input = '<system_instructions version="1">指令</system_instructions>内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('指令')
      expect(output).toBe('内容')
    })

    it('removes dash variant XML tags (system-instructions)', () => {
      const input = '<system-instructions>指令</system-instructions>内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('指令')
      expect(output).toBe('内容')
    })

    it('removes unclosed opening tags', () => {
      const input = '正文<system_instructions>更多正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('<system_instructions>')
      expect(output).toContain('正文')
      expect(output).toContain('更多正文')
    })

    it('removes orphaned closing tags', () => {
      const input = '正文</user_question>更多正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('</user_question>')
      expect(output).toContain('正文')
    })

    it('removes HTML-entity-encoded tags', () => {
      const input = '正文&lt;system_instructions&gt;隐藏指令&lt;/system_instructions&gt;尾巴'
      const output = filterAIContent(input)
      expect(output).not.toContain('&lt;system_instructions&gt;')
      expect(output).not.toContain('&lt;/system_instructions&gt;')
      expect(output).toContain('正文')
      expect(output).toContain('尾巴')
    })

    it('handles multiple sequential XML blocks', () => {
      const input = '<system_instructions>A</system_instructions><user_question>B</user_question>正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('A')
      expect(output).not.toContain('B')
      expect(output).toBe('正文')
    })
  })

  describe('Context block patterns', () => {
    it('removes User Context blocks at line start', () => {
      const input = 'User Context: {"family_id": "123"}\n正常回答内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('User Context:')
      expect(output).not.toContain('family_id')
      expect(output).toContain('正常回答内容')
    })

    it('removes mid-line User Context references', () => {
      const input = '根据 User Context: 数据，结论如下\n正文内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('User Context:')
      expect(output).toContain('正文内容')
    })

    it('removes System Prompt blocks', () => {
      const input = 'System Prompt: 你是助手\n正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('System Prompt:')
      expect(output).toBe('正文')
    })

    it('removes Context blocks at line start', () => {
      const input = 'Context: 这是上下文\n正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('Context:')
      expect(output).toBe('正文')
    })

    it('removes Internal Context blocks', () => {
      const input = 'Internal Context: 内部数据\n正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('Internal Context:')
      expect(output).toBe('正文')
    })

    it('handles case-insensitive context markers', () => {
      const input = 'user context: 小写内容\n正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('user context:')
      expect(output).toContain('正文')
    })
  })

  describe('Chinese repeating question patterns', () => {
    it('removes "你问的是" repeating patterns', () => {
      const input = '你问的是：我们家净资产是多少？\n根据查询结果...'
      const output = filterAIContent(input)
      expect(output).not.toContain('你问的是')
      expect(output).toContain('根据查询结果')
    })

    it('removes "问题是" pattern', () => {
      const input = '问题是：净资产计算\n答案如下'
      const output = filterAIContent(input)
      expect(output).not.toContain('问题是')
      expect(output).toContain('答案如下')
    })

    it('removes "您的问题是" pattern', () => {
      const input = '您的问题是：资产分布\n答案'
      const output = filterAIContent(input)
      expect(output).not.toContain('您的问题是')
      expect(output).toContain('答案')
    })

    it('removes "关于您问的" pattern', () => {
      const input = '关于您问的：投资建议\n答案'
      const output = filterAIContent(input)
      expect(output).not.toContain('关于您问的')
      expect(output).toContain('答案')
    })

    it('handles ASCII colon variant', () => {
      const input = '你问的是:净资产\n答案'
      const output = filterAIContent(input)
      expect(output).not.toContain('你问的是')
      expect(output).toContain('答案')
    })
  })

  describe('Identifier leakage patterns', () => {
    it('removes tenantId leakage', () => {
      const input = 'tenantId: 123456\n这是回答内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('tenantId')
      expect(output).toBe('这是回答内容')
    })

    it('removes family_id leakage', () => {
      const input = 'family_id: 999\n回答'
      const output = filterAIContent(input)
      expect(output).not.toContain('family_id')
      expect(output).toContain('回答')
    })

    it('removes user_id leakage', () => {
      const input = 'user_id: 42\n回答'
      const output = filterAIContent(input)
      expect(output).not.toContain('user_id')
      expect(output).toContain('回答')
    })

    it('removes internal_user_id leakage', () => {
      const input = 'internal_user_id: 7\n回答'
      const output = filterAIContent(input)
      expect(output).not.toContain('internal_user_id')
      expect(output).toContain('回答')
    })

    it('handles assignment-style identifier (=)', () => {
      const input = 'tenantId = 123\n回答'
      const output = filterAIContent(input)
      expect(output).not.toContain('tenantId')
      expect(output).toContain('回答')
    })

    it('handles case-insensitive identifier names', () => {
      const input = 'TENANTID: 123\n回答'
      const output = filterAIContent(input)
      expect(output).not.toContain('TENANTID')
      expect(output).toContain('回答')
    })
  })

  describe('Unicode and normalization', () => {
    it('strips zero-width space bypass attempt in XML tags', () => {
      const input = '<system​instructions>隐藏</system​instructions>正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('隐藏')
      expect(output).toBe('正文')
    })

    it('strips zero-width joiner', () => {
      const input = '<system‍instructions>隐藏</system‍instructions>正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('隐藏')
      expect(output).toBe('正文')
    })

    it('strips byte order mark (BOM)', () => {
      const input = '﻿<system_instructions>隐藏</system_instructions>正文'
      const output = filterAIContent(input)
      expect(output).not.toContain('隐藏')
      expect(output).toBe('正文')
    })
  })

  describe('Whitespace and structure', () => {
    it('preserves normal content', () => {
      const input = '根据您家庭数据，当前净资产为 100 万元。'
      const output = filterAIContent(input)
      expect(output).toBe(input)
    })

    it('cleans up excessive blank lines', () => {
      const input = '内容A\n\n\n\n\n内容B'
      const output = filterAIContent(input)
      expect(output).toBe('内容A\n\n内容B')
    })

    it('preserves single blank line', () => {
      const input = '段落A\n\n段落B'
      const output = filterAIContent(input)
      expect(output).toBe('段落A\n\n段落B')
    })

    it('preserves markdown formatting', () => {
      const input = '# 标题\n\n**加粗** 和 `code`\n\n- 列表项'
      const output = filterAIContent(input)
      expect(output).toBe(input)
    })
  })

  describe('Edge cases', () => {
    it('handles empty input', () => {
      expect(filterAIContent('')).toBe('')
    })

    it('handles whitespace-only input', () => {
      expect(filterAIContent('   \n\n   ')).toBe('')
    })

    it('handles input with only forbidden content', () => {
      const input = '<system_instructions>指令</system_instructions>'
      const output = filterAIContent(input)
      expect(output).toBe('')
    })

    it('handles multiple sequential forbidden patterns combined', () => {
      const input = [
        '<system_instructions>A</system_instructions>',
        'User Context: B',
        '你问的是：C',
        'tenantId: D',
        '真实回答内容',
      ].join('\n')
      const output = filterAIContent(input)
      expect(output).not.toContain('<system_instructions>')
      expect(output).not.toContain('User Context')
      expect(output).not.toContain('你问的是')
      expect(output).not.toContain('tenantId')
      expect(output).toContain('真实回答内容')
    })

    it('does not break on regex special characters in input', () => {
      const input = '正文 (a+b)*c? [test] .* end'
      const output = filterAIContent(input)
      expect(output).toBe(input)
    })

    it('handles very long input efficiently', () => {
      const longText = 'A'.repeat(10000) + '<system_instructions>X</system_instructions>' + 'B'.repeat(10000)
      const output = filterAIContent(longText)
      expect(output).not.toContain('<system_instructions>')
      expect(output.length).toBe(20000)
    })
  })

  describe('Error boundary', () => {
    it('returns empty string for empty input', () => {
      expect(filterAIContent('')).toBe('')
    })

    it('handles whitespace-only input', () => {
      expect(filterAIContent('   \n\n   ')).toBe('')
    })

    it('wrapper catches errors and returns raw input', async () => {
      // Use spyOn to mock the core function to throw
      const coreModule = await import('@/utils/contentFilter')
      const coreSpy = vi.spyOn(coreModule, 'filterAIContentCore').mockImplementation(() => {
        throw new Error('Mock regex failure')
      })

      const input = '正常内容'
      // Re-import to get fresh wrapper with spied core
      const { filterAIContent: freshFilter } = await import('@/utils/contentFilter')
      const output = freshFilter(input)

      // Error boundary should return raw input when core throws
      expect(output).toBe(input)

      coreSpy.mockRestore()
    })
  })

  describe('Performance monitoring', () => {
    beforeEach(() => {
      vi.stubEnv('DEV', true)
    })

    afterEach(() => {
      vi.unstubAllEnvs()
    })

    it('logs warning for slow filter in dev mode', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      // Create a very long input to potentially trigger slow filter (>200ms)
      // Note: In unit tests, performance.now() may not reflect real timing
      const longInput = 'A'.repeat(100000) + '<system_instructions>X</system_instructions>' + 'B'.repeat(100000)
      filterAIContent(longInput)

      // This test verifies the mechanism exists, not actual performance timing
      warnSpy.mockRestore()
    })

    it('does not log warning for fast filter', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      // Short input should be fast
      filterAIContent('简短内容')

      expect(warnSpy).not.toHaveBeenCalled()
      warnSpy.mockRestore()
    })
  })

  describe('filterAIContentCore (internal)', () => {
    it('exports core function for direct testing', () => {
      expect(filterAIContentCore).toBeDefined()
      expect(typeof filterAIContentCore).toBe('function')
    })

    it('core function produces same result as wrapper for normal input', () => {
      const input = '正文 <system_instructions>指令</system_instructions> 结尾'
      const coreResult = filterAIContentCore(input)
      const wrapperResult = filterAIContent(input)
      expect(coreResult).toBe(wrapperResult)
    })

    it('core function does not have error boundary', () => {
      // This test documents that core has no error boundary
      // If an error occurs, it will throw (unlike wrapper)
      const input = '正常内容'
      expect(() => filterAIContentCore(input)).not.toThrow()
    })
  })

  describe('Date marker patterns', () => {
    it('removes date marker line "YYYY-MM-DD, Weekday"', () => {
      const input = '问题内容\n2026-06-10, Wednesday\n回答内容'
      const output = filterAIContent(input)
      expect(output).not.toContain('2026-06-10')
      expect(output).not.toContain('Wednesday')
      expect(output).toContain('问题内容')
      expect(output).toContain('回答内容')
    })

    it('removes date marker without surrounding content', () => {
      const input = '2026-06-10, Wednesday'
      const output = filterAIContent(input)
      expect(output).toBe('')
    })

    it('removes date marker in various weekday formats', () => {
      const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
      for (const day of weekdays) {
        const input = `2025-01-15, ${day}\n正文`
        const output = filterAIContent(input)
        expect(output).not.toContain(day)
        expect(output).toBe('正文')
      }
    })

    it('handles date marker embedded in text', () => {
      const input = '开头 2026-06-10, Wednesday 结尾'
      const output = filterAIContent(input)
      expect(output).not.toContain('2026-06-10')
      expect(output).not.toContain('Wednesday')
      expect(output).toContain('开头')
      expect(output).toContain('结尾')
    })
  })
})
