import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import DashboardNarrativeCard from '../DashboardNarrativeCard.vue'

// Mock dependencies before import
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (key === 'dashboard.narrative.thoughtFor') return `已思考 ${params?.duration ?? ''}`
      if (key === 'dashboard.narrative.generatedAt') return `生成于 ${params?.time ?? ''}`
      if (key === 'dashboard.narrative.title') return '本月洞察'
      if (key === 'dashboard.narrative.thinking') return '思考中'
      return key
    },
  }),
}))

vi.mock('vant', () => ({
  showToast: vi.fn(),
  showFailToast: vi.fn(),
}))

vi.mock('@/api/dashboard', () => ({
  streamNarrative: vi.fn(),
}))

vi.mock('@/composables/useTaskResume', () => ({
  useTaskResume: vi.fn(() => ({
    taskId: { value: null },
    status: { value: 'idle' },
    task: { value: null },
    triggerFailed: { value: false },
    resume: vi.fn().mockResolvedValue(false),
    retryTrigger: vi.fn().mockResolvedValue(false),
    cancel: vi.fn().mockResolvedValue(undefined),
    disconnect: vi.fn(),
    cleanup: vi.fn(),
  })),
}))

vi.mock('@/utils/sanitize', () => ({
  sanitizeMarkdown: (html: string) => html,
}))

describe('DashboardNarrativeCard — thinking elapsed persistence', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('derives thinkingElapsed from generatedAt on cache hit (timer never ran)', async () => {
    const wrapper = mount(DashboardNarrativeCard, {
      global: {
        stubs: {
          'van-cell-group': { template: '<div><slot /></div>' },
          'van-collapse': { template: '<div><slot /></div>', props: ['modelValue'] },
          'van-collapse-item': { template: '<div><slot name="title" /><slot /></div>', props: ['name'] },
          'van-loading': true,
          'van-button': true,
          'van-skeleton': true,
          'van-icon': true,
          IIcon: true,
        },
      },
    })

    const vm = wrapper.vm as any

    // Simulate cache-hit: content arrived, generatedAt set, timer never ran
    vm.narrative = 'Test narrative content'
    vm.generatedAt = new Date(Date.now() - 20000).toISOString() // 20s ago
    vm.loading = false
    vm.streaming = false

    await nextTick()
    await nextTick() // watcher needs a tick

    expect(vm.thinkingElapsed).toBeGreaterThanOrEqual(19000)
    expect(vm.thinkingElapsed).toBeLessThanOrEqual(21000)
    expect(vm.formattedElapsed).toBe('20秒')

    wrapper.unmount()
  })

  it('does NOT override live timer when streaming is active', async () => {
    const wrapper = mount(DashboardNarrativeCard, {
      global: {
        stubs: {
          'van-cell-group': { template: '<div><slot /></div>' },
          'van-collapse': { template: '<div><slot /></div>', props: ['modelValue'] },
          'van-collapse-item': { template: '<div><slot name="title" /><slot /></div>', props: ['name'] },
          'van-loading': true,
          'van-button': true,
          'van-skeleton': true,
          'van-icon': true,
          IIcon: true,
        },
      },
    })

    const vm = wrapper.vm as any

    // Simulate active streaming: timer started 5s ago
    vm.thinkingStart = Date.now() - 5000
    vm.thinkingElapsed = 5000
    vm.streaming = true
    vm.generatedAt = null

    await nextTick()
    await nextTick()

    // Watcher should NOT override because streaming is active
    expect(vm.thinkingElapsed).toBe(5000)

    wrapper.unmount()
  })

  it('stays at 0 when generatedAt is missing but content exists', async () => {
    const wrapper = mount(DashboardNarrativeCard, {
      global: {
        stubs: {
          'van-cell-group': { template: '<div><slot /></div>' },
          'van-collapse': { template: '<div><slot /></div>', props: ['modelValue'] },
          'van-collapse-item': { template: '<div><slot name="title" /><slot /></div>', props: ['name'] },
          'van-loading': true,
          'van-button': true,
          'van-skeleton': true,
          'van-icon': true,
          IIcon: true,
        },
      },
    })

    const vm = wrapper.vm as any
    vm.narrative = 'Content without timestamp'
    vm.generatedAt = null
    vm.loading = false
    vm.streaming = false
    vm.thinkingElapsed = 0

    await nextTick()
    await nextTick()

    expect(vm.thinkingElapsed).toBe(0)

    wrapper.unmount()
  })
})
