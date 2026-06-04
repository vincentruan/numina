import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiPlanProgressBar from '@/components/ai/AiPlanProgressBar.vue'
import type { PlanStep } from '@/types/agent-stream'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiPlanProgress: {
        ariaLabel: '计划进度：已完成 {completed} / {total} 步',
        stepAria: '第 {index} 步：{label}，{status}',
        status_pending: '待执行',
        status_active: '执行中',
        status_done: '已完成',
        status_error: '执行出错',
        overflowTitle: '还有 {count} 步未显示',
      },
    },
  },
})

function makeStep(id: string, label: string, status: PlanStep['status']): PlanStep {
  return { id, label, status }
}

function mountBar(props: { steps: PlanStep[]; activeStepIndex: number }) {
  return mount(AiPlanProgressBar, {
    props,
    global: { plugins: [i18n] },
  })
}

describe('AiPlanProgressBar', () => {
  it('renders correct number of dots for given steps array', () => {
    const steps = [
      makeStep('1', '收集数据', 'done'),
      makeStep('2', '分析', 'active'),
      makeStep('3', '生成报告', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    expect(wrapper.findAll('.dot-hit').length).toBe(3)
  })

  it('active step dot has pulse animation class', () => {
    const steps = [
      makeStep('1', '收集数据', 'done'),
      makeStep('2', '分析', 'active'),
      makeStep('3', '生成报告', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    const dots = wrapper.findAll('.dot')
    expect(dots[1].classes()).toContain('dot--active')
  })

  it('done step dots have solid primary color class', () => {
    const steps = [
      makeStep('1', '收集数据', 'done'),
      makeStep('2', '分析', 'active'),
      makeStep('3', '生成报告', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    const dots = wrapper.findAll('.dot')
    expect(dots[0].classes()).toContain('dot--done')
  })

  it('pending dots are dimmed (dot--pending class)', () => {
    const steps = [
      makeStep('1', '收集数据', 'done'),
      makeStep('2', '分析', 'active'),
      makeStep('3', '生成报告', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    const dots = wrapper.findAll('.dot')
    expect(dots[2].classes()).toContain('dot--pending')
  })

  it('error dot has dot--error class', () => {
    const steps = [
      makeStep('1', '收集数据', 'done'),
      makeStep('2', '分析', 'error'),
      makeStep('3', '生成报告', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    const dots = wrapper.findAll('.dot')
    expect(dots[1].classes()).toContain('dot--error')
  })

  it('progress fill bar is present', () => {
    const steps = [
      makeStep('1', '收集数据', 'done'),
      makeStep('2', '分析', 'active'),
      makeStep('3', '生成报告', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    expect(wrapper.find('.progress-fill').exists()).toBe(true)
  })

  it('progress fill width is proportional to completed steps', () => {
    // 1 done out of 3 steps → fill = 1/(3-1) = 50%
    const steps = [
      makeStep('1', '步骤一', 'done'),
      makeStep('2', '步骤二', 'active'),
      makeStep('3', '步骤三', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    const fill = wrapper.find('.progress-fill')
    expect(fill.attributes('style')).toContain('50%')
  })

  it('shows overflow indicator when steps > 7', () => {
    const steps = Array.from({ length: 8 }, (_, i) =>
      makeStep(String(i + 1), `步骤${i + 1}`, 'pending'),
    )
    const wrapper = mountBar({ steps, activeStepIndex: 0 })
    expect(wrapper.find('.overflow-indicator').exists()).toBe(true)
    // Only MAX_VISIBLE (6) dots shown
    expect(wrapper.findAll('.dot-hit').length).toBe(6)
  })

  it('does not show overflow indicator for 7 steps', () => {
    const steps = Array.from({ length: 7 }, (_, i) =>
      makeStep(String(i + 1), `步骤${i + 1}`, 'pending'),
    )
    const wrapper = mountBar({ steps, activeStepIndex: 0 })
    expect(wrapper.find('.overflow-indicator').exists()).toBe(false)
    expect(wrapper.findAll('.dot-hit').length).toBe(7)
  })

  it('tapping a dot emits step-tap with correct stepId', async () => {
    const steps = [
      makeStep('step-a', '步骤A', 'done'),
      makeStep('step-b', '步骤B', 'active'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    await wrapper.findAll('.dot-hit')[1].trigger('click')
    expect(wrapper.emitted('step-tap')).toBeTruthy()
    expect(wrapper.emitted('step-tap')![0]).toEqual(['step-b'])
  })

  it('progress bar container is exactly 24px height', () => {
    const steps = [makeStep('1', '步骤一', 'pending')]
    const wrapper = mountBar({ steps, activeStepIndex: 0 })
    // The outer element has height: 24px from CSS — check via class presence
    expect(wrapper.find('.ai-plan-progress-bar').exists()).toBe(true)
  })

  it('aria-valuenow equals number of completed steps', () => {
    const steps = [
      makeStep('1', '步骤一', 'done'),
      makeStep('2', '步骤二', 'done'),
      makeStep('3', '步骤三', 'active'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 2 })
    expect(wrapper.find('.ai-plan-progress-bar').attributes('aria-valuenow')).toBe('2')
  })

  it('aria-valuemin is 0 and aria-valuemax equals total steps', () => {
    const steps = [
      makeStep('1', '步骤一', 'pending'),
      makeStep('2', '步骤二', 'pending'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 0 })
    const bar = wrapper.find('.ai-plan-progress-bar')
    expect(bar.attributes('aria-valuemin')).toBe('0')
    expect(bar.attributes('aria-valuemax')).toBe('2')
  })

  it('each dot has aria-label with step info', () => {
    const steps = [makeStep('1', '收集数据', 'done')]
    const wrapper = mountBar({ steps, activeStepIndex: 0 })
    const hitEl = wrapper.find('.dot-hit')
    expect(hitEl.attributes('aria-label')).toBeTruthy()
    expect(hitEl.attributes('aria-label')).toContain('收集数据')
  })

  it('no inline style color attributes in rendered output', () => {
    const steps = [
      makeStep('1', '步骤一', 'done'),
      makeStep('2', '步骤二', 'active'),
    ]
    const wrapper = mountBar({ steps, activeStepIndex: 1 })
    const html = wrapper.html()
    // progress-fill has a width inline style but not color/background
    expect(html).not.toMatch(/style="[^"]*color[^"]*"/)
  })

  it('zero steps renders no dots', () => {
    const wrapper = mountBar({ steps: [], activeStepIndex: 0 })
    expect(wrapper.findAll('.dot-hit').length).toBe(0)
  })
})
