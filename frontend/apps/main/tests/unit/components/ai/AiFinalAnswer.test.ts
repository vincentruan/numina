import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiFinalAnswer from '@/components/ai/AiFinalAnswer.vue'
import type { Artifact } from '@/types/agent-stream'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiProcess: {
        copy: '复制',
        regenerate: '重新生成',
        copySuccess: '✅ 已复制',
        copyFailed: '❌ 复制失败',
        artifactsTitle: '关联资源',
        openArtifact: '打开',
        copyPath: '复制路径',
        pathCopied: '✅ 已复制路径',
      },
    },
  },
})

function mountWith(props: any) {
  return mount(AiFinalAnswer, {
    props,
    global: { plugins: [i18n] },
  })
}

describe('AiFinalAnswer — streaming skeleton', () => {
  it('renders skeleton when streaming and no content', () => {
    const w = mountWith({ content: '', streaming: true })
    expect(w.find('.answer-skeleton').exists()).toBe(true)
    expect(w.find('.answer-content').exists()).toBe(false)
  })

  it('switches to markdown content the moment first token arrives', () => {
    const w = mountWith({ content: 'first', streaming: true })
    expect(w.find('.answer-skeleton').exists()).toBe(false)
    expect(w.find('.answer-content').exists()).toBe(true)
    expect(w.find('.answer-cursor').exists()).toBe(true)
  })

  it('shows neither skeleton nor cursor when not streaming', () => {
    const w = mountWith({ content: 'final answer', streaming: false })
    expect(w.find('.answer-skeleton').exists()).toBe(false)
    expect(w.find('.answer-cursor').exists()).toBe(false)
    expect(w.find('.answer-content').exists()).toBe(true)
  })
})

describe('AiFinalAnswer — report header', () => {
  it('does not render header by default', () => {
    const w = mountWith({ content: 'x' })
    expect(w.find('.answer-report-header').exists()).toBe(false)
  })

  it('renders header when isReport=true and reportTitle is set', () => {
    const w = mountWith({ content: 'x', isReport: true, reportTitle: 'Q3 报告' })
    expect(w.find('.answer-report-header').exists()).toBe(true)
    expect(w.find('.report-title').text()).toBe('Q3 报告')
  })

  it('omits the title element if reportTitle is missing', () => {
    const w = mountWith({ content: 'x', isReport: true })
    expect(w.find('.answer-report-header').exists()).toBe(false)
  })

  it('shows generatedAt meta when provided', () => {
    const w = mountWith({
      content: 'x',
      isReport: true,
      reportTitle: 'r',
      reportMeta: { generatedAt: '2026-05-25 10:00' },
    })
    expect(w.find('.report-meta').text()).toBe('2026-05-25 10:00')
  })
})

describe('AiFinalAnswer — artifact row', () => {
  const fixtures: Artifact[] = [
    { id: '1', title: 'Report PDF', kind: 'report', url: 'https://example.com/r.pdf' },
    { id: '2', title: 'Local data', kind: 'file', path: '/data/x.json' },
    { id: '3', title: 'Bare', kind: 'other' },
  ]

  it('does not render artifact section when artifacts is undefined', () => {
    const w = mountWith({ content: 'x', streaming: false })
    expect(w.find('.answer-artifacts').exists()).toBe(false)
  })

  it('does not render artifact section when artifacts is empty', () => {
    const w = mountWith({ content: 'x', streaming: false, artifacts: [] })
    expect(w.find('.answer-artifacts').exists()).toBe(false)
  })

  it('renders one AiArtifactLink per artifact when artifacts is non-empty', () => {
    const w = mountWith({ content: 'x', streaming: false, artifacts: fixtures })
    const items = w.findAll('.ai-artifact-link')
    expect(items).toHaveLength(3)
    expect(items[0].text()).toContain('Report PDF')
    expect(items[2].text()).toContain('Bare')
  })

  it('does not render artifact section while streaming', () => {
    const w = mountWith({ content: 'x', streaming: true, artifacts: fixtures })
    expect(w.find('.answer-artifacts').exists()).toBe(false)
  })
})
