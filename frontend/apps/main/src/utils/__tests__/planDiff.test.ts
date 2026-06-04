import { describe, it, expect } from 'vitest'
import { hashTodos, mapTodosToPlanSteps } from '@/utils/planDiff'

describe('hashTodos', () => {
  it('produces the same hash for identical content+status', () => {
    const todos = [
      { id: '1', content: 'Search the web', status: 'completed' },
      { id: '2', content: 'Analyze results', status: 'in_progress' },
    ]
    expect(hashTodos(todos)).toBe(hashTodos(todos))
  })

  it('produces the same hash when id differs but content+status are the same', () => {
    const a = [{ id: 'plan-0', content: 'Search', status: 'pending' }]
    const b = [{ id: 'plan-99', content: 'Search', status: 'pending' }]
    // hash is based on content+status only, not id
    expect(hashTodos(a)).toBe(hashTodos(b))
  })

  it('produces a different hash when status changes', () => {
    const before = [{ id: '1', content: 'Search', status: 'pending' }]
    const after = [{ id: '1', content: 'Search', status: 'completed' }]
    expect(hashTodos(before)).not.toBe(hashTodos(after))
  })

  it('produces a different hash when content changes', () => {
    const before = [{ id: '1', content: 'Search for cats', status: 'pending' }]
    const after = [{ id: '1', content: 'Search for dogs', status: 'pending' }]
    expect(hashTodos(before)).not.toBe(hashTodos(after))
  })

  it('produces a different hash when a todo is added', () => {
    const before = [{ id: '1', content: 'Step 1', status: 'pending' }]
    const after = [
      { id: '1', content: 'Step 1', status: 'pending' },
      { id: '2', content: 'Step 2', status: 'pending' },
    ]
    expect(hashTodos(before)).not.toBe(hashTodos(after))
  })

  it('returns a stable string for empty array', () => {
    expect(hashTodos([])).toBe(hashTodos([]))
  })
})

describe('mapTodosToPlanSteps', () => {
  it('maps pending status to pending', () => {
    const steps = mapTodosToPlanSteps([{ id: 'plan-0', content: 'Do thing', status: 'pending' }])
    expect(steps[0].status).toBe('pending')
  })

  it('maps in_progress status to active', () => {
    const steps = mapTodosToPlanSteps([
      { id: 'plan-0', content: 'Do thing', status: 'in_progress' },
    ])
    expect(steps[0].status).toBe('active')
  })

  it('maps completed status to done', () => {
    const steps = mapTodosToPlanSteps([{ id: 'plan-0', content: 'Do thing', status: 'completed' }])
    expect(steps[0].status).toBe('done')
  })

  it('maps error status to error', () => {
    const steps = mapTodosToPlanSteps([{ id: 'plan-0', content: 'Do thing', status: 'error' }])
    expect(steps[0].status).toBe('error')
  })

  it('maps unknown status to pending as fallback', () => {
    const steps = mapTodosToPlanSteps([{ id: 'plan-0', content: 'Do thing', status: 'unknown' }])
    expect(steps[0].status).toBe('pending')
  })

  it('preserves id and uses content as label', () => {
    const steps = mapTodosToPlanSteps([
      { id: 'plan-2', content: 'Run analysis', status: 'in_progress' },
    ])
    expect(steps[0].id).toBe('plan-2')
    expect(steps[0].label).toBe('Run analysis')
  })

  it('maps a mixed list correctly', () => {
    const todos = [
      { id: 'p0', content: 'Step A', status: 'completed' },
      { id: 'p1', content: 'Step B', status: 'in_progress' },
      { id: 'p2', content: 'Step C', status: 'pending' },
    ]
    const steps = mapTodosToPlanSteps(todos)
    expect(steps).toEqual([
      { id: 'p0', label: 'Step A', status: 'done' },
      { id: 'p1', label: 'Step B', status: 'active' },
      { id: 'p2', label: 'Step C', status: 'pending' },
    ])
  })

  it('returns an empty array for an empty input', () => {
    expect(mapTodosToPlanSteps([])).toEqual([])
  })
})
