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

vi.mock('vant', async () => {
  const actual = await vi.importActual<typeof import('vant')>('vant')
  return {
    ...actual,
    showConfirmDialog: vi.fn(),
    showFailToast: vi.fn(),
    showSuccessToast: vi.fn(),
  }
})

import * as api from '@/api/ai-scheduled-tasks'
import { showConfirmDialog, showFailToast } from 'vant'

// Only the keys these tests read back are supplied: ``van-field`` label lookups
// match on rendered text, so an empty message table would leave raw key paths.
const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      scheduledTasks: {
        time: '时间',
        cron: 'Cron 表达式',
        cronInvalid: 'cron 表达式无效，请使用 5 字段格式',
      },
    },
  },
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

/**
 * Stubs that keep the form interactive so the handlers can be driven.
 *
 * The global setup stubs Vant components as inert placeholders (VanField renders
 * a bare input with no label slot, VanRadioGroup renders no children), which is
 * fine for render assertions but makes it impossible to change frequency or read
 * back which field is which. These PascalCase overrides replace them per-mount.
 */
function mountInteractive(isOwner = true) {
  const VanField = {
    name: 'VanField',
    props: ['modelValue', 'label', 'type', 'placeholder', 'errorMessage', 'readonly'],
    emits: ['update:modelValue', 'blur'],
    template: `
      <div class="form-field" :data-label="label">
        <input
          class="form-field__input"
          :type="type || 'text'"
          :value="modelValue"
          :readonly="readonly"
          @input="$emit('update:modelValue', $event.target.value)"
          @blur="$emit('blur')"
        />
        <slot name="input" />
        <span v-if="errorMessage" class="form-field__error">{{ errorMessage }}</span>
      </div>
    `,
  }

  // VanRadioGroup/Radio mirror Vant's real provide/inject contract: the group
  // owns the model and each radio reports its own name up to it. A slot-only
  // stub would render the options but never change the bound value.
  const VanRadioGroup = {
    name: 'VanRadioGroup',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    provide() {
      return {
        vanRadioGroup: {
          get value() {
            return (this as unknown as { $props: { modelValue: string } }).$props.modelValue
          },
          set: (v: string) => this.$emit('update:modelValue', v),
        },
      }
    },
    template: '<div class="radio-group"><slot /></div>',
  }

  const VanRadio = {
    name: 'VanRadio',
    props: ['name'],
    inject: ['vanRadioGroup'],
    template: '<button class="radio" :data-name="name" @click="vanRadioGroup.set(name)"><slot /></button>',
  }

  const VanForm = {
    name: 'VanForm',
    emits: ['submit'],
    template:
      '<form @submit.prevent="$emit(`submit`, {})"><slot /></form>',
  }

  const VanSwitch = {
    name: 'VanSwitch',
    props: ['modelValue', 'size', 'loading'],
    emits: ['update:modelValue'],
    template:
      '<button class="switch" :data-on="String(modelValue)" @click="$emit(`update:modelValue`, !modelValue)" />',
  }

  return mount(ScheduledTasksTab, {
    props: { isOwner },
    global: {
      plugins: [i18n],
      stubs: {
        VanField,
        VanRadioGroup,
        VanRadio,
        VanForm,
        VanSwitch,
        VanSkeleton: true,
        VanPicker: true,
      },
    },
  })
}

type Wrapper = ReturnType<typeof mountInteractive>

function formField(wrapper: Wrapper, label: string) {
  const field = wrapper.findAll('.form-field').find((f) => f.attributes('data-label') === label)
  if (!field) throw new Error(`no form field labelled ${label}`)
  return field
}

async function openCreateForm(wrapper: Wrapper) {
  await wrapper.find('.page-actions button').trigger('click')
  await flushPromises()
}

