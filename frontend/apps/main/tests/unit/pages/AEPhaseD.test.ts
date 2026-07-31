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
        systemCapabilities: '系统能力',
        alwaysEnabled: '始终启用',
        builtin: {
          assetReport: { name: '家庭资产体检', description: '结构化分析' },
          financeCoach: { name: '财务处方建议', description: '优化建议' },
          wishAdvice: { name: '心愿储蓄建议', description: '储蓄分配' },
          dashboardNarrative: { name: '仪表盘月度叙事', description: '月度解读' },
          literacyWeeklyReport: { name: '儿童财商周报', description: '周度报告' },
          importParse: { name: '金融文档解析', description: '提取持仓' },
        },
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

  it('AE4: renders "系统能力" collapsible section (read-only builtin skills)', async () => {
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
    // The builtin section now shows a "系统能力" header (collapsible, read-only).
    // It replaces the old "内置技能" toggle section (removed per T11).
    const header = wrapper.find('.builtin-header')
    expect(header.exists()).toBe(true)
    expect(header.text()).toContain('系统能力')
  })

  it('AE4: builtin skills are collapsed by default and show 6 rows when expanded', async () => {
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
    // Collapsed by default: builtin-list is hidden via v-show
    const builtinList = wrapper.find('.builtin-list')
    expect(builtinList.exists()).toBe(true)
    // v-show sets display:none when false — check the hidden state
    expect(builtinList.element.getAttribute('style')).toContain('display: none')
    // Expand by clicking the header
    await wrapper.find('.builtin-header').trigger('click')
    // After expansion, 6 builtin skill cells should be visible
    const cells = wrapper.findAll('.builtin-list .van-cell')
    expect(cells.length).toBe(6)
    // Each cell should show "始终启用" tag (no toggle switch)
    const tags = wrapper.findAll('.always-enabled-tag')
    expect(tags.length).toBe(6)
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
    // Only the publish toggle is rendered for custom agents (model/subagent fields hidden)
    expect(switches.length).toBe(1)
  })
})

