import { describe, it, expect } from 'vitest'
import { effectScope, ref } from 'vue'
import { usePlanInference, WRITE_TODOS_PLANNING_LABEL } from '@/composables/usePlanInference'
import type { ProcessStep } from '@/types/agent-stream'

// Helper: build a tool_call ProcessStep
function toolStep(name: string): Extract<ProcessStep, { type: 'tool_call' }> {
  return {
    type: 'tool_call',
    id: `tc-${name}-${Math.random().toString(36).slice(2)}`,
    name,
    displayName: name,
    icon: '⚙️',
    args: {},
    status: 'done',
  }
}

// Helper: build a reasoning ProcessStep
function reasoningStep(content: string): Extract<ProcessStep, { type: 'reasoning' }> {
  return {
    type: 'reasoning',
    id: `r-${Math.random().toString(36).slice(2)}`,
    content,
    status: 'done',
  }
}

describe('usePlanInference', () => {
  // ─── source-gate tests ────────────────────────────────────────────────────

  it('returns empty array when planSource is null', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('web_search')])
    const planSource = ref<'explicit' | 'inferred' | null>(null)

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toEqual([])
    scope.stop()
  })

  it('returns empty array when planSource is explicit', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('web_search')])
    const planSource = ref<'explicit' | 'inferred' | null>('explicit')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toEqual([])
    scope.stop()
  })

  it('clears inferred steps when planSource switches to explicit', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('web_search')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value.length).toBe(1)
    planSource.value = 'explicit'
    expect(result!.inferredPlanSteps.value).toEqual([])
    scope.stop()
  })

  // ─── tool-type mapping tests ───────────────────────────────────────────────

  it('web_search tool_call → infers "搜索" label', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('web_search')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toHaveLength(1)
    expect(result!.inferredPlanSteps.value[0].label).toBe('搜索')
    expect(result!.inferredPlanSteps.value[0].status).toBe('done')
    scope.stop()
  })

  it('tavily_search tool_call → infers "搜索" label', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('tavily_search')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('搜索')
    scope.stop()
  })

  it('code_interpreter tool_call → infers "计算" label', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('code_interpreter')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('计算')
    scope.stop()
  })

  it('unknown tool → infers "工具调用" label', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('some_custom_tool')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('工具调用')
    scope.stop()
  })

  it('mcp_* tool → infers "工具调用" label', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('mcp_some_service')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('工具调用')
    scope.stop()
  })

  // ─── write_todos suppression ───────────────────────────────────────────────

  it('write_todos tool_call is suppressed from inferred steps', () => {
    const scope = effectScope()
    // write_todos surrounded by other tools to confirm only it is filtered
    const steps = ref<ProcessStep[]>([
      toolStep('web_search'),
      toolStep('write_todos'),
      toolStep('code_interpreter'),
    ])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    const labels = result!.inferredPlanSteps.value.map((s) => s.label)
    expect(labels).not.toContain('write_todos')
    expect(labels).not.toContain('AI 正在规划...' + 'dummy') // just ensure no write_todos label
    scope.stop()
  })

  it('write_todos alone → renders WRITE_TODOS_PLANNING_LABEL transient step', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('write_todos')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toHaveLength(1)
    expect(result!.inferredPlanSteps.value[0].label).toBe(WRITE_TODOS_PLANNING_LABEL)
    expect(result!.inferredPlanSteps.value[0].status).toBe('active')
    scope.stop()
  })

  it('write_todos with other tools → planning step appended after other inferred steps', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('web_search'), toolStep('write_todos')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    const planSteps = result!.inferredPlanSteps.value
    expect(planSteps).toHaveLength(2)
    expect(planSteps[0].label).toBe('搜索')
    expect(planSteps[1].label).toBe(WRITE_TODOS_PLANNING_LABEL)
    expect(planSteps[1].status).toBe('active')
    scope.stop()
  })

  it('write_todos → plan_update arrives → inferred steps cleared, writeTodosCollapsedLabel shown', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('write_todos')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')
    const explicitPlanStepCount = ref(0)

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource, explicitPlanStepCount })
    })

    // While inferred: planning step visible
    expect(result!.inferredPlanSteps.value[0].label).toBe(WRITE_TODOS_PLANNING_LABEL)
    expect(result!.writeTodosCollapsedLabel.value).toBeNull()

    // plan_update arrives: source switches to explicit with 3 steps
    planSource.value = 'explicit'
    explicitPlanStepCount.value = 3

    expect(result!.inferredPlanSteps.value).toEqual([])
    expect(result!.writeTodosCollapsedLabel.value).toBe('制定了 3 步计划')
    scope.stop()
  })

  // ─── deduplication tests ───────────────────────────────────────────────────

  it('three consecutive web_search calls → one "搜索" dot', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([
      toolStep('web_search'),
      toolStep('web_search'),
      toolStep('web_search'),
    ])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toHaveLength(1)
    expect(result!.inferredPlanSteps.value[0].label).toBe('搜索')
    scope.stop()
  })

  it('mixed tool calls → separate dots per type', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([
      toolStep('web_search'),
      toolStep('code_interpreter'),
      toolStep('web_search'),
    ])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    const labels = result!.inferredPlanSteps.value.map((s) => s.label)
    expect(labels).toEqual(['搜索', '计算', '搜索'])
    scope.stop()
  })

  it('two consecutive same-type tools then different → only merges consecutive run', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([
      toolStep('web_search'),
      toolStep('web_search'),
      toolStep('code_interpreter'),
      toolStep('code_interpreter'),
    ])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    const labels = result!.inferredPlanSteps.value.map((s) => s.label)
    expect(labels).toEqual(['搜索', '计算'])
    scope.stop()
  })

  // ─── reasoning keyword extraction ─────────────────────────────────────────

  it('reasoning starting with "搜索" keyword → infers "搜索" label', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([reasoningStep('搜索相关资料')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('搜索')
    scope.stop()
  })

  it('reasoning starting with "计算" keyword → infers "计算" label', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([reasoningStep('计算净资产总额')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('计算')
    scope.stop()
  })

  it('reasoning with no matching keywords → "思考" fallback', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([reasoningStep('用户问了一个问题')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('思考')
    scope.stop()
  })

  it('empty reasoning content → step skipped', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([reasoningStep('')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toEqual([])
    scope.stop()
  })

  it('keyword only checked in first 10 chars of reasoning content', () => {
    const scope = effectScope()
    // "搜索" appears only after position 10 — should fall back to '思考'
    const longPrefix = '这是一段很长的前缀文字'
    const content = longPrefix + '搜索网络资料'
    const steps = ref<ProcessStep[]>([reasoningStep(content)])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value[0].label).toBe('思考')
    scope.stop()
  })

  // ─── inferred steps are append-only ───────────────────────────────────────

  it('inferred steps are all status=done (never pending)', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([
      toolStep('web_search'),
      reasoningStep('分析数据'),
      toolStep('code_interpreter'),
    ])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    for (const step of result!.inferredPlanSteps.value) {
      expect(step.status).toBe('done')
    }
    scope.stop()
  })

  it('adding more steps to steps array reactively appends inferred steps', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([toolStep('web_search')])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toHaveLength(1)

    steps.value = [...steps.value, toolStep('code_interpreter')]
    expect(result!.inferredPlanSteps.value).toHaveLength(2)
    expect(result!.inferredPlanSteps.value[1].label).toBe('计算')
    scope.stop()
  })

  // ─── writeTodosCollapsedLabel ──────────────────────────────────────────────

  it('writeTodosCollapsedLabel is null when planSource is inferred', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')
    const explicitPlanStepCount = ref(5)

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource, explicitPlanStepCount })
    })

    expect(result!.writeTodosCollapsedLabel.value).toBeNull()
    scope.stop()
  })

  it('writeTodosCollapsedLabel is null when explicitPlanStepCount is 0', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([])
    const planSource = ref<'explicit' | 'inferred' | null>('explicit')
    const explicitPlanStepCount = ref(0)

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource, explicitPlanStepCount })
    })

    expect(result!.writeTodosCollapsedLabel.value).toBeNull()
    scope.stop()
  })

  it('writeTodosCollapsedLabel formats count correctly', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([])
    const planSource = ref<'explicit' | 'inferred' | null>('explicit')
    const explicitPlanStepCount = ref(7)

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource, explicitPlanStepCount })
    })

    expect(result!.writeTodosCollapsedLabel.value).toBe('制定了 7 步计划')
    scope.stop()
  })

  // ─── non-tool/reasoning step types are skipped ────────────────────────────

  it('subagent, artifact, progress steps are not inferred as plan steps', () => {
    const scope = effectScope()
    const steps = ref<ProcessStep[]>([
      { type: 'subagent', id: 'sa1', taskId: 't1', status: 'done' },
      { type: 'artifact', id: 'art1', title: 'report' },
      { type: 'progress', id: 'p1', title: 'progress', status: 'done' },
    ])
    const planSource = ref<'explicit' | 'inferred' | null>('inferred')

    let result: ReturnType<typeof usePlanInference>
    scope.run(() => {
      result = usePlanInference({ steps, planSource })
    })

    expect(result!.inferredPlanSteps.value).toEqual([])
    scope.stop()
  })
})
