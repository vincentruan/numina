import { describe, it, expect } from 'vitest'
import {
  getChineseSummary,
  getToolCategory,
  mergeConsecutiveSteps,
  TOOL_SUMMARY_MAP,
} from '@/utils/aiStepSummary'
import type { ProcessStep } from '@/types/agent-stream'

// Helper to create tool_call steps
function createToolCallStep(
  id: string,
  name: string,
  toolType: string,
  displayName?: string,
): ProcessStep {
  return {
    type: 'tool_call',
    id,
    name,
    displayName: displayName || name,
    icon: '🔧',
    toolType,
    args: {},
    status: 'done',
  }
}

// Helper to create reasoning steps
function createReasoningStep(id: string, content: string): ProcessStep {
  return {
    type: 'reasoning',
    id,
    content,
    status: 'done',
  }
}

describe('getChineseSummary', () => {
  it('returns i18n key for known tool names', () => {
    expect(getChineseSummary('get_asset_allocation')).toBe('aiStepSummary.getAssetAllocation')
    expect(getChineseSummary('query_assets')).toBe('aiStepSummary.queryAssets')
    expect(getChineseSummary('generate_report')).toBe('aiStepSummary.generateReport')
  })

  it('returns displayName fallback for unknown tool names', () => {
    expect(getChineseSummary('unknown_tool', 'Custom Tool')).toBe('Custom Tool')
  })

  it('returns raw tool name as final fallback', () => {
    expect(getChineseSummary('unknown_tool')).toBe('unknown_tool')
  })

  it('contains expected tool mappings in TOOL_SUMMARY_MAP', () => {
    expect(TOOL_SUMMARY_MAP['get_asset_allocation']).toBe('aiStepSummary.getAssetAllocation')
    expect(TOOL_SUMMARY_MAP['web_search']).toBe('aiStepSummary.webSearch')
    expect(TOOL_SUMMARY_MAP['write_todos']).toBe('aiStepSummary.writeTodos')
  })
})

describe('getToolCategory', () => {
  it('returns correct category for known tool types', () => {
    expect(getToolCategory('data_query')).toBe('aiStepSummary.categoryDataQuery')
    expect(getToolCategory('calculation')).toBe('aiStepSummary.categoryCalculation')
    expect(getToolCategory('report_gen')).toBe('aiStepSummary.categoryReportGen')
    expect(getToolCategory('web_search')).toBe('aiStepSummary.categoryWebSearch')
  })

  it('returns unknown category for undefined toolType', () => {
    expect(getToolCategory(undefined)).toBe('unknown')
    expect(getToolCategory()).toBe('unknown')
  })

  it('returns unknown category for unknown toolType', () => {
    expect(getToolCategory('custom_type')).toBe('aiStepSummary.categoryUnknown')
  })
})

