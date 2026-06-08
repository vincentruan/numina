import { describe, it, expect } from 'vitest'
import { filterAIContent } from '@/utils/contentFilter'

describe('filterAIContent', () => {
  it('removes system_instructions XML tags', () => {
    const input = '这是回答开头<system_instructions>内部指令内容</system_instructions>这是正常内容'
    const output = filterAIContent(input)
    expect(output).not.toContain('<system_instructions>')
    expect(output).not.toContain('内部指令内容')
    expect(output).toContain('这是回答开头')
    expect(output).toContain('这是正常内容')
  })

  it('removes user_question XML tags', () => {
    const input = '<user_question>用户原始问题</user_question>这是AI回答'
    const output = filterAIContent(input)
    expect(output).not.toContain('<user_question>')
    expect(output).not.toContain('用户原始问题')
    expect(output).toBe('这是AI回答')
  })

  it('removes User Context blocks', () => {
    const input = 'User Context: {"family_id": "123"}\n正常回答内容'
    const output = filterAIContent(input)
    expect(output).not.toContain('User Context:')
    expect(output).not.toContain('family_id')
    expect(output).toContain('正常回答内容')
  })

  it('removes "你问的是" repeating patterns', () => {
    const input = '你问的是：我们家净资产是多少？\n根据查询结果...'
    const output = filterAIContent(input)
    expect(output).not.toContain('你问的是')
    expect(output).toContain('根据查询结果')
  })

  it('removes tenantId leakage', () => {
    const input = 'tenantId: 123456\n这是回答内容'
    const output = filterAIContent(input)
    expect(output).not.toContain('tenantId')
    expect(output).toBe('这是回答内容')
  })

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

  it('handles empty input', () => {
    expect(filterAIContent('')).toBe('')
  })

  it('handles input with only forbidden content', () => {
    const input = '<system_instructions>指令</system_instructions>'
    const output = filterAIContent(input)
    expect(output).toBe('')
  })
})