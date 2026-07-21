import { computed } from 'vue'
import type { Ref } from 'vue'

/**
 * U7 (D5 TodoList) — derive reactive todo display state from the live
 * `todos` ref owned by `useThreadChat`.
 *
 * DeerFlow parity (`frontend/src/components/workspace/todo-list.tsx`):
 * - read-only semantics — the agent owns todo state via `write_todos`;
 *   the user cannot toggle items.
 * - todo item shape is `{ content, status }` (no id); UI keys by index+content.
 *
 * The composable is a thin derivation layer so components stay declarative
 * and the single source of truth stays in `useThreadChat` (which captures
 * `todos` from the `values` SSE channel + hydrates from checkpoint history).
 */
export interface TodoItem {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

export interface UseThreadTodosReturn {
  /** Normalized todo items (status coerced to the 3 known values). */
  todos: Ref<TodoItem[]>
  /** True when at least one todo item exists — gates TodoListBar rendering. */
  hasTodos: Ref<boolean>
  /** Count of completed items (for optional progress display). */
  completedCount: Ref<number>
  /** Total item count. */
  totalCount: Ref<number>
}

function normalizeStatus(status: string): TodoItem['status'] {
  switch (status) {
    case 'in_progress':
      return 'in_progress'
    case 'completed':
      return 'completed'
    default:
      return 'pending'
  }
}

/**
 * @param todosRef The `todos` ref returned by `useThreadChat` (single source
 * of truth). Pass `chat.todos`.
 */
export function useThreadTodos(
  todosRef: Ref<Array<{ content: string; status: string }>>,
): UseThreadTodosReturn {
  const todos = computed<TodoItem[]>(() =>
    (todosRef.value ?? []).map((t) => ({
      content: typeof t?.content === 'string' ? t.content : '',
      status: normalizeStatus(typeof t?.status === 'string' ? t.status : 'pending'),
    })),
  )
  const hasTodos = computed(() => todos.value.length > 0)
  const completedCount = computed(() => todos.value.filter((t) => t.status === 'completed').length)
  const totalCount = computed(() => todos.value.length)
  return { todos, hasTodos, completedCount, totalCount }
}
