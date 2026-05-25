import { describe, it, expect } from 'vitest'
import {
  createNormalizationState,
  normalizeAgentEvent,
} from '@/utils/aiEventNormalizer'
import type { AgentEvent } from '@/types/agent-stream'

describe('createNormalizationState', () => {
  it('initializes phase to connecting', () => {
    expect(createNormalizationState().phase).toBe('connecting')
  })

  it('initializes empty steps array', () => {
    expect(createNormalizationState().steps).toEqual([])
  })

  it('initializes empty answerContent string', () => {
    expect(createNormalizationState().answerContent).toBe('')
  })

  it('initializes null reasoningStartTime', () => {
    expect(createNormalizationState().reasoningStartTime).toBeNull()
  })

  it('initializes artifacts as empty array', () => {
    expect(createNormalizationState().artifacts).toEqual([])
  })

  it('initializes subagents as empty Map', () => {
    const s = createNormalizationState()
    expect(s.subagents).toBeInstanceOf(Map)
    expect(s.subagents.size).toBe(0)
  })
})

describe('normalizeAgentEvent — phase transitions', () => {
  it('phase.connecting sets phase and emits phase_change', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent({ type: 'phase.connecting' }, state)
    expect(state.phase).toBe('connecting')
    expect(out).toEqual([{ type: 'phase_change', phase: 'connecting' }])
  })

  it('phase.thinking sets reasoningStartTime on first event', () => {
    const state = createNormalizationState()
    const before = Date.now()
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    const after = Date.now()
    expect(state.phase).toBe('thinking')
    expect(state.reasoningStartTime).not.toBeNull()
    expect(state.reasoningStartTime!).toBeGreaterThanOrEqual(before)
    expect(state.reasoningStartTime!).toBeLessThanOrEqual(after)
  })

  it('phase.thinking is idempotent — second event does not reset reasoningStartTime', async () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    const first = state.reasoningStartTime
    await new Promise((r) => setTimeout(r, 5))
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    expect(state.reasoningStartTime).toBe(first)
  })

  it('phase.answering marks tail reasoning step done with elapsedMs', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    normalizeAgentEvent(
      { type: 'token.stream', token: 'reasoning content', is_thinking: true },
      state,
    )
    const out = normalizeAgentEvent({ type: 'phase.answering' }, state)
    const tail = state.steps[state.steps.length - 1]
    expect(tail.type).toBe('reasoning')
    if (tail.type === 'reasoning') {
      expect(tail.status).toBe('done')
      expect(tail.elapsedMs).toBeGreaterThanOrEqual(0)
    }
    expect(out.some((e) => e.type === 'reasoning_done')).toBe(true)
    expect(out.some((e) => e.type === 'phase_change' && e.phase === 'answering')).toBe(true)
  })
})

describe('normalizeAgentEvent — token.stream routing', () => {
  it('thinking token appends to a reasoning step', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    normalizeAgentEvent(
      { type: 'token.stream', token: 'hello', is_thinking: true },
      state,
    )
    expect(state.steps).toHaveLength(1)
    const step = state.steps[0]
    expect(step.type).toBe('reasoning')
    if (step.type === 'reasoning') {
      expect(step.content).toBe('hello')
      expect(step.status).toBe('streaming')
    }
  })

  it('multiple thinking tokens concatenate onto the same reasoning step', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    normalizeAgentEvent({ type: 'token.stream', token: 'a', is_thinking: true }, state)
    normalizeAgentEvent({ type: 'token.stream', token: 'b', is_thinking: true }, state)
    normalizeAgentEvent({ type: 'token.stream', token: 'c', is_thinking: true }, state)
    expect(state.steps).toHaveLength(1)
    const step = state.steps[0]
    if (step.type === 'reasoning') expect(step.content).toBe('abc')
  })

  it('non-thinking token in answering phase appends to answerContent', () => {
    const state = createNormalizationState()
    state.phase = 'answering'
    const out = normalizeAgentEvent({ type: 'token.stream', token: 'final' }, state)
    expect(state.answerContent).toBe('final')
    expect(out).toContainEqual({ type: 'answer_delta', content: 'final' })
  })

  it('non-thinking token in thinking phase still routes to answer_delta (fallback)', () => {
    const state = createNormalizationState()
    state.phase = 'thinking'
    const out = normalizeAgentEvent({ type: 'token.stream', token: 'oops' }, state)
    expect(state.answerContent).toBe('oops')
    expect(out).toContainEqual({ type: 'answer_delta', content: 'oops' })
  })

  it('empty token is dropped', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent(
      { type: 'token.stream', token: '', is_thinking: true },
      state,
    )
    expect(state.steps).toHaveLength(0)
    expect(out).toEqual([])
  })

  it('reasoning followed by tool_call followed by reasoning creates 3 steps in order', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    normalizeAgentEvent({ type: 'token.stream', token: 'r1', is_thinking: true }, state)
    normalizeAgentEvent(
      {
        type: 'tool.call',
        tool: { id: 't1', name: 'tool', display_name: 'tool', icon: '⚙', arguments: {} },
      },
      state,
    )
    normalizeAgentEvent({ type: 'token.stream', token: 'r2', is_thinking: true }, state)
    expect(state.steps).toHaveLength(3)
    expect(state.steps[0].type).toBe('reasoning')
    expect(state.steps[1].type).toBe('tool_call')
    expect(state.steps[2].type).toBe('reasoning')
  })
})

