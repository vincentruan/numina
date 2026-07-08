/**
 * messageGroups.ts unit tests — DeerFlow getMessageGroups() parity
 *
 * 参考: frontend/src/core/messages/utils.ts getMessageGroups()
 */
import { describe, it, expect } from 'vitest'
import {
  getMessageGroups,
  hasToolCalls,
  hasPresentFiles,
  hasSubagent,
  isClarificationToolMessage,
  extractToolCalls,
  findToolCallResult,
  getSubagentCount,
  getSubagentTaskIds,
} from '@/utils/ai-chat/messageGroups'
import type { ChatMessage, AssistantSubagentGroup } from '@/types/ai-chat/message-group'

function human(id: string, content: string): ChatMessage {
  return {
    id,
    type: 'human',
    role: 'user',
    content,
    displayTime: '00:00',
  }
}

function ai(
  id: string,
  overrides: Partial<ChatMessage> = {},
): ChatMessage {
  return {
    id,
    type: 'ai',
    role: 'assistant',
    content: '',
    displayTime: '00:00',
    ...overrides,
  }
}

function tool(id: string, toolCallId: string, content: string, name?: string): ChatMessage {
  return {
    id,
    type: 'tool',
    role: 'assistant',
    content,
    tool_call_id: toolCallId,
    name,
    displayTime: '00:00',
  }
}

describe('getMessageGroups — empty input', () => {
  it('returns empty array for empty messages', () => {
    expect(getMessageGroups([])).toEqual([])
  })
})

describe('getMessageGroups — human messages', () => {
  it('creates a HumanMessageGroup for a single human message', () => {
    const msgs = [human('h1', 'hello')]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('human')
    expect(groups[0].messages).toEqual(msgs)
  })

  it('creates separate HumanMessageGroups for consecutive human messages', () => {
    const msgs = [human('h1', 'q1'), human('h2', 'q2')]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(2)
    expect(groups.every(g => g.type === 'human')).toBe(true)
  })
})

describe('getMessageGroups — assistant message body bubbles', () => {
  it('creates an assistant group for content-only AI message', () => {
    const msgs = [ai('a1', { content: 'hi there' })]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('assistant')
  })

  it('does not create assistant group for empty content', () => {
    const msgs = [ai('a1', { content: '' })]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(0)
  })
})

