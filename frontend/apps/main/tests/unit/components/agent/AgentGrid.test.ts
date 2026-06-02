/**
 * AE integration tests for AgentGrid (Phase D / U16).
 *
 * Covers:
 * - AE1: owner sees system section rendered in correct order
 * - AE5: numina row in system section renders NuminaLogo (not emoji)
 * - AE11: non-owner with zero custom agents sees section title + van-empty,
 *   no create-placeholder card
 */
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import { createI18n } from 'vue-i18n'
import AgentGrid from '@/components/agent/AgentGrid.vue'
import type { Agent } from '@/types/agent'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      agents: {
        systemAgents: '系统智能体',
        customAgents: '我的智能体',
        apps: '应用',
        createAgent: '创建智能体',
        noCustomAgents: '还没有自定义智能体',
        consult: '立即咨询',
        chat: '对话',
        edit: '编辑',
      },
    },
  },
})

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: 'agent-id',
    family_id: '0',
    agent_name: 'test',
    display_name: 'Test',
    description: '',
    icon: '🤖',
    color: '#6366f1',
    soul_md: '',
    skills: [],
    model: null,
    subagent_enabled: false,
    tool_groups: null,
    agent_type: 'custom',
    is_enabled: true,
    display_order: 0,
    can_edit: true,
    can_delete: true,
    created_by: null,
    created_at: '2026-05-27T00:00:00Z',
    updated_at: '2026-05-27T00:00:00Z',
    ...overrides,
  }
}

const aiAssistant = makeAgent({
  id: 'ai-assistant-id',
  agent_name: 'ai-assistant',
  display_name: 'AI 问答',
  agent_type: 'system',
  can_edit: false,
  can_delete: false,
})

const numina = makeAgent({
  id: 'numina-id',
  agent_name: 'numina',
  display_name: '数鸣',
  icon: '✨',
  agent_type: 'system',
  can_edit: true,
  can_delete: false,
})

describe('AgentGrid — AE integration tests', () => {
  it('AE1: renders system agents in the systemAgents section', () => {
    const wrapper = mount(AgentGrid, {
      props: {
        systemAgents: [aiAssistant, numina],
        customAgents: [],
        showCreate: true,
      },
      global: { plugins: [i18n] },
    })
    const sectionTitles = wrapper.findAll('.agent-section__title').map((s) => s.text())
    expect(sectionTitles).toContain('系统智能体')
    expect(sectionTitles).toContain('我的智能体')
    // Render order: system before custom
    expect(sectionTitles[0]).toBe('系统智能体')

    const cards = wrapper.findAll('.agent-card')
    const cardNames = cards.map((c) => c.find('.agent-card__name').text())
    expect(cardNames).toContain('AI 问答')
    expect(cardNames).toContain('数鸣')
  })

  it('AE5: numina card renders NuminaLogo (not emoji)', () => {
    const wrapper = mount(AgentGrid, {
      props: {
        systemAgents: [numina],
        customAgents: [],
        showCreate: false,
      },
      global: { plugins: [i18n] },
    })
    // The numina agent card should contain an inline <svg> (NuminaLogo) and
    // NOT render its emoji fallback in the icon slot. AgentCard's branch on
    // agent_name === 'numina' is what produces this.
    const numinaCard = wrapper
      .findAll('.agent-card')
      .find((c) => c.find('.agent-card__name').text() === '数鸣')
    expect(numinaCard?.exists()).toBe(true)
    expect(numinaCard?.find('svg').exists()).toBe(true)
    // The emoji span should not be in the icon slot for numina.
    const iconSlot = numinaCard?.find('.agent-card__icon')
    expect(iconSlot?.text()).not.toContain('✨')
  })

  it('AE5 inverse: non-numina cards render emoji icon, not SVG', () => {
    const customAgent = makeAgent({
      id: 'custom-1',
      agent_name: 'my-agent',
      display_name: 'Custom Agent',
      icon: '🎯',
      agent_type: 'custom',
    })
    const wrapper = mount(AgentGrid, {
      props: {
        systemAgents: [],
        customAgents: [customAgent],
        showCreate: false,
      },
      global: { plugins: [i18n] },
    })
    const card = wrapper.find('.agent-card')
    const iconSlot = card.find('.agent-card__icon')
    expect(iconSlot.text()).toContain('🎯')
    // No NuminaLogo SVG for non-numina agents.
    expect(card.find('svg').exists()).toBe(false)
  })

  it('AE11: non-owner with zero custom agents sees section title and empty hint, no create card', () => {
    const wrapper = mount(AgentGrid, {
      props: {
        systemAgents: [aiAssistant, numina],
        customAgents: [],
        showCreate: false, // non-owner
      },
      global: { plugins: [i18n] },
    })
    // Custom section title still renders (R1 mandate).
    const sectionTitles = wrapper.findAll('.agent-section__title').map((s) => s.text())
    expect(sectionTitles).toContain('我的智能体')
    // van-empty placeholder visible for the empty state (test stub renders
    // .van-empty without inlining the description prop into text).
    expect(wrapper.find('.van-empty').exists()).toBe(true)
    // No create-placeholder card for non-owners.
    expect(wrapper.find('.agent-card--create').exists()).toBe(false)
  })

  it('owner with zero custom agents sees the create-placeholder card', () => {
    const wrapper = mount(AgentGrid, {
      props: {
        systemAgents: [aiAssistant, numina],
        customAgents: [],
        showCreate: true, // owner
      },
      global: { plugins: [i18n] },
    })
    expect(wrapper.find('.agent-card--create').exists()).toBe(true)
    // van-empty hint does NOT render when create card is shown.
    expect(wrapper.find('.van-empty').exists()).toBe(false)
  })

  it('handles zero system agents gracefully (no system section header)', () => {
    const wrapper = mount(AgentGrid, {
      props: {
        systemAgents: [],
        customAgents: [],
        showCreate: false,
      },
      global: { plugins: [i18n] },
    })
    // System section title should not render when systemAgents is empty.
    const sectionTitles = wrapper.findAll('.agent-section__title').map((s) => s.text())
    expect(sectionTitles).not.toContain('系统智能体')
    // Custom section still renders (always present per R1).
    expect(sectionTitles).toContain('我的智能体')
  })
})