describe('ScheduledTasksTab form behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({ data: { items: [] } } as never)
    vi.mocked(api.createScheduledTask).mockResolvedValue({ data: makeTask() } as never)
    vi.mocked(api.updateScheduledTask).mockResolvedValue({ data: makeTask() } as never)
    vi.mocked(api.deleteScheduledTask).mockResolvedValue(undefined as never)
  })

  it('submits a daily preset as "<minute> <hour> * * *"', async () => {
    const wrapper = mountInteractive()
    await flushPromises()
    await openCreateForm(wrapper)

    await formField(wrapper, '时间').find('input').setValue('09:30')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.createScheduledTask).toHaveBeenCalledWith({
      skill_id: 'asset-report',
      cron_expression: '30 9 * * *',
      is_enabled: true,
    })
  })

  it('submits a weekly preset with Sunday (0) as the day of week', async () => {
    const wrapper = mountInteractive()
    await flushPromises()
    await openCreateForm(wrapper)

    await wrapper.find('.radio[data-name="weekly"]').trigger('click')
    await formField(wrapper, '时间').find('input').setValue('07:05')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.createScheduledTask).toHaveBeenCalledWith({
      skill_id: 'asset-report',
      cron_expression: '5 7 * * 0',
      is_enabled: true,
    })
  })

  it('rejects a custom cron that is not five fields', async () => {
    const wrapper = mountInteractive()
    await flushPromises()
    await openCreateForm(wrapper)

    await wrapper.find('.radio[data-name="custom"]').trigger('click')
    await flushPromises()
    await formField(wrapper, 'Cron 表达式').find('input').setValue('0 9 * *')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.createScheduledTask).not.toHaveBeenCalled()
    expect(wrapper.find('.form-field__error').exists()).toBe(true)
  })

  it('accepts a valid custom cron verbatim', async () => {
    const wrapper = mountInteractive()
    await flushPromises()
    await openCreateForm(wrapper)

    await wrapper.find('.radio[data-name="custom"]').trigger('click')
    await flushPromises()
    await formField(wrapper, 'Cron 表达式').find('input').setValue('15 6 * * 1-5')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(api.createScheduledTask).toHaveBeenCalledWith({
      skill_id: 'asset-report',
      cron_expression: '15 6 * * 1-5',
      is_enabled: true,
    })
  })

  it('toggles a task and replaces it with the server response', async () => {
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({
      data: { items: [makeTask()] },
    } as never)
    vi.mocked(api.updateScheduledTask).mockResolvedValue({
      data: makeTask({ is_enabled: false }),
    } as never)

    const wrapper = mountInteractive()
    await flushPromises()

    await wrapper.find('.task-card .switch').trigger('click')
    await flushPromises()

    expect(api.updateScheduledTask).toHaveBeenCalledWith('1', { is_enabled: false })
    expect(wrapper.find('.task-card .switch').attributes('data-on')).toBe('false')
  })

  it('deletes a task once the confirm dialog resolves', async () => {
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({
      data: { items: [makeTask()] },
    } as never)

    const wrapper = mountInteractive()
    await flushPromises()

    await wrapper.find('.action-btn--danger').trigger('click')
    await flushPromises()

    expect(showConfirmDialog).toHaveBeenCalled()
    expect(api.deleteScheduledTask).toHaveBeenCalledWith('1')
    expect(wrapper.findAll('.task-card')).toHaveLength(0)
  })

  it('does not delete when the confirm dialog is dismissed', async () => {
    vi.mocked(api.fetchScheduledTasks).mockResolvedValue({
      data: { items: [makeTask()] },
    } as never)
    vi.mocked(showConfirmDialog).mockRejectedValueOnce('cancel')

    const wrapper = mountInteractive()
    await flushPromises()

    await wrapper.find('.action-btn--danger').trigger('click')
    await flushPromises()

    expect(api.deleteScheduledTask).not.toHaveBeenCalled()
    expect(wrapper.findAll('.task-card')).toHaveLength(1)
  })

  it('shows a failure toast when loading the list fails', async () => {
    vi.mocked(api.fetchScheduledTasks).mockRejectedValueOnce(new Error('boom'))

    mountInteractive()
    await flushPromises()

    expect(showFailToast).toHaveBeenCalled()
  })
})
