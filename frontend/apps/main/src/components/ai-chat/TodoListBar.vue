<script setup lang="ts">
/**
 * TodoListBar — mobile-adapted read-only todo list for /ai/chat (U7 / D5).
 *
 * DeerFlow parity (`frontend/src/components/workspace/todo-list.tsx`):
 * - read-only: the agent owns todo state via `write_todos`; the user cannot
 *   toggle items. `van-checkbox` is `disabled` and serves only as a visual
 *   "completed" indicator.
 * - default collapsed (`internalCollapsed = ref(true)`); click header toggles.
 * - item shape `{ content, status }` (no id) — keyed by `index + content`.
 *
 * Mobile design (375×812 baseline): see
 * `docs/design/ai-chat-todolist-mobile-adaptation.md`.
 *   - header min-height: 44px (Apple HIG touch target; DeerFlow desktop 32px
 *     is too small for touch).
 *   - chevron container ≥44px; collapsed list scrollable (max-height 180px).
 *   - status: completed → checked checkbox (disabled); in_progress → primary
 *     tag + primary text; pending → empty circle.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TodoItem } from '@/composables/ai-chat/useThreadTodos'

const props = defineProps<{
  todos: TodoItem[]
}>()

const { t } = useI18n()

// Default collapsed — aligned with DeerFlow `internalCollapsed = useState(true)`.
const collapsed = ref(true)

function toggle() {
  // Pure local UI state — no backend call (read-only semantics).
  collapsed.value = !collapsed.value
}

// Stable key per DeerFlow `todo-list.tsx:76` (i + content).
function itemKey(todo: TodoItem, index: number): string {
  return `${index}-${todo.content}`
}

// aria-label for the status indicator — screen-reader friendly status text.
function statusLabel(status: TodoItem['status']): string {
  switch (status) {
    case 'completed':
      return t('aiChat.todoStatusCompleted')
    case 'in_progress':
      return t('aiChat.todoStatusInProgress')
    default:
      return t('aiChat.todoStatusPending')
  }
}
</script>

<template>
  <div class="todo-list-bar" role="region" :aria-label="t('aiChat.todosLabel')">
    <button
      type="button"
      class="todo-list-bar__header"
      :aria-expanded="!collapsed"
      :aria-controls="`todo-list-bar-body-${props.todos.length}`"
      @click="toggle"
    >
      <span class="todo-list-bar__title">
        <van-icon name="orders-o" class="todo-list-bar__icon" />
        <span class="todo-list-bar__label">{{ t('aiChat.todosLabel') }}</span>
        <span v-if="props.todos.length" class="todo-list-bar__count">
          {{ props.todos.filter((x) => x.status === 'completed').length }}/{{ props.todos.length }}
        </span>
      </span>
      <span class="todo-list-bar__chevron">
        <van-icon
          name="arrow-up"
          class="todo-list-bar__chevron-icon"
          :class="{ 'todo-list-bar__chevron-icon--open': !collapsed }"
        />
      </span>
    </button>

    <ul
      v-show="!collapsed"
      :id="`todo-list-bar-body-${props.todos.length}`"
      class="todo-list-bar__body"
      role="list"
    >
      <li
        v-for="(todo, index) in props.todos"
        :key="itemKey(todo, index)"
        class="todo-list-bar__item"
        :class="`todo-list-bar__item--${todo.status}`"
        role="listitem"
      >
        <span
          class="todo-list-bar__indicator"
          :aria-label="statusLabel(todo.status)"
        >
          <!-- completed → read-only checked checkbox -->
          <van-checkbox
            v-if="todo.status === 'completed'"
            :model-value="true"
            disabled
            shape="square"
          />
          <!-- in_progress → primary tag dot -->
          <van-tag
            v-else-if="todo.status === 'in_progress'"
            type="primary"
            round
            class="todo-list-bar__dot"
          >
            •
          </van-tag>
          <!-- pending → empty circle -->
          <van-icon
            v-else
            name="circle"
            class="todo-list-bar__circle"
          />
        </span>
        <span
          class="todo-list-bar__content"
          :class="{ 'todo-list-bar__content--done': todo.status === 'completed' }"
          :title="todo.content"
        >
          {{ todo.content }}
        </span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.todo-list-bar {
  width: 100%;
  border-top-left-radius: 12px;
  border-top-right-radius: 12px;
  border: 1px solid var(--van-border-color, #ebedf0);
  border-bottom: 0;
  background: var(--van-background-2, #fff);
  overflow: hidden;
}

.todo-list-bar__header {
  /* ≥44px touch target (Apple HIG); DeerFlow desktop min-h-8 (32px) is too
     small for mobile touch. */
  min-height: 44px;
  width: 100%;
  padding: 0 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--van-background-2, #f7f8fa);
  border: 0;
  cursor: pointer;
  /* reset native button styles */
  font: inherit;
  color: inherit;
  text-align: left;
}

.todo-list-bar__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--van-text-color-2, #969799);
  min-width: 0;
}

.todo-list-bar__icon {
  font-size: 16px;
}

.todo-list-bar__label {
  white-space: nowrap;
}

.todo-list-bar__count {
  font-size: 12px;
  color: var(--van-text-color-3, #c8c9cc);
  margin-left: 2px;
}

.todo-list-bar__chevron {
  /* ensure right-side tap zone ≥44px */
  min-width: 44px;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 -12px 0 0;
  padding: 0 12px;
}

.todo-list-bar__chevron-icon {
  font-size: 16px;
  color: var(--van-text-color-2, #969799);
  transition: transform 0.3s ease;
}

.todo-list-bar__chevron-icon--open {
  transform: rotate(180deg);
}

.todo-list-bar__body {
  margin: 0;
  padding: 4px 0;
  list-style: none;
  max-height: 180px;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.todo-list-bar__item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 6px 12px;
  /* single line + ellipsis (mobile density) */
}

.todo-list-bar__indicator {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
}

.todo-list-bar__dot {
  min-width: 8px;
  height: 8px;
  padding: 0;
  border: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.todo-list-bar__circle {
  font-size: 16px;
  color: var(--van-text-color-3, #c8c9cc);
}

.todo-list-bar__content {
  flex: 1 1 auto;
  min-width: 0;
  font-size: 13px;
  line-height: 1.4;
  color: var(--van-text-color, #323233);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.todo-list-bar__content--done {
  color: var(--van-text-color-3, #c8c9cc);
  text-decoration: line-through;
}

.todo-list-bar__item--in_progress .todo-list-bar__content {
  color: var(--van-primary-color, #1989fa);
  font-weight: 500;
}
</style>
