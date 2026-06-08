/**
 * Long task detection utility for Agent Execution Canvas.
 *
 * Determines when to switch from narrow bubble to full-width "execution canvas"
 * display based on configurable thresholds.
 */

import type { ProcessStep } from '@/types/agent-stream'

/**
 * Detection thresholds (configurable for tuning).
 */
export const DETECTION_THRESHOLDS = {
  /** Minimum steps to trigger canvas (≥3) */
  MIN_STEPS: 3,
  /** Tool names that trigger canvas regardless of step count */
  TRIGGER_TOOL_NAMES: ['generate_report', 'create_chart'] as const,
}

/**
 * Detection criteria for long task:
 * - hasDeepThink: Deep thinking mode enabled
 * - steps.length >= MIN_STEPS: At least 3 steps
 * - triggerToolNames: Special tools like generate_report
 *
 * @param steps - Process steps from normalizer
 * @param hasDeepThink - Whether deep thinking mode is enabled
 * @returns true if the task should use full-width canvas display
 */
export function isLongTask(
  steps: ProcessStep[],
  hasDeepThink: boolean,
): boolean {
  // Deep think always triggers canvas (immediate, no delay)
  if (hasDeepThink) return true

  // Check step count threshold
  if (steps.length >= DETECTION_THRESHOLDS.MIN_STEPS) return true

  // Check for trigger tool names (e.g., generate_report)
  for (const step of steps) {
    if (step.type === 'tool_call') {
      const name = step.name.toLowerCase()
      for (const triggerName of DETECTION_THRESHOLDS.TRIGGER_TOOL_NAMES) {
        if (name.includes(triggerName)) return true
      }
    }
  }

  return false
}

/**
 * Check if steps contain a tool that should trigger canvas immediately.
 * Used for early detection before steps accumulate.
 *
 * @param steps - Process steps from normalizer
 * @returns true if a trigger tool is detected
 */
export function hasTriggerTool(steps: ProcessStep[]): boolean {
  for (const step of steps) {
    if (step.type === 'tool_call') {
      const name = step.name.toLowerCase()
      for (const triggerName of DETECTION_THRESHOLDS.TRIGGER_TOOL_NAMES) {
        if (name.includes(triggerName)) return true
      }
    }
  }
  return false
}