describe('normalizeAgentEvent — tool.call / tool.result', () => {
  it('tool.call appends a tool_call step with status=running', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent(
      {
        type: 'tool.call',
        tool: {
          id: 't1',
          name: 'web_search',
          display_name: '搜索文档',
          icon: '🔍',
          arguments: { query: 'foo' },
        },
      },
      state,
    )
    expect(state.steps).toHaveLength(1)
    const s = state.steps[0]
    expect(s.type).toBe('tool_call')
    if (s.type === 'tool_call') {
      expect(s.status).toBe('running')
      expect(s.args).toEqual({ query: 'foo' })
    }
    expect(out.some((e) => e.type === 'tool_call')).toBe(true)
    expect(out.some((e) => e.type === 'tool_running')).toBe(true)
  })

  it('tool.result updates the matching tool_call to done', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      {
        type: 'tool.call',
        tool: { id: 't1', name: 'x', display_name: 'x', icon: '⚙', arguments: {} },
      },
      state,
    )
    normalizeAgentEvent(
      {
        type: 'tool.result',
        tool_id: 't1',
        result: { success: true, summary: '完成', execution_time_ms: 120 },
      },
      state,
    )
    const s = state.steps[0]
    if (s.type === 'tool_call') {
      expect(s.status).toBe('done')
      expect(s.resultSummary).toBe('完成')
      expect(s.elapsedMs).toBe(120)
    }
  })

  it('tool.result with success=false marks the step as error', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      {
        type: 'tool.call',
        tool: { id: 't1', name: 'x', display_name: 'x', icon: '⚙', arguments: {} },
      },
      state,
    )
    normalizeAgentEvent(
      {
        type: 'tool.result',
        tool_id: 't1',
        result: { success: false, error: '执行失败' },
      },
      state,
    )
    const s = state.steps[0]
    if (s.type === 'tool_call') {
      expect(s.status).toBe('error')
      expect(s.error).toBe('执行失败')
    }
  })

  it('tool.result for an unknown tool_id is silently dropped', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent(
      { type: 'tool.result', tool_id: 'unknown', result: { success: true } },
      state,
    )
    expect(state.steps).toHaveLength(0)
    expect(out).toEqual([])
  })

  it('tool.call with no tool payload is dropped', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent({ type: 'tool.call' }, state)
    expect(state.steps).toHaveLength(0)
    expect(out).toEqual([])
  })
})

