import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { useAgentStore } from '../../src/stores/agent'
import AgentsManagePage from '../../src/pages/AgentsManagePage.vue'

const { push } = vi.hoisted(() => ({
  push: vi.fn(),
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = (await importOriginal()) as any
  return {
    ...actual,
    useRouter: () => ({ push, back: vi.fn() }),
  }
})

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      agents: {
        title: '智能体管理',
        alwaysEnabled: '始终启用',
        noCustomAgents: '暂无自定义智能体',
        form: { deleteConfirm: '确认删除？', deleteSuccess: '删除成功' },
      },
      ai: {
        systemAgents: '系统智能体',
        systemAgentHint: '内置功能',
        customAgents: '自定义智能体',
        customAgentHint: '自定义指令',
        createAgent: '创建智能体',
      },
      toast: {
        agentToggleEnabled: '已启用',
        agentToggleDisabled: '已禁用',
      },
    },
  },
})

describe('AgentsManagePage skeleton shimmer tests', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
  })

  it('renders skeleton cells when agentStore.loading is true', async () => {
    const agentStore = useAgentStore()
    agentStore.loading = true

    const wrapper = mount(AgentsManagePage, {
      global: {
        plugins: [i18n],
        stubs: {
          VanNavBar: true,
          VanCellGroup: {
            template: '<div class="van-cell-group"><slot></slot></div>',
          },
          VanCell: {
            template: '<div class="van-cell"><slot name="icon"></slot><slot name="title"></slot><slot name="label"></slot><slot name="value"></slot></div>',
          },
          IIcon: true,
          AIBrainIcon: true,
          EmptyState: true,
          VanSwitch: true,
          VanIcon: true,
          VanButton: true,
          VanTag: true,
        },
      },
    })

    // Assert skeleton elements exist
    const skeletonCells = wrapper.findAll('.skeleton-cell')
    expect(skeletonCells.length).toBe(4) // 2 for system, 2 for custom

    const shimmerIcons = wrapper.findAll('.skeleton-icon.skeleton-shimmer')
    expect(shimmerIcons.length).toBe(4)

    const shimmerTitles = wrapper.findAll('.skeleton-title.skeleton-shimmer')
    expect(shimmerTitles.length).toBe(4)
  })

  it('renders actual agent cells when agentStore.loading is false', async () => {
    const agentStore = useAgentStore()
    agentStore.loading = false
    agentStore.systemAgents = [
      {
        id: '1',
        agent_name: 'numina',
        display_name: '数鸣',
        description: '数鸣智能体',
        icon: 'numina',
        color: '#6366F1',
        is_enabled: true,
        can_edit: false,
        can_delete: false,
        created_at: '',
        updated_at: '',
      } as any,
    ]
    agentStore.customAgents = [
      {
        id: '2',
        agent_name: 'custom-1',
        display_name: '我的智能体',
        description: '测试自定义',
        icon: 'test',
        color: '#10B981',
        is_enabled: true,
        can_edit: true,
        can_delete: true,
        created_at: '',
        updated_at: '',
      } as any,
    ]

    const wrapper = mount(AgentsManagePage, {
      global: {
        plugins: [i18n],
        stubs: {
          VanNavBar: true,
          IIcon: true,
          AIBrainIcon: true,
          EmptyState: true,
          VanSwitch: true,
          VanIcon: true,
          VanButton: true,
          VanTag: true,
        },
      },
    })

    // Assert no skeleton cells exist
    const skeletonCells = wrapper.findAll('.skeleton-cell')
    expect(skeletonCells.length).toBe(0)

    // Assert actual agent cells render
    const cells = wrapper.findAll('.van-cell')
    expect(cells.length).toBe(2) // 1 system + 1 custom
  })
})
