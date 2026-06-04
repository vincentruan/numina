import { computed, type Ref } from 'vue'
import type { PlanStep, ProcessStep } from '@/types/agent-stream'

// Map tool names to their inferred plan step labels (zh-CN)
const TOOL_LABEL_MAP: Record<string, string> = {
  web_search: '搜索',
  tavily_search: '搜索',
  code_interpreter: '计算',
  python_repl: '计算',
  // write_todos is suppressed (not in this map — handled explicitly)
}

// Keyword → label map for reasoning content (checked against first 10 chars)
const REASONING_KEYWORD_MAP: Array<{ keywords: string[]; label: string }> = [
  { keywords: ['搜索', '查找', '查询', '检索', 'search'], label: '搜索' },
  { keywords: ['计算', '统计', '汇总', 'calcul', 'compute'], label: '计算' },
  { keywords: ['分析', 'analys', 'analyz'], label: '分析' },
  { keywords: ['规划', '计划', '步骤', 'plan'], label: '规划' },
  { keywords: ['生成', '写', '撰写', 'generat', 'writ'], label: '生成' },
  { keywords: ['读取', '获取', '加载', 'read', 'fetch', 'load'], label: '读取' },
]

const FALLBACK_REASONING_LABEL = '思考'
const FALLBACK_TOOL_LABEL = '工具调用'

// write_todos transient label — shown while planning is in progress
export const WRITE_TODOS_PLANNING_LABEL = 'AI 正在规划...'

/**
 * Derives a short label from a tool name.
 * Returns null when the tool is suppressed (write_todos).
 */
function labelFromTool(toolName: string): string | null {
  if (toolName === 'write_todos') return null
  if (TOOL_LABEL_MAP[toolName]) return TOOL_LABEL_MAP[toolName]
  // mcp_* → generic tool call label
  if (toolName.startsWith('mcp_')) return FALLBACK_TOOL_LABEL
  return FALLBACK_TOOL_LABEL
}

/**
 * Derives a short label from the first 10 chars of reasoning content.
 */
function labelFromReasoning(content: string): string {
  const snippet = content.slice(0, 10).toLowerCase()
  for (const { keywords, label } of REASONING_KEYWORD_MAP) {
    if (keywords.some((kw) => snippet.includes(kw.toLowerCase()))) return label
  }
  return FALLBACK_REASONING_LABEL
}

/**
 * Options for usePlanInference.
 */
export interface UsePlanInferenceOptions {
  /** The reactive ProcessStep array from the normalizer */
  steps: Ref<ProcessStep[]>
  /** Current plan source — inferred steps are only derived when 'inferred' */
  planSource: Ref<'explicit' | 'inferred' | null>
  /**
   * Step count from the latest plan_update (write_todos result).
   * When truthy and planSource is 'explicit', the write_todos transient step
   * is replaced by a "制定了 N 步计划" collapsed label.
   */
  explicitPlanStepCount?: Ref<number>
}

/**
 * usePlanInference — Source B inference composable.
 *
 * When planSource === 'inferred', derives a deduplicated PlanStep[] from the
 * observed ProcessStep[] (tool_calls and reasoning blocks).
 *
 * When planSource === 'explicit' the inferred steps are cleared and the
 * caller should use the explicit planSteps directly.
 *
 * write_todos handling:
 *   - A write_todos tool_call emits a transient "AI 正在规划..." step.
 *   - When planSource switches to 'explicit' (plan_update arrived),
 *     inferredPlanSteps is cleared — callers should show the explicit plan.
 */
export function usePlanInference(options: UsePlanInferenceOptions) {
  const { steps, planSource, explicitPlanStepCount } = options

  /**
   * Derived, deduplicated plan steps from observed process steps.
   * Only populated when planSource === 'inferred'.
   * - tool_call steps with suppressed names (write_todos) are excluded,
   *   but generate a single transient "AI 正在规划..." entry instead.
   * - Consecutive steps with the same label are merged into one.
   * - All inferred steps are 'done' (append-only, never revert).
   */
  const inferredPlanSteps = computed<PlanStep[]>(() => {
    if (planSource.value !== 'inferred') return []

    const result: PlanStep[] = []
    let idSeq = 0
    let hasWriteTodos = false

    for (const step of steps.value) {
      let label: string | null = null

      if (step.type === 'tool_call') {
        if (step.name === 'write_todos') {
          hasWriteTodos = true
          continue // suppress from inferred steps
        }
        label = labelFromTool(step.name)
      } else if (step.type === 'reasoning') {
        if (!step.content) continue
        label = labelFromReasoning(step.content)
      } else {
        // subagent, artifact, progress — not inferred as plan steps
        continue
      }

      if (!label) continue

      // Deduplication: skip if last step has the same label
      const last = result[result.length - 1]
      if (last && last.label === label) continue

      idSeq += 1
      result.push({ id: `inferred-${idSeq}`, label, status: 'done' })
    }

    // If write_todos appeared and we still have no explicit plan, add transient step
    if (hasWriteTodos) {
      result.push({
        id: 'inferred-planning',
        label: WRITE_TODOS_PLANNING_LABEL,
        status: 'active',
      })
    }

    return result
  })

  /**
   * When planSource switches to 'explicit' after a write_todos,
   * returns the collapsed summary label for display.
   * e.g. "制定了 3 步计划"
   */
  const writeTodosCollapsedLabel = computed<string | null>(() => {
    if (planSource.value !== 'explicit') return null
    const count = explicitPlanStepCount?.value
    if (!count) return null
    return `制定了 ${count} 步计划`
  })

  return {
    inferredPlanSteps,
    writeTodosCollapsedLabel,
  }
}