describe('normalizeAgentEvent — capability.end / capability.error', () => {
  it('capability.end during answering emits answer_done then phase_change(done) + session_end', () => {
    const state = createNormalizationState()
    state.phase = 'answering'
    const out = normalizeAgentEvent({ type: 'capability.end' }, state)
    expect(state.phase).toBe('done')
    const types = out.map((e) => e.type)
    expect(types).toEqual(['answer_done', 'phase_change', 'session_end'])
  })

  it('capability.end outside answering skips answer_done', () => {
    const state = createNormalizationState()
    state.phase = 'thinking'
    const out = normalizeAgentEvent({ type: 'capability.end' }, state)
    expect(state.phase).toBe('done')
    expect(out.some((e) => e.type === 'answer_done')).toBe(false)
    expect(out.some((e) => e.type === 'phase_change' && e.phase === 'done')).toBe(true)
    expect(out.some((e) => e.type === 'session_end')).toBe(true)
  })

  it('capability.error with nested error object emits error event with message + code', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent(
      { type: 'capability.error', error: { message: 'boom', code: 'E_FOO' } },
      state,
    )
    expect(out).toEqual([{ type: 'error', message: 'boom', code: 'E_FOO' }])
  })

  it('capability.error with flat shape (message+code on root) is supported', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent(
      { type: 'capability.error', message: 'flat error', code: 'E_BAR' },
      state,
    )
    expect(out).toEqual([{ type: 'error', message: 'flat error', code: 'E_BAR' }])
  })

  it('capability.error with no message falls back to "Unknown error"', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent({ type: 'capability.error' }, state)
    expect(out[0]).toMatchObject({ type: 'error', message: 'Unknown error' })
  })
})

describe('normalizeAgentEvent — subagent.update', () => {
  it('inserts a new subagent into state and emits subagent_update', () => {
    const state = createNormalizationState()
    const event: AgentEvent = {
      type: 'subagent.update',
      subagent: { taskId: 't1', status: 'running', title: '子任务 1' },
    }
    const out = normalizeAgentEvent(event, state)
    expect(state.subagents.get('t1')).toEqual({
      taskId: 't1',
      status: 'running',
      title: '子任务 1',
    })
    expect(out).toEqual([
      {
        type: 'subagent_update',
        taskId: 't1',
        status: 'running',
        title: '子任务 1',
        description: undefined,
        result: undefined,
        error: undefined,
      },
    ])
  })

  it('appends a subagent step in arrival order with reasoning/tool_call', () => {
    const state = createNormalizationState()
    normalizeAgentEvent({ type: 'phase.thinking' }, state)
    normalizeAgentEvent({ type: 'token.stream', token: 'r1', is_thinking: true }, state)
    normalizeAgentEvent(
      {
        type: 'tool.call',
        tool: { id: 't1', name: 'x', display_name: 'x', icon: '⚙', arguments: {} },
      },
      state,
    )
    normalizeAgentEvent(
      {
        type: 'subagent.update',
        subagent: { taskId: 'sa1', status: 'running', title: 'Sub' },
      },
      state,
    )
    expect(state.steps.map((s) => s.type)).toEqual(['reasoning', 'tool_call', 'subagent'])
    const sub = state.steps[2]
    if (sub.type === 'subagent') {
      expect(sub.taskId).toBe('sa1')
      expect(sub.title).toBe('Sub')
      expect(sub.status).toBe('running')
    }
  })

  it('partial subagent update merges in place in steps[] (status-only update keeps title)', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      {
        type: 'subagent.update',
        subagent: { taskId: 'sa1', status: 'running', title: '原始', description: '描述' },
      },
      state,
    )
    normalizeAgentEvent(
      { type: 'subagent.update', subagent: { taskId: 'sa1', status: 'done', result: '完成' } },
      state,
    )
    expect(state.steps).toHaveLength(1)
    const step = state.steps[0]
    if (step.type === 'subagent') {
      expect(step).toMatchObject({
        taskId: 'sa1',
        title: '原始',
        description: '描述',
        status: 'done',
        result: '完成',
      })
    }
  })

  it('merges partial updates into existing subagent state', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      {
        type: 'subagent.update',
        subagent: { taskId: 't1', status: 'running', title: '原始标题', description: '描述' },
      },
      state,
    )
    const out = normalizeAgentEvent(
      {
        type: 'subagent.update',
        subagent: { taskId: 't1', status: 'done', result: '完成' },
      },
      state,
    )
    expect(state.subagents.get('t1')).toEqual({
      taskId: 't1',
      status: 'done',
      title: '原始标题',
      description: '描述',
      result: '完成',
    })
    expect(out[0]).toMatchObject({
      type: 'subagent_update',
      taskId: 't1',
      status: 'done',
      title: '原始标题',
      result: '完成',
    })
  })

  it('drops malformed subagent update without taskId', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent(
      { type: 'subagent.update', subagent: { taskId: '', status: 'running' } },
      state,
    )
    expect(state.subagents.size).toBe(0)
    expect(out).toEqual([])
  })
})

