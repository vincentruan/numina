import { describe, it, expect } from 'vitest'
import {
  isLongTask,
  hasTriggerTool,
  DETECTION_THRESHOLDS,
} from '@/utils/aiTaskDetection'
import type { ProcessStep } from '@/types/agent-stream'

// Helper to create tool_call steps
function createToolCallStep(id: string, name: string): ProcessStep {
  return {
    type: 'tool_call',
    id,
    name,
    displayName: name,
    icon: '🔧',
    toolType: 'data_query',
    args: {},
    status: 'done',
  }
}

// Helper to create reasoning steps
function createReasoningStep(id: string): ProcessStep {
  return {
    type: 'reasoning',
    id,
    content: 'Thinking...',
    status: 'done',
  }
}

describe('DETECTION_THRESHOLDS', () => {
  it('defines MIN_STEPS as 3', () => {
    expect(DETECTION_THRESHOLDS.MIN_STEPS).toBe(3)
  })

  it('defines trigger tool names', () => {
    expect(DETECTION_THRESHOLDS.TRIGGER_TOOL_NAMES).toContain('generate_report')
    expect(DETECTION_THRESHOLDS.TRIGGER_TOOL_NAMES).toContain('create_chart')
  })
})

describe('isLongTask', () => {
  describe('deep think mode', () => {
    it('returns true when hasDeepThink is true', () => {
      expect(isLongTask([], true)).toBe(true)
    })

    it('returns true when hasDeepThink is true even with 0 steps', () => {
      expect(isLongTask([], true)).toBe(true)
    })

    it('returns true when hasDeepThink is true even with 1 step', () => {
      const steps = [createToolCallStep('t1', 'get_assets')]
      expect(isLongTask(steps, true)).toBe(true)
    })
  })

  describe('U4: tool_call threshold', () => {
    // U4: threshold lowered — any tool_call triggers canvas
    it('returns false for 0 steps without deepThink', () => {
      expect(isLongTask([], false)).toBe(false)
    })

    it('returns false for reasoning-only steps without deepThink', () => {
      const steps = [createReasoningStep('r1'), createReasoningStep('r2')]
      expect(isLongTask(steps, false)).toBe(false)
    })

    it('returns true for 1 tool_call step without deepThink', () => {
      const steps = [createToolCallStep('t1', 'get_assets')]
      expect(isLongTask(steps, false)).toBe(true)
    })

    it('returns true for 2 tool_call steps without deepThink', () => {
      const steps = [
        createToolCallStep('t1', 'get_assets'),
        createToolCallStep('t2', 'get_liabilities'),
      ]
      expect(isLongTask(steps, false)).toBe(true)
    })

    it('returns true for 3 tool_call steps without deepThink', () => {
      const steps = [
        createToolCallStep('t1', 'get_assets'),
        createToolCallStep('t2', 'get_liabilities'),
        createToolCallStep('t3', 'get_members'),
      ]
      expect(isLongTask(steps, false)).toBe(true)
    })
  })

  describe('trigger tool names', () => {
    it('returns true for generate_report with 1 step', () => {
      const steps = [createToolCallStep('t1', 'generate_report')]
      expect(isLongTask(steps, false)).toBe(true)
    })

    it('returns true for create_chart with 1 step', () => {
      const steps = [createToolCallStep('t1', 'create_chart')]
      expect(isLongTask(steps, false)).toBe(true)
    })

    it('returns true for tool name containing generate_report', () => {
      const steps = [createToolCallStep('t1', 'agent_generate_report')]
      expect(isLongTask(steps, false)).toBe(true)
    })

    it('returns true for tool name containing create_chart', () => {
      const steps = [createToolCallStep('t1', 'pdf_create_chart')]
      expect(isLongTask(steps, false)).toBe(true)
    })

    // U4: Any tool_call triggers canvas, not just trigger tools
    it('returns true for non-trigger tool with 1 step', () => {
      const steps = [createToolCallStep('t1', 'get_assets')]
      expect(isLongTask(steps, false)).toBe(true)
    })
  })

  describe('mixed step types', () => {
    // U4: Any tool_call triggers canvas
    it('returns true when tool_call present among reasoning steps', () => {
      const steps = [
        createReasoningStep('r1'),
        createToolCallStep('t1', 'get_assets'),
        createReasoningStep('r2'),
      ]
      expect(isLongTask(steps, false)).toBe(true)
    })

    it('returns false for reasoning-only steps', () => {
      const steps = [createReasoningStep('r1'), createReasoningStep('r2')]
      expect(isLongTask(steps, false)).toBe(false)
    })

    it('returns true when tool_call present with artifact step', () => {
      const artifactStep: ProcessStep = {
        type: 'artifact',
        id: 'a1',
        title: 'Report',
        kind: 'report',
      }
      const steps = [
        createToolCallStep('t1', 'get_assets'),
        artifactStep,
      ]
      expect(isLongTask(steps, false)).toBe(true)
    })
  })

  describe('edge cases', () => {
    it('handles empty steps array', () => {
      expect(isLongTask([], false)).toBe(false)
    })

    it('handles case-insensitive tool names', () => {
      const steps = [createToolCallStep('t1', 'GENERATE_REPORT')]
      expect(isLongTask(steps, false)).toBe(true)
    })

    it('handles tool name with underscores', () => {
      const steps = [createToolCallStep('t1', 'generate_report_v2')]
      expect(isLongTask(steps, false)).toBe(true)
    })
  })
})

describe('hasTriggerTool', () => {
  it('returns true when generate_report is present', () => {
    const steps = [createToolCallStep('t1', 'generate_report')]
    expect(hasTriggerTool(steps)).toBe(true)
  })

  it('returns true when create_chart is present', () => {
    const steps = [createToolCallStep('t1', 'create_chart')]
    expect(hasTriggerTool(steps)).toBe(true)
  })

  it('returns false when no trigger tools', () => {
    const steps = [
      createToolCallStep('t1', 'get_assets'),
      createToolCallStep('t2', 'get_liabilities'),
    ]
    expect(hasTriggerTool(steps)).toBe(false)
  })

  it('returns false for empty steps', () => {
    expect(hasTriggerTool([])).toBe(false)
  })

  it('returns false for reasoning steps only', () => {
    const steps = [createReasoningStep('r1'), createReasoningStep('r2')]
    expect(hasTriggerTool(steps)).toBe(false)
  })
})