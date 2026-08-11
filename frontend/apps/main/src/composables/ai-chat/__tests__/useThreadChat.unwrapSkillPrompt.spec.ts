import { describe, expect, it } from 'vitest'
import { stripLanguagePrefix, unwrapSkillPrompt } from '../useThreadChat'

describe('unwrapSkillPrompt', () => {
  it('extracts free_text from bare JSON (current format)', () => {
    const json = JSON.stringify({
      family_id: '1828512128389146',
      free_text: '<user_message>\n帮我看看家庭财务近况\n</user_message>',
    })
    expect(unwrapSkillPrompt(json)).toBe('帮我看看家庭财务近况')
  })

  it('extracts free_text from legacy [SKILL:chat] prefixed JSON', () => {
    const json = JSON.stringify({
      family_id: '123',
      free_text: '查看资产负债',
    })
    const content = `[SKILL:chat]\n${json}`
    expect(unwrapSkillPrompt(content)).toBe('查看资产负债')
  })

  it('strips [LANGUAGE REQUIREMENT] prefix from free_text', () => {
    const json = JSON.stringify({
      family_id: '123',
      free_text:
        '[LANGUAGE REQUIREMENT] Output language: English.\n帮我看看家庭财务',
    })
    expect(unwrapSkillPrompt(json)).toBe('帮我看看家庭财务')
  })

  it('strips [语言要求] prefix from free_text', () => {
    const json = JSON.stringify({
      family_id: '123',
      free_text: '[语言要求] 输出语言：中文。\n查看家庭资产',
    })
    expect(unwrapSkillPrompt(json)).toBe('查看家庭资产')
  })

  it('returns empty string for JSON with missing free_text', () => {
    const json = JSON.stringify({ family_id: '123' })
    expect(unwrapSkillPrompt(json)).toBe('')
  })

  it('returns empty string for JSON with empty free_text', () => {
    const json = JSON.stringify({ family_id: '123', free_text: '' })
    expect(unwrapSkillPrompt(json)).toBe('')
  })

  it('returns plain text unchanged (non-JSON content)', () => {
    expect(unwrapSkillPrompt('普通用户消息')).toBe('普通用户消息')
  })

  it('returns empty for legacy [SKILL:] with invalid JSON body', () => {
    expect(unwrapSkillPrompt('[SKILL:chat]\nnot-json')).toBe('')
  })

  it('does not leak family_id in output', () => {
    const json = JSON.stringify({
      family_id: 'secret-family-id',
      free_text: '我的问题',
    })
    const result = unwrapSkillPrompt(json)
    expect(result).not.toContain('secret-family-id')
    expect(result).not.toContain('family_id')
  })

  it('handles full real-world payload', () => {
    const payload = {
      family_id: '1828512128389146',
      free_text:
        '<user_message>\n[LANGUAGE REQUIREMENT] Output language: English.\n帮我看看家庭财务近况，我想快速了解有没有需要关注的变化。\n</user_message>',
    }
    const json = JSON.stringify(payload)
    expect(unwrapSkillPrompt(json)).toBe(
      '帮我看看家庭财务近况，我想快速了解有没有需要关注的变化。',
    )
  })
})

describe('stripLanguagePrefix', () => {
  it('strips English prefix', () => {
    expect(
      stripLanguagePrefix(
        '[LANGUAGE REQUIREMENT] Output language: English.\nhello',
      ),
    ).toBe('hello')
  })

  it('strips Chinese prefix', () => {
    expect(
      stripLanguagePrefix('[语言要求] 输出语言：中文。\n你好'),
    ).toBe('你好')
  })

  it('returns text unchanged when no prefix', () => {
    expect(stripLanguagePrefix('普通消息')).toBe('普通消息')
  })

  it('handles empty string', () => {
    expect(stripLanguagePrefix('')).toBe('')
  })
})