describe('normalizeAgentEvent — artifact.created', () => {
  it('appends artifact and emits artifact event', () => {
    const state = createNormalizationState()
    const event: AgentEvent = {
      type: 'artifact.created',
      artifact: { id: 'a1', title: 'Q3 报告', url: 'https://example.com/r.pdf' },
    }
    const out = normalizeAgentEvent(event, state)
    expect(state.artifacts).toEqual([
      { id: 'a1', title: 'Q3 报告', url: 'https://example.com/r.pdf' },
    ])
    expect(out).toEqual([
      {
        type: 'artifact',
        id: 'a1',
        title: 'Q3 报告',
        url: 'https://example.com/r.pdf',
        path: undefined,
      },
    ])
  })

  it('appends an artifact step in steps[] in arrival order', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      {
        type: 'tool.call',
        tool: { id: 't1', name: 'x', display_name: 'x', icon: '⚙', arguments: {} },
      },
      state,
    )
    normalizeAgentEvent(
      { type: 'artifact.created', artifact: { id: 'a1', title: '报告', url: 'https://x' } },
      state,
    )
    expect(state.steps.map((s) => s.type)).toEqual(['tool_call', 'artifact'])
    const art = state.steps[1]
    if (art.type === 'artifact') {
      expect(art.id).toBe('a1')
      expect(art.title).toBe('报告')
      expect(art.url).toBe('https://x')
    }
  })

  it('artifact re-emit replaces in place in steps[]', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      { type: 'artifact.created', artifact: { id: 'a1', title: '初始' } },
      state,
    )
    normalizeAgentEvent(
      { type: 'artifact.created', artifact: { id: 'a1', title: '更新', url: 'https://x' } },
      state,
    )
    expect(state.steps).toHaveLength(1)
    const step = state.steps[0]
    if (step.type === 'artifact') {
      expect(step).toMatchObject({ id: 'a1', title: '更新', url: 'https://x' })
    }
  })

  it('dedupes artifact by id (re-emit replaces in place)', () => {
    const state = createNormalizationState()
    normalizeAgentEvent(
      { type: 'artifact.created', artifact: { id: 'a1', title: '初始' } },
      state,
    )
    normalizeAgentEvent(
      {
        type: 'artifact.created',
        artifact: { id: 'a1', title: '更新', url: 'https://x' },
      },
      state,
    )
    expect(state.artifacts).toHaveLength(1)
    expect(state.artifacts[0]).toEqual({
      id: 'a1',
      title: '更新',
      url: 'https://x',
    })
  })

  it('drops artifact without id', () => {
    const state = createNormalizationState()
    const out = normalizeAgentEvent(
      { type: 'artifact.created', artifact: { id: '', title: 'x' } },
      state,
    )
    expect(state.artifacts).toEqual([])
    expect(out).toEqual([])
  })
})

describe('normalizeAgentEvent — state.snapshot', () => {
  it('replaces artifacts from snapshot and emits state_snapshot', () => {
    const state = createNormalizationState()
    state.artifacts = [{ id: 'old', title: 'stale' }]
    const out = normalizeAgentEvent(
      {
        type: 'state.snapshot',
        artifacts: [{ id: 'fresh1', title: 'A' }, { id: 'fresh2', title: 'B' }],
        title: '历史会话',
      },
      state,
    )
    expect(state.artifacts).toEqual([
      { id: 'fresh1', title: 'A' },
      { id: 'fresh2', title: 'B' },
    ])
    expect(out[0]).toMatchObject({
      type: 'state_snapshot',
      title: '历史会话',
    })
  })

  it('emits state_snapshot even without artifacts', () => {
    const state = createNormalizationState()
    state.artifacts = [{ id: 'kept', title: 'preserved' }]
    const out = normalizeAgentEvent(
      { type: 'state.snapshot', messages: [{ role: 'user' }], title: 't' },
      state,
    )
    expect(state.artifacts).toEqual([{ id: 'kept', title: 'preserved' }])
    expect(out[0]).toMatchObject({ type: 'state_snapshot', title: 't' })
  })
})
