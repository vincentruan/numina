import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import TodoListBar from '../TodoListBar.vue'
import { useThreadTodos, type TodoItem } from '@/composables/ai-chat/useThreadTodos'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

// jsdom does not parse <style scoped> into getComputedStyle, so the touch-
// target (≥44px) tests read the SFC source directly to assert the CSS rule is
// present (the build + browser apply it at runtime). The spec sits in
// __tests__/; the component is one directory up.
const todoListBarSource = readFileSync(
  resolve(process.cwd(), 'src/components/ai-chat/TodoListBar.vue'),
  'utf8',
)

// Vant components (van-icon, van-checkbox, van-tag) are globally registered via
// unplugin-vue-components in the real app; in tests they resolve to stubs via
// the global.components stub config (see vitest config). Mount with stubs to
// avoid importing the full Vant library.

function makeTodos(overrides: Partial<TodoItem>[] = []): TodoItem[] {
  return [
    { content: '分析资产', status: 'completed' },
    { content: '查询负债', status: 'in_progress' },
    { content: '生成报告', status: 'pending' },
    ...overrides,
  ]
}

function mountBar(props: Partial<{ todos: TodoItem[] }> = {}) {
  return mount(TodoListBar, {
    props: {
      todos: makeTodos(),
      ...props,
    },
    global: {
      stubs: {
        'van-icon': { template: '<i class="van-icon"><slot /></i>' },
        'van-checkbox': {
          props: ['modelValue', 'disabled', 'shape'],
          template: '<span class="van-checkbox" :data-disabled="disabled" :data-checked="modelValue"></span>',
        },
        'van-tag': {
          props: ['type', 'round'],
          template: '<span class="van-tag"><slot /></span>',
        },
      },
    },
  })
}

