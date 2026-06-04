import type { PlanStep } from '@/types/agent-stream'

/**
 * Produces a stable hash of a todo list based on content+status only.
 * Used to skip redundant plan.update events when DeerFlow emits the full
 * todo list on every graph node transition but the list hasn't changed.
 */
export function hashTodos(todos: Array<{ content: string; status: string }>): string {
  return JSON.stringify(todos.map((t) => `${t.content}|${t.status}`))
}

/**
 * Maps DeerFlow todo status strings to PlanStep status values.
 *   pending     → pending
 *   in_progress → active
 *   completed   → done
 *   (anything else) → pending
 */
function mapStatus(status: string): PlanStep['status'] {
  switch (status) {
    case 'in_progress':
      return 'active'
    case 'completed':
      return 'done'
    case 'error':
      return 'error'
    default:
      return 'pending'
  }
}

/**
 * Converts an array of DeerFlow todos into PlanStep objects for UI rendering.
 */
export function mapTodosToPlanSteps(
  todos: Array<{ id: string; content: string; status: string }>,
): PlanStep[] {
  return todos.map((t) => ({
    id: t.id,
    label: t.content,
    status: mapStatus(t.status),
  }))
}
