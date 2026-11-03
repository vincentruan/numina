import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import ScheduledTasksTab from '../ScheduledTasksTab.vue'
import type { ScheduledTask } from '@/api/ai-scheduled-tasks'

vi.mock('@/api/ai-scheduled-tasks', () => ({
  fetchScheduledTasks: vi.fn(),
  createScheduledTask: vi.fn(),
  updateScheduledTask: vi.fn(),
  deleteScheduledTask: vi.fn(),
}))

import * as api from '@/api/ai-scheduled-tasks'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: { 'zh-CN': {} },
})

function makeTask(overrides: Partial<ScheduledTask> = {}): ScheduledTask {
  return {
    id: '1',
    family_id: '1',
    skill_id: 'asset-report',
    cron_expression: '0 9 * * *',
    is_enabled: true,
    next_run_at: '2026-11-04T01:00:00+00:00',
    last_run_at: null,
    status: 'idle',
    last_error: null,
    created_at: '2026-11-03T00:00:00+00:00',
    updated_at: '2026-11-03T00:00:00+00:00',
    ...overrides,
  }
}

function mountTab(isOwner = true) {
  return mount(ScheduledTasksTab, {
    props: { isOwner },
    global: {
      plugins: [i18n],
      stubs: {
        'van-skeleton': true,
        'van-pull-refresh': { template: '<div><slot /></div>' },
        'van-list': { template: '<div><slot /></div>' },
        'van-popup': { template: '<div><slot /></div>' },
        'van-picker': true,
        'van-form': { template: '<form><slot /></form>' },
        'van-field': true,
        'van-radio-group': { template: '<div><slot /></div>' },
        'van-radio': true,
        'van-switch': true,
        'van-button': { template: '<button><slot /></button>' },
        'van-icon': true,
        EmptyState: { template: '<div class="empty-state"><slot /></div>' },
      },
    },
  })
}

describe('ScheduledTasksTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a task card for each scheduled task', async () => {
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({
      data: { items: [makeTask(), makeTask({ id: '2', cron_expression: '0 9 * * 0' })] },
    } as never)

    const wrapper = mountTab()
    await flushPromises()

    expect(wrapper.findAll('.task-card')).toHaveLength(2)
    expect(wrapper.text()).toContain('0 9 * * *')
  })

  it('shows the empty state when the family has no tasks', async () => {
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({ data: { items: [] } } as never)

    const wrapper = mountTab()
    await flushPromises()

    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('hides owner-only controls from non-owner members', async () => {
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({
      data: { items: [makeTask()] },
    } as never)

    const wrapper = mountTab(false)
    await flushPromises()

    expect(wrapper.find('.task-card__actions').exists()).toBe(false)
    expect(wrapper.find('.page-actions').exists()).toBe(false)
  })

  it('shows failed status and the recorded error', async () => {
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({
      data: {
        items: [makeTask({ status: 'failed', last_error: 'HTTP 500: boom' })],
      },
    } as never)

    const wrapper = mountTab()
    await flushPromises()

    expect(wrapper.find('.task-card__status--failed').exists()).toBe(true)
    expect(wrapper.text()).toContain('HTTP 500: boom')
  })
})
