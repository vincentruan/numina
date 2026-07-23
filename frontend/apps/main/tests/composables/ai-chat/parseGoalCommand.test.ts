import { describe, it, expect } from 'vitest'
import { parseGoalCommand } from '@/composables/ai-chat/useThreadChat'

describe('parseGoalCommand (U5 /goal three-state branch)', () => {
  it('returns null for non-/goal input', () => {
    expect(parseGoalCommand('hello')).toBeNull()
    expect(parseGoalCommand('/compact')).toBeNull()
    expect(parseGoalCommand('')).toBeNull()
  })

  it('parses /goal with no args as status', () => {
    expect(parseGoalCommand('/goal')).toEqual({ kind: 'status' })
    expect(parseGoalCommand('/goal   ')).toEqual({ kind: 'status' })
  })

  it('parses /goal clear|reset|off as clear (case-insensitive)', () => {
    expect(parseGoalCommand('/goal clear')).toEqual({ kind: 'clear' })
    expect(parseGoalCommand('/goal reset')).toEqual({ kind: 'clear' })
    expect(parseGoalCommand('/goal off')).toEqual({ kind: 'clear' })
    expect(parseGoalCommand('/goal CLEAR')).toEqual({ kind: 'clear' })
    expect(parseGoalCommand('/goal Clear')).toEqual({ kind: 'clear' })
  })

  it('parses /goal <condition> as set with the trimmed objective', () => {
    expect(parseGoalCommand('/goal 分析资产')).toEqual({ kind: 'set', objective: '分析资产' })
    expect(parseGoalCommand('/goal  ship the landing page ')).toEqual({
      kind: 'set',
      objective: 'ship the landing page',
    })
  })

  it('matches case-insensitively on the /goal keyword and trims surrounding whitespace', () => {
    expect(parseGoalCommand('  /GOAL finish the report  ')).toEqual({
      kind: 'set',
      objective: 'finish the report',
    })
    expect(parseGoalCommand('/Goal')).toEqual({ kind: 'status' })
  })
})
