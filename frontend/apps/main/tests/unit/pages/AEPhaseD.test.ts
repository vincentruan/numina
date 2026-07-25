/**
 * AE4 + AE10 integration tests (Phase D / U16).
 *
 * AE4 - Given owner enters /settings/ai/skills, when the page renders, then
 * the "fixed skills" section header is gone. Per T11 (BUILTIN_CAPABILITIES
 * deleted), builtin skills are no longer family-toggleable, so the builtin
 * section renders no rows; only custom skills (if any) appear.
 *
 * AE10 — Given owner clicks the edit button on numina's card, when AgentFormPage
 * loads with agent_type='system', then all form fields are disabled, save
 * button is removed from the DOM, and a banner explains the read-only mode.
 */
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'

const mockParams = { id: '' }
vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
  useRoute: () => ({ params: mockParams }),
}))

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      common: { back: '返回', noData: '暂无数据' },
      toast: { loadFailed: '❌ 加载失败', operationFailed: '❌ 操作失败' },
      skills: {
        title: '技能管理',
        builtinSkills: '内置技能',
        customSkills: '自定义技能',
        capability: {
          report: { name: '资产体检', description: '综合健康评分' },
          alerts: { name: '老化预警', description: '即将到期资产' },
          allocation: { name: '配置漂移', description: '资产配置偏离' },
          disposal: { name: '闲置清仓', description: '建议处置资产' },
          liability: { name: '负债优化', description: '还款策略' },
          spending_leak: { name: '资金泄漏', description: '检测泄漏' },
        },
        form: {
          createBtn: '创建',
          updateBtn: '保存',
          skillId: 'ID',
          skillIdPlaceholder: '',
          skillName: '名称',
          skillNamePlaceholder: '',
          skillDescription: '描述',
          skillDescriptionPlaceholder: '',
          skillIcon: '图标',
          skillColor: '颜色',
          skillInputMode: '输入模式',
          inputModeTrigger: '触发',
          inputModeFreeText: '自由',
          skillPrompt: '提示词',
          skillPromptPlaceholder: '',
          skillIdInvalid: 'invalid',
          skillIdConflict: 'conflict',
          skillIdReserved: 'reserved',
          skillIdExists: 'exists',
          updateSuccess: '✅ 已更新',
        },
      },
      agents: {
        editAgent: '编辑智能体',
        createAgent: '创建智能体',
        form: {
          agentName: '标识名',
          agentNameHint: '小写字母开头',
          displayName: '显示名称',
          description: '描述',
          icon: '图标',
          color: '颜色',
          soulMd: '人格定义',
          soulMdHint: '',
          skills: '可用技能',
          model: '模型',
          modelInherit: '继承',
          subagentEnabled: '子智能体',
          createBtn: '创建',
          updateBtn: '保存',
          systemAgentBanner: '🔒 系统智能体只读',
          noEnabledSkills: '尚未启用任何技能',
          updateSuccess: '✅ 已更新',
          createSuccess: '✅ 已创建',
        },
      },
    },
  },
})

// ── AE4: SkillsManagePage no fixed-skills section ─────────────────────────────

const skillsManageMocks = vi.hoisted(() => ({
  getSkillsGrouped: vi.fn(),
  toggleSkill: vi.fn(),
  createCustomSkill: vi.fn(),
  updateCustomSkill: vi.fn(),
  deleteCustomSkill: vi.fn(),
}))

vi.mock('@/api/ai', () => skillsManageMocks)

vi.mock('@/stores/auth', () => ({
  useAuthStore: vi.fn(() => ({
    user: { role: 'owner' },
  })),
}))

describe('AE4: SkillsManagePage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    skillsManageMocks.getSkillsGrouped.mockReset()
    skillsManageMocks.getSkillsGrouped.mockResolvedValue({
      fixed: [], // backend returns empty fixed array per U1
      builtin: [
        { id: 'report', skill_type: 'builtin', is_enabled: true, display_order: 100 },
        { id: 'alerts', skill_type: 'builtin', is_enabled: true, display_order: 101 },
      ],
      custom: [],
    })
  })

  it('AE4: does NOT render the "固定技能" section', async () => {
    const SkillsManagePage = (await import('@/pages/SkillsManagePage.vue')).default
    const wrapper = mount(SkillsManagePage, {
      global: {
        plugins: [i18n],
        stubs: {
          PageHeader: true,
        },
      },
    })
    await flushPromises()
    // Structural check: there should be no van-cell-group with the fixed-skills
    // title. The fixed section's removal is what AE4 mandates; checking inner
    // text would hit Chinese strings in template comments.
    const cellGroups = wrapper.findAll('.van-cell-group')
    const titleAttrs = cellGroups.map((g) => g.attributes('title'))
    expect(titleAttrs).not.toContain('固定技能')
    expect(titleAttrs).toContain('内置技能')
  })

  it('AE4: renders no builtin skill rows (BUILTIN_CAPABILITIES deleted per T11)', async () => {
    const SkillsManagePage = (await import('@/pages/SkillsManagePage.vue')).default
    const wrapper = mount(SkillsManagePage, {
      global: {
        plugins: [i18n],
        stubs: {
          PageHeader: true,
        },
      },
    })
    await flushPromises()
    // T11: BUILTIN_CAPABILITIES deleted, builtinIds is empty, so the builtin
    // section renders no rows. Builtin skills are no longer family-toggleable
    // (is_enabled always True, no db row after family_skill_configs retirement).
    // The custom section is empty so only the "暂无数据" placeholder cell remains.
    const cells = wrapper.findAll('.van-cell')
    // 0 builtin rows + 1 noData placeholder in the custom section.
    expect(cells.length).toBe(1)
  })
})