describe('getMessageGroups — processing groups (tool_calls/reasoning)', () => {
  it('creates assistant:processing group for AI message with tool_calls', () => {
    const msgs = [
      ai('a1', {
        tool_calls: [{ id: 'tc1', name: 'web_search', args: { query: 'foo' } }],
      }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('assistant:processing')
  })

  it('merges consecutive processing AI messages into the same group', () => {
    const msgs = [
      ai('a1', { tool_calls: [{ id: 'tc1', name: 'web_search', args: {} }] }),
      ai('a2', { tool_calls: [{ id: 'tc2', name: 'read_file', args: {} }] }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('assistant:processing')
    expect(groups[0].messages).toHaveLength(2)
  })

  it('merges tool messages into the previous processing group', () => {
    const msgs = [
      ai('a1', { tool_calls: [{ id: 'tc1', name: 'web_search', args: {} }] }),
      tool('t1', 'tc1', 'search results'),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('assistant:processing')
    expect(groups[0].messages).toHaveLength(2)
  })

  it('AI with both tool_calls and content creates processing + assistant body', () => {
    const msgs = [
      ai('a1', {
        content: 'partial body',
        tool_calls: [{ id: 'tc1', name: 'web_search', args: {} }],
      }),
    ]
    const groups = getMessageGroups(msgs)
    // tool_calls → processing group (ChainOfThought); content → assistant body
    // bubble. Both render so the AI's text reply is never silently dropped
    // (the blank-page bug when an AI replies text + ask_clarification).
    expect(groups.map(g => g.type)).toEqual([
      'assistant:processing',
      'assistant',
    ])
    expect(groups[0].messages[0].id).toBe('a1')
    expect(groups[1].messages[0].id).toBe('a1')
  })
})

describe('getMessageGroups — clarification dual group', () => {
  it('creates clarification group AND merges into prior processing group', () => {
    const msgs = [
      ai('a1', {
        tool_calls: [{ id: 'tc1', name: 'ask_clarification', args: {} }],
      }),
      tool('t1', 'tc1', 'need more info', 'ask_clarification'),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups.map(g => g.type)).toEqual([
      'assistant:processing',
      'assistant:clarification',
    ])
    expect(groups[0].messages).toHaveLength(2)
  })
})

describe('getMessageGroups — present-files group', () => {
  it('creates assistant:present-files group for present_files tool', () => {
    const msgs = [
      ai('a1', {
        tool_calls: [
          {
            id: 'tc1',
            name: 'present_files',
            args: { files: [{ id: 'f1', title: 'doc.md', kind: 'markdown' }] },
          },
        ],
      }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('assistant:present-files')
  })
})

describe('getMessageGroups — subagent group', () => {
  it('creates assistant:subagent group for task tool', () => {
    const msgs = [
      ai('a1', {
        tool_calls: [
          { id: 'tc1', name: 'task', args: { description: 'subtask' } },
        ],
      }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].type).toBe('assistant:subagent')
  })

  it('creates subagent group when message has subagent field', () => {
    const msgs = [
      ai('a1', {
        subagent: {
          taskId: 'sa1',
          status: 'in_progress',
        },
      }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups[0].type).toBe('assistant:subagent')
  })
})

describe('getMessageGroups — hidden message filtering', () => {
  it('filters out hide_from_ui messages', () => {
    const msgs = [
      ai('a1', {
        content: 'visible',
      }),
      ai('a2', {
        content: 'hidden',
        additional_kwargs: { hide_from_ui: true },
      }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].messages[0].id).toBe('a1')
  })

  it('filters out HIDDEN_CONTROL_MESSAGE_NAMES', () => {
    const msgs = [
      ai('a1', { content: 'real' }),
      ai('a2', { content: 'control', name: 'summary' }),
      ai('a3', { content: 'control', name: 'loop_warning' }),
      ai('a4', { content: 'control', name: 'todo_reminder' }),
      ai('a5', { content: 'control', name: 'todo_completion_reminder' }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups).toHaveLength(1)
    expect(groups[0].messages[0].id).toBe('a1')
  })
})

describe('getMessageGroups — full flow', () => {
  it('handles human → processing → assistant', () => {
    const msgs = [
      human('h1', 'q'),
      ai('a1', { tool_calls: [{ id: 'tc1', name: 'web_search', args: {} }] }),
      tool('t1', 'tc1', 'results'),
      ai('a2', { content: 'final answer' }),
    ]
    const groups = getMessageGroups(msgs)
    expect(groups.map(g => g.type)).toEqual([
      'human',
      'assistant:processing',
      'assistant',
    ])
  })
})

describe('helper predicates', () => {
  it('hasToolCalls detects tool_calls on AI', () => {
    expect(hasToolCalls(ai('a', { tool_calls: [{ id: '1', name: 'x', args: {} }] }))).toBe(
      true,
    )
    expect(hasToolCalls(ai('a'))).toBe(false)
    expect(hasToolCalls(human('h', 'q'))).toBe(false)
  })

  it('hasPresentFiles detects present_files tool', () => {
    expect(
      hasPresentFiles(ai('a', { tool_calls: [{ id: '1', name: 'present_files', args: {} }] })),
    ).toBe(true)
    expect(hasPresentFiles(ai('a', { tool_calls: [{ id: '1', name: 'web_search', args: {} }] }))).toBe(
      false,
    )
  })

  it('hasSubagent detects task tool or subagent field', () => {
    expect(hasSubagent(ai('a', { tool_calls: [{ id: '1', name: 'task', args: {} }] }))).toBe(true)
    expect(hasSubagent(ai('a', { subagent: { taskId: '1', status: 'in_progress' } }))).toBe(true)
    expect(hasSubagent(ai('a'))).toBe(false)
  })

  it('isClarificationToolMessage detects ask_clarification tool message', () => {
    expect(isClarificationToolMessage(tool('t1', 'tc1', 'res', 'ask_clarification'))).toBe(true)
    expect(isClarificationToolMessage(tool('t1', 'tc1', 'res', 'web_search'))).toBe(false)
  })

  it('extractToolCalls maps tool_calls with defaults', () => {
    const calls = extractToolCalls(
      ai('a', { tool_calls: [{ id: 'tc1', name: 'web_search', args: { q: 'x' } }] }),
    )
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ id: 'tc1', name: 'web_search', status: 'pending' })
  })

  it('findToolCallResult finds matching tool result', () => {
    const msgs = [tool('t1', 'tc1', 'result-1'), tool('t2', 'tc2', 'result-2')]
    expect(findToolCallResult('tc1', msgs)).toBe('result-1')
    expect(findToolCallResult('tc2', msgs)).toBe('result-2')
    expect(findToolCallResult('missing', msgs)).toBeUndefined()
  })

  it('getSubagentCount counts subagent messages', () => {
    const group: AssistantSubagentGroup = {
      type: 'assistant:subagent',
      id: 'g1',
      messages: [
        ai('a1', { subagent: { taskId: 's1', status: 'in_progress' } }),
        ai('a2', { tool_calls: [{ id: 'tc1', name: 'task', args: {} }] }),
        ai('a3'),
      ],
    }
    expect(getSubagentCount(group)).toBe(2)
  })

  it('getSubagentTaskIds collects task ids from subagent + tool_calls', () => {
    const group: AssistantSubagentGroup = {
      type: 'assistant:subagent',
      id: 'g1',
      messages: [
        ai('a1', { subagent: { taskId: 's1', status: 'in_progress' } }),
        ai('a2', { tool_calls: [{ id: 'tc-task-1', name: 'task', args: {} }] }),
      ],
    }
    expect(getSubagentTaskIds(group)).toEqual(['s1', 'tc-task-1'])
  })
})
