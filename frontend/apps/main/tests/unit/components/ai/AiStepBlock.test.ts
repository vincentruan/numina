import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiStepBlock from '@/components/ai/AiStepBlock.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiProcess: {
        stepReasoning: '思考',
        argsLabel: '参数：',
        statusDone: '已完成',
        reasoningDuration: '思考 {seconds}s',
        thinkingLabel: '思考中...',
      },
    },
  },
})

function mountWith(props: Record<string, unknown>) {
  return mount(AiStepBlock, {
    props: props as any,
    global: {
      plugins: [i18n],
      stubs: {
        'van-icon': { template: '<i class="van-icon" />' },
      },
    },
  })
}

describe('AiStepBlock', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders reasoning type with streaming status: shimmer and expanded', () => {
    const wrapper = mountWith({
      type: 'reasoning',
      id: 'r-1',
      status: 'streaming',
      content: '正在分析您的资产配置...',
      defaultExpanded: true,
    })

    expect(wrapper.find('.ai-step-block--streaming').exists()).toBe(true)
    expect(wrapper.find('.ai-step-block--active').exists()).toBe(true)
    expect(wrapper.find('.reasoning-content.body-streaming').exists()).toBe(true)
    expect(wrapper.text()).toContain('正在分析您的资产配置')
  })

  it('renders reasoning type with done status: static content, summary in header', () => {
    const wrapper = mountWith({
      type: 'reasoning',
      id: 'r-2',
      status: 'done',
      content: '您的总资产为150万元。其中金融资产占比较高，建议适当分散。',
      elapsedMs: 5000,
    })

    expect(wrapper.find('.ai-step-block--done').exists()).toBe(true)
    expect(wrapper.find('.ai-step-block--active').exists()).toBe(false)
    expect(wrapper.find('.step-summary').exists()).toBe(true)
  })

  it('renders tool_call type running: shows gradient border', () => {
    const wrapper = mountWith({
      type: 'tool_call',
      id: 'tc-1',
      status: 'running',
      name: 'get_assets',
      displayName: '查询资产',
      icon: '📊',
      args: { filter: 'all' },
    })

    expect(wrapper.find('.ai-step-block--active').exists()).toBe(true)
    expect(wrapper.find('.tool-args.args-running').exists()).toBe(true)
  })

  it('renders tool_call type done without compression: shows result', () => {
    const wrapper = mountWith({
      type: 'tool_call',
      id: 'tc-2',
      status: 'done',
      name: 'get_assets',
      displayName: '查询资产',
      icon: '📊',
      args: { filter: 'all' },
      resultSummary: '返回 5 条资产',
      compressed: false,
    })

    expect(wrapper.find('.tool-result.result-success').exists()).toBe(true)
    expect(wrapper.text()).toContain('返回 5 条资产')
  })

  it('renders tool_call type error: shows error message', () => {
    const wrapper = mountWith({
      type: 'tool_call',
      id: 'tc-3',
      status: 'error',
      name: 'get_assets',
      args: {},
      error: '查询超时',
    })

    expect(wrapper.find('.ai-step-block--error').exists()).toBe(true)
    expect(wrapper.find('.tool-result.result-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('查询超时')
  })

  it('compressed tool_call hides body content', () => {
    const wrapper = mountWith({
      type: 'tool_call',
      id: 'tc-4',
      status: 'done',
      name: 'get_assets',
      args: { filter: 'all' },
      resultSummary: '返回 5 条',
      compressed: true,
    })

    expect(wrapper.find('.ai-step-block--compressed').exists()).toBe(true)
  })

  it('aria-expanded attribute reflects actual expand state', async () => {
    const wrapper = mountWith({
      type: 'reasoning',
      id: 'r-3',
      status: 'done',
      content: '分析完成',
      defaultExpanded: true,
    })

    expect(wrapper.find('.ai-step-block').attributes('aria-expanded')).toBe('true')

    await wrapper.find('.step-header').trigger('click')
    expect(wrapper.find('.ai-step-block').attributes('aria-expanded')).toBe('false')
  })

  it('summary truncation: Chinese content ≤40 chars + …', () => {
    const longContent = '这是一段非常长的中文内容，用来测试摘要截断功能是否正常工作，应该在四十个字符左右截断然后加省略号'
    const wrapper = mountWith({
      type: 'reasoning',
      id: 'r-4',
      status: 'done',
      content: longContent,
    })

    const summaryEl = wrapper.find('.step-summary')
    expect(summaryEl.exists()).toBe(true)
    const summaryText = summaryEl.text()
    expect(summaryText.length).toBeLessThanOrEqual(41) // 40 chars + …
    expect(summaryText.endsWith('…')).toBe(true)
  })

  it('tool_call type without aria-expanded (not collapsible)', () => {
    const wrapper = mountWith({
      type: 'tool_call',
      id: 'tc-5',
      status: 'done',
      name: 'web_search',
      args: { query: 'test' },
    })

    expect(wrapper.find('.ai-step-block').attributes('aria-expanded')).toBeUndefined()
  })

  it('no inline style attributes for color/background in rendered output', () => {
    const wrapper = mountWith({
      type: 'reasoning',
      id: 'r-5',
      status: 'streaming',
      content: 'test',
    })

    const html = wrapper.html()
    expect(html).not.toMatch(/style="[^"]*background[^"]*"/)
    expect(html).not.toMatch(/style="[^"]*color[^"]*"/)
  })

  // Subagent tests
  it('subagent running: gradient border, title visible', () => {
    const wrapper = mountWith({
      type: 'subagent',
      id: 'sa-1',
      taskId: 'task-123',
      status: 'running',
      title: '分析负债',
      description: '正在分析您的负债结构',
    })

    expect(wrapper.find('.ai-step-block--active').exists()).toBe(true)
    expect(wrapper.text()).toContain('分析负债')
  })

  it('subagent done: static border, result visible', () => {
    const wrapper = mountWith({
      type: 'subagent',
      id: 'sa-2',
      taskId: 'task-456',
      status: 'done',
      title: '分析负债',
      result: '负债结构健康',
    })

    expect(wrapper.find('.ai-step-block--done').exists()).toBe(true)
    expect(wrapper.text()).toContain('负债结构健康')
  })

  it('subagent failed: red border, error visible', () => {
    const wrapper = mountWith({
      type: 'subagent',
      id: 'sa-3',
      taskId: 'task-789',
      status: 'failed',
      title: '分析负债',
      error: '数据不足',
    })

    expect(wrapper.find('.ai-step-block--failed').exists()).toBe(true)
    expect(wrapper.text()).toContain('数据不足')
  })

  // Artifact tests
  it('artifact: renders link with href and title', () => {
    const wrapper = mountWith({
      type: 'artifact',
      id: 'art-1',
      status: 'done',
      title: '资产报告',
      url: '/reports/asset.pdf',
      path: '/reports/asset.pdf',
    })

    expect(wrapper.find('.artifact-link').exists()).toBe(true)
    expect(wrapper.find('.artifact-link').attributes('href')).toBe('/reports/asset.pdf')
    expect(wrapper.text()).toContain('资产报告')
  })

  // Progress tests
  it('progress running: shows title and description', () => {
    const wrapper = mountWith({
      type: 'progress',
      id: 'pg-1',
      status: 'running',
      title: '生成报告',
      description: '正在整理数据',
    })

    expect(wrapper.find('.ai-step-block--active').exists()).toBe(true)
    expect(wrapper.text()).toContain('生成报告')
    expect(wrapper.text()).toContain('正在整理数据')
  })

  it('progress done: static state', () => {
    const wrapper = mountWith({
      type: 'progress',
      id: 'pg-2',
      status: 'done',
      title: '生成报告',
    })

    expect(wrapper.find('.ai-step-block--done').exists()).toBe(true)
    expect(wrapper.text()).toContain('生成报告')
  })

  // statusText computed property tests
  describe('tool_call statusText (dynamic from displayName)', () => {
    it('running status shows "正在<displayName>"', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'st-1',
        status: 'running',
        name: 'get_assets',
        displayName: '获取家庭概览',
        args: {},
      })

      expect(wrapper.find('.tool-status-text').text()).toBe('正在获取家庭概览')
    })

    it('running status falls back to name when displayName missing', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'st-2',
        status: 'running',
        name: 'web_search',
        args: {},
      })

      expect(wrapper.find('.tool-status-text').text()).toBe('正在web_search')
    })

    it('running status falls back to "处理" when both missing', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'st-3',
        status: 'running',
        args: {},
      })

      expect(wrapper.find('.tool-status-text').text()).toBe('正在处理')
    })

    it('done/error/streaming statuses do not render the running status text element', () => {
      const states = ['done', 'error', 'streaming'] as const
      for (const status of states) {
        const wrapper = mountWith({
          type: 'tool_call',
          id: `st-${status}`,
          status,
          name: 'get_assets',
          displayName: '获取家庭概览',
          args: {},
          resultSummary: 'ok',
        })

        expect(wrapper.find('.tool-status-text').exists()).toBe(false)
      }
    })
  })

  // args display condition tests
  describe('tool_call args display condition', () => {
    it('running status shows args even when compressed=true', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'ar-1',
        status: 'running',
        name: 'get_assets',
        args: { filter: 'all' },
        compressed: true,
      })

      expect(wrapper.find('.tool-args').exists()).toBe(true)
    })

    it('done status hides args by default (compressed=true, not expanded)', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'ar-2',
        status: 'done',
        name: 'get_assets',
        args: { filter: 'all' },
        resultSummary: 'ok',
        compressed: true,
      })

      expect(wrapper.find('.tool-args').exists()).toBe(false)
      expect(wrapper.find('.tool-result').exists()).toBe(true)
    })

    it('done status hides args by default in compressed mode', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'ar-3',
        status: 'done',
        name: 'get_assets',
        args: { filter: 'all' },
        resultSummary: 'ok',
        compressed: true,
      })

      expect(wrapper.find('.tool-args').exists()).toBe(false)
    })

    it('done status shows args when expanded (after user click)', async () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'ar-4',
        status: 'done',
        name: 'get_assets',
        args: { filter: 'all' },
        resultSummary: 'ok',
        compressed: true,
      })

      // expand by clicking header
      await wrapper.find('.step-header').trigger('click')
      expect(wrapper.find('.tool-args').exists()).toBe(true)
    })

    it('error status hides args by default in compressed mode', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'ar-5',
        status: 'error',
        name: 'get_assets',
        args: { filter: 'all' },
        error: '失败',
        compressed: true,
      })

      expect(wrapper.find('.tool-args').exists()).toBe(false)
      expect(wrapper.find('.tool-result.result-error').exists()).toBe(true)
    })

    it('args-label is hidden in compressed mode', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'ar-6',
        status: 'running',
        name: 'get_assets',
        args: { filter: 'all' },
        compressed: true,
      })

      expect(wrapper.find('.args-label').exists()).toBe(false)
      expect(wrapper.find('.args-value').exists()).toBe(true)
    })

    it('args-label is shown in non-compressed mode', () => {
      const wrapper = mountWith({
        type: 'tool_call',
        id: 'ar-7',
        status: 'running',
        name: 'get_assets',
        args: { filter: 'all' },
        compressed: false,
      })

      expect(wrapper.find('.args-label').exists()).toBe(true)
    })
  })
})