describe('mergeConsecutiveSteps', () => {
  describe('empty and single inputs', () => {
    it('returns empty array for empty input', () => {
      expect(mergeConsecutiveSteps([])).toEqual([])
    })

    it('returns single tool_call as unmerged item', () => {
      const step = createToolCallStep('t1', 'query_assets', 'data_query')
      const result = mergeConsecutiveSteps([step])

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(false)
      expect(result[0].steps).toEqual([step])
      expect(result[0].displayTextKey).toBe('aiStepSummary.queryAssets')
    })

    it('returns single tool_call with unknown name using fallback', () => {
      const step = createToolCallStep('t1', 'custom_tool', 'data_query', 'Custom Tool')
      const result = mergeConsecutiveSteps([step])

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(false)
      expect(result[0].displayTextKey).toBe('Custom Tool')
    })

    it('returns single reasoning step as unmerged item', () => {
      const step = createReasoningStep('r1', 'Thinking about the problem...')
      const result = mergeConsecutiveSteps([step])

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(false)
      expect(result[0].steps).toEqual([step])
      expect(result[0].displayTextKey).toBe('')
    })
  })

  describe('same-category merging', () => {
    it('merges 3 consecutive same-category tool_calls', () => {
      const steps = [
        createToolCallStep('t1', 'get_assets', 'data_query'),
        createToolCallStep('t2', 'get_liabilities', 'data_query'),
        createToolCallStep('t3', 'get_members', 'data_query'),
      ]
      const result = mergeConsecutiveSteps(steps)

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(true)
      expect(result[0].steps).toEqual(steps)
      expect(result[0].count).toBe(3)
      expect(result[0].category).toBe('data_query')
      expect(result[0].displayTextKey).toBe('aiStepSummary.categoryDataQuery')
    })

    it('does not merge single tool_call with same category', () => {
      const step = createToolCallStep('t1', 'get_assets', 'data_query')
      const result = mergeConsecutiveSteps([step])

      expect(result[0].isMerged).toBe(false)
      expect(result[0].count).toBeUndefined()
    })

    it('merges 2 consecutive same-category tool_calls', () => {
      const steps = [
        createToolCallStep('t1', 'calc_net_worth', 'calculation'),
        createToolCallStep('t2', 'calc_ratio', 'calculation'),
      ]
      const result = mergeConsecutiveSteps(steps)

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(true)
      expect(result[0].count).toBe(2)
    })
  })

  describe('mixed types (tool_call + reasoning)', () => {
    it('passes reasoning through unchanged, merges tool_calls separately', () => {
      const steps: ProcessStep[] = [
        createReasoningStep('r1', 'First thought...'),
        createToolCallStep('t1', 'get_assets', 'data_query'),
        createToolCallStep('t2', 'get_liabilities', 'data_query'),
        createReasoningStep('r2', 'Second thought...'),
      ]
      const result = mergeConsecutiveSteps(steps)

      expect(result).toHaveLength(3)
      // First reasoning
      expect(result[0].isMerged).toBe(false)
      expect(result[0].steps[0].type).toBe('reasoning')
      // Merged tool_calls
      expect(result[1].isMerged).toBe(true)
      expect(result[1].steps).toHaveLength(2)
      expect(result[1].category).toBe('data_query')
      // Second reasoning
      expect(result[2].isMerged).toBe(false)
      expect(result[2].steps[0].type).toBe('reasoning')
    })
  })

  describe('category change mid-sequence', () => {
    it('flushes previous group and starts new group on category change', () => {
      const steps = [
        createToolCallStep('t1', 'get_assets', 'data_query'),
        createToolCallStep('t2', 'get_liabilities', 'data_query'),
        createToolCallStep('t3', 'calc_ratio', 'calculation'),
        createToolCallStep('t4', 'calc_trend', 'calculation'),
      ]
      const result = mergeConsecutiveSteps(steps)

      expect(result).toHaveLength(2)
      // First group (data_query)
      expect(result[0].isMerged).toBe(true)
      expect(result[0].category).toBe('data_query')
      expect(result[0].steps).toHaveLength(2)
      // Second group (calculation)
      expect(result[1].isMerged).toBe(true)
      expect(result[1].category).toBe('calculation')
      expect(result[1].steps).toHaveLength(2)
    })

    it('handles three category changes', () => {
      const steps = [
        createToolCallStep('t1', 'get_assets', 'data_query'),
        createToolCallStep('t2', 'calc_ratio', 'calculation'),
        createToolCallStep('t3', 'gen_report', 'report_gen'),
      ]
      const result = mergeConsecutiveSteps(steps)

      expect(result).toHaveLength(3)
      expect(result[0].category).toBe('data_query')
      expect(result[1].category).toBe('calculation')
      expect(result[2].category).toBe('report_gen')
      // Each is single (not merged)
      expect(result[0].isMerged).toBe(false)
      expect(result[1].isMerged).toBe(false)
      expect(result[2].isMerged).toBe(false)
    })
  })

  describe('undefined toolType fallback', () => {
    it('groups tool_calls with undefined toolType together as unknown category', () => {
      const step1 = createToolCallStep('t1', 'custom_tool', '')
      const step2 = createToolCallStep('t2', 'another_tool', '')
      // Remove toolType to make it undefined
      ;(step1 as any).toolType = undefined
      ;(step2 as any).toolType = undefined

      const result = mergeConsecutiveSteps([step1, step2])

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(true)
      expect(result[0].category).toBe('unknown')
    })

    it('handles undefined toolType mixed with defined toolType', () => {
      const step1 = createToolCallStep('t1', 'custom_tool', '')
      ;(step1 as any).toolType = undefined
      const step2 = createToolCallStep('t2', 'get_assets', 'data_query')

      const result = mergeConsecutiveSteps([step1, step2])

      expect(result).toHaveLength(2)
      expect(result[0].category).toBe('unknown')
      expect(result[1].category).toBe('data_query')
    })
  })

  describe('other step types', () => {
    it('passes artifact steps through unchanged', () => {
      const artifactStep: ProcessStep = {
        type: 'artifact',
        id: 'a1',
        title: 'Generated Report',
        url: '/reports/report.pdf',
        kind: 'report',
      }
      const result = mergeConsecutiveSteps([artifactStep])

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(false)
      expect(result[0].steps[0].type).toBe('artifact')
    })

    it('passes subagent steps through unchanged', () => {
      const subagentStep: ProcessStep = {
        type: 'subagent',
        id: 's1',
        taskId: 'task-123',
        title: 'Subagent Task',
        status: 'done',
      }
      const result = mergeConsecutiveSteps([subagentStep])

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(false)
      expect(result[0].steps[0].type).toBe('subagent')
    })

    it('passes progress steps through unchanged', () => {
      const progressStep: ProcessStep = {
        type: 'progress',
        id: 'p1',
        title: 'Processing...',
        status: 'running',
      }
      const result = mergeConsecutiveSteps([progressStep])

      expect(result).toHaveLength(1)
      expect(result[0].isMerged).toBe(false)
      expect(result[0].steps[0].type).toBe('progress')
    })
  })

  describe('complex sequences', () => {
    it('handles interleaved reasoning and tool_calls correctly', () => {
      const steps: ProcessStep[] = [
        createReasoningStep('r1', 'Starting analysis...'),
        createToolCallStep('t1', 'get_assets', 'data_query'),
        createReasoningStep('r2', 'Analyzing data...'),
        createToolCallStep('t2', 'get_liabilities', 'data_query'),
        createReasoningStep('r3', 'Calculating...'),
        createToolCallStep('t3', 'calc_ratio', 'calculation'),
        createToolCallStep('t4', 'calc_trend', 'calculation'),
      ]
      const result = mergeConsecutiveSteps(steps)

      // r1 (reasoning) → single
      // t1 (data_query) → single (followed by reasoning, not same-category)
      // r2 (reasoning) → single
      // t2 (data_query) → single (followed by reasoning)
      // r3 (reasoning) → single
      // t3+t4 (calculation) → merged
      expect(result).toHaveLength(6)
      expect(result[0].steps[0].type).toBe('reasoning')
      expect(result[1].steps[0].type).toBe('tool_call')
      expect(result[1].isMerged).toBe(false)
      expect(result[2].steps[0].type).toBe('reasoning')
      expect(result[3].steps[0].type).toBe('tool_call')
      expect(result[3].isMerged).toBe(false)
      expect(result[4].steps[0].type).toBe('reasoning')
      expect(result[5].isMerged).toBe(true)
      expect(result[5].category).toBe('calculation')
    })
  })
})