describe('TodoListBar', () => {
  it('renders the header with todosLabel + count when todos exist', () => {
    const wrapper = mountBar()
    expect(wrapper.find('.todo-list-bar__label').text()).toBe('aiChat.todosLabel')
    // 1 completed / 3 total
    expect(wrapper.find('.todo-list-bar__count').text()).toBe('1/3')
  })

  it('renders one item per todo with content', () => {
    const wrapper = mountBar()
    const items = wrapper.findAll('.todo-list-bar__item')
    expect(items).toHaveLength(3)
    expect(items[0].find('.todo-list-bar__content').text()).toBe('分析资产')
    expect(items[1].find('.todo-list-bar__content').text()).toBe('查询负债')
    expect(items[2].find('.todo-list-bar__content').text()).toBe('生成报告')
  })

  it('is collapsed by default (chevron not rotated, aria-expanded false)', () => {
    const wrapper = mountBar()
    // The collapsed ref drives the chevron rotation class + aria-expanded.
    // (v-show display state is the visible effect; the class is the source of truth.)
    expect(wrapper.find('.todo-list-bar__chevron-icon').classes()).not.toContain('todo-list-bar__chevron-icon--open')
    expect(wrapper.find('.todo-list-bar__header').attributes('aria-expanded')).toBe('false')
  })

  it('expands on header click and collapses on second click', async () => {
    const wrapper = mountBar()
    await wrapper.find('.todo-list-bar__header').trigger('click')
    expect(wrapper.find('.todo-list-bar__chevron-icon').classes()).toContain('todo-list-bar__chevron-icon--open')
    expect(wrapper.find('.todo-list-bar__header').attributes('aria-expanded')).toBe('true')
    // body is now visible (v-show removed display:none)
    expect(wrapper.find('.todo-list-bar__body').element.style.display).not.toBe('none')
    await wrapper.find('.todo-list-bar__header').trigger('click')
    expect(wrapper.find('.todo-list-bar__chevron-icon').classes()).not.toContain('todo-list-bar__chevron-icon--open')
    // body hidden via v-show → display:none
    expect(wrapper.find('.todo-list-bar__body').element.style.display).toBe('none')
  })

  it('marks completed items with the done content class', () => {
    const wrapper = mountBar()
    const items = wrapper.findAll('.todo-list-bar__item')
    expect(items[0].classes()).toContain('todo-list-bar__item--completed')
    expect(items[0].find('.todo-list-bar__content').classes()).toContain('todo-list-bar__content--done')
  })

  it('marks in_progress items with the in_progress class + primary content', () => {
    const wrapper = mountBar()
    const items = wrapper.findAll('.todo-list-bar__item')
    expect(items[1].classes()).toContain('todo-list-bar__item--in_progress')
    // in_progress content is NOT struck-through (only completed is)
    expect(items[1].find('.todo-list-bar__content').classes()).not.toContain('todo-list-bar__content--done')
  })

  it('renders empty list without crashing and hides count', () => {
    const wrapper = mountBar({ todos: [] })
    expect(wrapper.findAll('.todo-list-bar__item')).toHaveLength(0)
    // count span not rendered when todos.length is 0 (v-if)
    expect(wrapper.find('.todo-list-bar__count').exists()).toBe(false)
  })

  it('header CSS declares ≥44px min-height touch target', () => {
    // jsdom does not parse <style scoped> blocks into getComputedStyle, so
    // assert the rule is present in the component SFC source (the build +
    // browser apply it at runtime).
    expect(todoListBarSource).toMatch(/\.todo-list-bar__header\s*{[^}]*min-height:\s*44px/)
  })

  it('chevron CSS declares ≥44px min-width + min-height tap zone', () => {
    expect(todoListBarSource).toMatch(/\.todo-list-bar__chevron\s*{[^}]*min-width:\s*44px/)
    expect(todoListBarSource).toMatch(/\.todo-list-bar__chevron\s*{[^}]*min-height:\s*44px/)
  })

  it('does not declare any component emits (read-only — no backend calls)', () => {
    const wrapper = mountBar()
    // The component has no `defineEmits`; the only events in `emitted()` are
    // native DOM events (click) forwarded by @vue/test-utils, not component
    // emits. Assert the component's emits option is undefined/empty.
    const optionEmits = (wrapper.vm.$options as { emits?: unknown }).emits
    expect(optionEmits).toBeFalsy()
  })

  it('reflects status changes reactively when todos prop updates', async () => {
    const wrapper = mountBar({ todos: makeTodos() })
    await wrapper.find('.todo-list-bar__header').trigger('click')
    expect(wrapper.findAll('.todo-list-bar__item--pending')).toHaveLength(1)
    // mark the pending item completed
    await wrapper.setProps({
      todos: makeTodos().map((t, i) => (i === 2 ? { ...t, status: 'completed' as const } : t)),
    })
    expect(wrapper.findAll('.todo-list-bar__item--pending')).toHaveLength(0)
    expect(wrapper.findAll('.todo-list-bar__item--completed')).toHaveLength(2)
    expect(wrapper.find('.todo-list-bar__count').text()).toBe('2/3')
  })

  it('keys items by index+content (stable key, no id required)', () => {
    const wrapper = mountBar()
    const items = wrapper.findAll('.todo-list-bar__item')
    // key attr is applied via :key — verify items render in order matching content
    expect(items[0].find('.todo-list-bar__content').text()).toBe('分析资产')
  })
})

describe('useThreadTodos', () => {
  it('derives hasTodos=false from empty ref', () => {
    const source = ref<Array<{ content: string; status: string }>>([])
    const { hasTodos, todos, totalCount, completedCount } = useThreadTodos(source)
    expect(hasTodos.value).toBe(false)
    expect(todos.value).toEqual([])
    expect(totalCount.value).toBe(0)
    expect(completedCount.value).toBe(0)
  })

  it('derives hasTodos=true + normalizes status from non-empty ref', () => {
    const source = ref([{ content: 'a', status: 'in_progress' }, { content: 'b', status: 'completed' }, { content: 'c', status: 'unknown' }])
    const { hasTodos, todos, totalCount, completedCount } = useThreadTodos(source)
    expect(hasTodos.value).toBe(true)
    expect(totalCount.value).toBe(3)
    expect(completedCount.value).toBe(1)
    expect(todos.value[0].status).toBe('in_progress')
    expect(todos.value[1].status).toBe('completed')
    // unknown status coerces to pending
    expect(todos.value[2].status).toBe('pending')
  })

  it('reacts to source ref mutation', async () => {
    const source = ref<Array<{ content: string; status: string }>>([{ content: 'a', status: 'pending' }])
    const { hasTodos, totalCount } = useThreadTodos(source)
    expect(hasTodos.value).toBe(true)
    source.value = []
    await nextTick()
    expect(hasTodos.value).toBe(false)
    expect(totalCount.value).toBe(0)
  })
})
