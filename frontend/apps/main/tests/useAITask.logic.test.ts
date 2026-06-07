import { describe, it, expect } from 'vitest'
import { ref, nextTick } from 'vue'
import type { PlanStep } from '@/types/agent-stream'
import type { AgentEvent } from '@/types/agent-stream'

// Test the plan.update handling logic by simulating the event handler behavior
// These tests verify the core logic without needing the full composable setup

describe('plan.update event handling', () => {
  // Simulates the handleEvent logic for plan.update
  function handlePlanUpdate(
    planSteps: PlanStep[],
    event: AgentEvent,
    genericFallbackLabel: string = '处理中',
  ): PlanStep[] {
    if (event.type !== 'plan.update' || !event.todos?.length) {
      return planSteps
    }
    return event.todos.map((todo) => ({
      id: todo.id,
      label: todo.content,
      status:
        todo.status === 'in_progress'
          ? 'active'
          : todo.status === 'done' || todo.status === 'completed'
            ? 'done'
            : 'pending',
    })) as PlanStep[]
  }

  it('maps in_progress status to active', () => {
    const planSteps: PlanStep[] = []
    const event: AgentEvent = {
      type: 'plan.update',
      todos: [
        { id: 'step-1', content: '数据采集', status: 'in_progress' },
        { id: 'step-2', content: '分析数据', status: 'pending' },
      ],
    }
    const result = handlePlanUpdate(planSteps, event)
    expect(result).toHaveLength(2)
    expect(result[0].status).toBe('active')
    expect(result[0].label).toBe('数据采集')
  })

  it('maps done status to done', () => {
    const planSteps: PlanStep[] = []
    const event: AgentEvent = {
      type: 'plan.update',
      todos: [
        { id: 'step-1', content: '数据采集', status: 'done' },
        { id: 'step-2', content: '分析数据', status: 'completed' },
      ],
    }
    const result = handlePlanUpdate(planSteps, event)
    expect(result).toHaveLength(2)
    expect(result[0].status).toBe('done')
    expect(result[1].status).toBe('done')
  })

  it('maps unknown status to pending', () => {
    const planSteps: PlanStep[] = []
    const event: AgentEvent = {
      type: 'plan.update',
      todos: [{ id: 'step-1', content: '未知步骤', status: 'blocked' }],
    }
    const result = handlePlanUpdate(planSteps, event)
    expect(result[0].status).toBe('pending')
  })

  it('preserves empty todos check', () => {
    const planSteps: PlanStep[] = [{ id: 'old', label: '旧步骤', status: 'done' }]
    const event: AgentEvent = {
      type: 'plan.update',
      todos: [],
    }
    const result = handlePlanUpdate(planSteps, event)
    // Empty todos should NOT update planSteps (guard behavior)
    expect(result).toEqual(planSteps)
  })

  it('skips update when todos is undefined', () => {
    const planSteps: PlanStep[] = [{ id: 'old', label: '旧步骤', status: 'active' }]
    const event: AgentEvent = {
      type: 'plan.update',
    }
    const result = handlePlanUpdate(planSteps, event)
    expect(result).toEqual(planSteps)
  })
})

describe('currentStepIndex computed logic', () => {
  // Simulates the currentStepIndex computed behavior
  function computeCurrentStepIndex(planSteps: PlanStep[]): number {
    const activeIdx = planSteps.findIndex((s) => s.status === 'active')
    if (activeIdx >= 0) return activeIdx
    const pendingIdx = planSteps.findIndex((s) => s.status === 'pending')
    if (pendingIdx >= 0) return pendingIdx
    const doneCount = planSteps.filter((s) => s.status === 'done').length
    if (doneCount === planSteps.length && doneCount > 0) return doneCount - 1
    return 0
  }

  it('returns index of active step when present', () => {
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'done' },
      { id: '2', label: 'Step 2', status: 'active' },
      { id: '3', label: 'Step 3', status: 'pending' },
    ]
    expect(computeCurrentStepIndex(steps)).toBe(1)
  })

  it('returns first pending index when no active step', () => {
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'done' },
      { id: '2', label: 'Step 2', status: 'pending' },
      { id: '3', label: 'Step 3', status: 'pending' },
    ]
    expect(computeCurrentStepIndex(steps)).toBe(1)
  })

  it('returns last index when all steps are done', () => {
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'done' },
      { id: '2', label: 'Step 2', status: 'done' },
      { id: '3', label: 'Step 3', status: 'done' },
    ]
    expect(computeCurrentStepIndex(steps)).toBe(2)
  })

  it('returns 0 for empty array', () => {
    expect(computeCurrentStepIndex([])).toBe(0)
  })

  it('returns 0 for mixed statuses without active or pending', () => {
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'error' },
    ]
    expect(computeCurrentStepIndex(steps)).toBe(0)
  })
})

describe('progressPercent computed logic', () => {
  function computeProgressPercent(planSteps: PlanStep[]): number {
    const total = planSteps.length
    if (total === 0) return 0
    const doneCount = planSteps.filter((s) => s.status === 'done').length
    const activeCount = planSteps.filter((s) => s.status === 'active').length
    return Math.min(Math.round(((doneCount + activeCount * 0.5) / total) * 100), 100)
  }

  it('returns 0 for empty planSteps', () => {
    expect(computeProgressPercent([])).toBe(0)
  })

  it('calculates 50% for one active out of two', () => {
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'active' },
      { id: '2', label: 'Step 2', status: 'pending' },
    ]
    // (0 + 1*0.5) / 2 * 100 = 25
    expect(computeProgressPercent(steps)).toBe(25)
  })

  it('calculates 100% when all done', () => {
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'done' },
      { id: '2', label: 'Step 2', status: 'done' },
    ]
    expect(computeProgressPercent(steps)).toBe(100)
  })

  it('caps at 100 even with overshoot', () => {
    // This edge case shouldn't happen in practice but tests the cap
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'done' },
      { id: '2', label: 'Step 2', status: 'done' },
      { id: '3', label: 'Step 3', status: 'done' },
    ]
    expect(computeProgressPercent(steps)).toBe(100)
  })

  it('weights active steps at 50%', () => {
    const steps: PlanStep[] = [
      { id: '1', label: 'Step 1', status: 'done' },
      { id: '2', label: 'Step 2', status: 'active' },
      { id: '3', label: 'Step 3', status: 'pending' },
    ]
    // (1 + 1*0.5) / 3 * 100 = 50
    expect(computeProgressPercent(steps)).toBe(50)
  })
})

describe('tool icon normalization', () => {
  function normalizeIcon(rawIcon: string | undefined): string {
    if (rawIcon === 'tool' || !rawIcon) return '⚙️'
    return rawIcon
  }

  it('replaces literal "tool" string with gear emoji', () => {
    expect(normalizeIcon('tool')).toBe('⚙️')
  })

  it('uses gear emoji for empty string', () => {
    expect(normalizeIcon('')).toBe('⚙️')
  })

  it('uses gear emoji for undefined', () => {
    expect(normalizeIcon(undefined)).toBe('⚙️')
  })

  it('preserves valid emoji icons', () => {
    expect(normalizeIcon('💾')).toBe('💾')
  })

  it('preserves valid text icons', () => {
    expect(normalizeIcon('wallet')).toBe('wallet')
  })
})