// ── AE10: AgentFormPage read-only mode for system agents ──────────────────────

const agentFormMocks = vi.hoisted(() => ({
  getAgent: vi.fn(),
  getSkillsGrouped: vi.fn(),
}))

vi.mock('@/api/agent', () => ({
  getAgent: agentFormMocks.getAgent,
}))

const numinaAgentResponse = {
  id: 'numina-id',
  family_id: '0',
  agent_name: 'numina',
  display_name: '数鸣',
  description: '家庭财务大使',
  icon: '✨',
  color: '#8b5cf6',
  soul_md: '你是数鸣...',
  skills: ['*'],
  model: null,
  subagent_enabled: false,
  tool_groups: null,
  agent_type: 'system' as const,
  is_enabled: true,
  display_order: 15,
  can_edit: true,
  can_delete: false,
  created_by: null,
  created_at: '2026-05-27T00:00:00Z',
  updated_at: '2026-05-27T00:00:00Z',
}

describe('AE10: AgentFormPage read-only for numina', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    agentFormMocks.getAgent.mockReset()
    agentFormMocks.getAgent.mockResolvedValue(numinaAgentResponse)
    skillsManageMocks.getSkillsGrouped.mockReset()
    skillsManageMocks.getSkillsGrouped.mockResolvedValue({
      fixed: [],
      builtin: [
        { id: 'report', skill_type: 'builtin', is_enabled: true, display_order: 100 },
      ],
      custom: [],
    })
  })

  it('AE10: shows the system-agent banner', async () => {
    mockParams.id = 'numina-id'
    const AgentFormPage = (await import('@/pages/AgentFormPage.vue')).default
    const wrapper = mount(AgentFormPage, {
      global: { plugins: [i18n] },
    })
    await flushPromises()

    // Banner should render with the system-agent lock text.
    const banner = wrapper.find('.van-notice-bar')
    expect(banner.exists()).toBe(true)
  })

  it('AE10: save button is removed from DOM (not just disabled)', async () => {
    mockParams.id = 'numina-id'
    const AgentFormPage = (await import('@/pages/AgentFormPage.vue')).default
    const wrapper = mount(AgentFormPage, {
      global: { plugins: [i18n] },
    })
    await flushPromises()

    // bottom-bar wraps the save button and is gated on !isSystemAgent.
    expect(wrapper.find('.bottom-bar').exists()).toBe(false)
  })
})

describe('AgentFormPage custom agent create/edit optimization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    skillsManageMocks.getSkillsGrouped.mockReset()
    skillsManageMocks.getSkillsGrouped.mockResolvedValue({
      fixed: [],
      builtin: [
        { id: 'report', skill_type: 'builtin', is_enabled: true, display_order: 100 },
        { id: 'alerts', skill_type: 'builtin', is_enabled: false, display_order: 101 },
      ],
      custom: [
        { id: 'custom-skill', name: '自定义技能', skill_type: 'custom', is_enabled: true, display_order: 102 },
      ],
    })
  })

  it('only shows enabled skills, checks them by default on create, and hides model/subagent fields', async () => {
    mockParams.id = ''
    const AgentFormPage = (await import('@/pages/AgentFormPage.vue')).default
    const wrapper = mount(AgentFormPage, {
      global: { plugins: [i18n] },
    })
    await flushPromises()

    // It should load and show only the enabled skills: 'report' and 'custom-skill' (not 'alerts')
    const groups = wrapper.findAll('.van-cell-group')
    const skillsGroup = groups.find(g => g.attributes('title') === '可用技能')
    expect(skillsGroup).toBeDefined()
    const cells = skillsGroup!.findAll('.van-cell, van-cell')
    expect(cells.length).toBe(2)

    // Verify icons are rendered. T11: skillIcons map is empty, so builtin
    // 'report' falls back to '✨'; custom-skill has no icon -> '✨' as well.
    const icons = skillsGroup!.findAll('.skill-icon')
    expect(icons.length).toBe(2)
    expect(icons[0].text()).toBe('✨')
    expect(icons[1].text()).toBe('✨')

    // Verify model field and subagent toggle cell-group are completely absent
    const fields = wrapper.findAll('.van-field')
    const hasModelField = fields.some(f => f.text().includes('模型'))
    expect(hasModelField).toBe(false)

    const switches = wrapper.findAll('.van-switch')
    expect(switches.length).toBe(0)
  })
})

