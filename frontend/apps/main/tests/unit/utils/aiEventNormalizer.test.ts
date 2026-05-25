import { describe, it, expect } from 'vitest'
import {
  createNormalizationState,
  normalizeAgentEvent,
} from '@/utils/aiEventNormalizer'
import type { AgentEvent } from '@/types/agent-stream'

describe('createNormalizationState', () => {
  it('initializes artifacts as empty array', () => {
    const s = createNormalizationState()
    expect(s.artifacts).toEqual([])
  })

  it('initializes subagents as empty Map', () => {
    const s = createNormalizationState()
    expect(s.subagents).toBeInstanceOf(Map)
    expect(s.subagents.size).toBe(0)
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
    // No artifacts in snapshot → preserve existing
    expect(state.artifacts).toEqual([{ id: 'kept', title: 'preserved' }])
    expect(out[0]).toMatchObject({ type: 'state_snapshot', title: 't' })
  })
})
