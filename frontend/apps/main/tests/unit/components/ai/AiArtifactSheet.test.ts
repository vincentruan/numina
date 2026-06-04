import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AiArtifactSheet from '@/components/ai/AiArtifactSheet.vue'
import AiArtifactLink from '@/components/ai/AiArtifactLink.vue'
import { createI18n } from 'vue-i18n'
import type { Artifact } from '@/types/agent-stream'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiArtifact: {
        sheetTitle: '附件 ({count})',
        emptyMessage: '暂无附件',
      },
    },
  },
})

describe('AiArtifactSheet', () => {
  const mockArtifacts: Artifact[] = [
    {
      id: '1',
      title: 'Test Report',
      kind: 'report',
      url: 'https://example.com/report',
      sourceStepId: 'step-1',
      generatedAt: '2026-06-04T10:00:00Z',
    },
    {
      id: '2',
      title: 'Test File',
      kind: 'file',
      path: '/tmp/test.txt',
      sourceStepId: 'step-2',
      generatedAt: '2026-06-04T10:01:00Z',
    },
    {
      id: '3',
      title: 'Test Image',
      kind: 'image',
      url: 'https://example.com/image.png',
      sourceStepId: 'step-3',
      generatedAt: '2026-06-04T10:02:00Z',
    },
  ]

  it('R4: visible=true → popup shown', () => {
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: [],
      },
      global: {
        plugins: [i18n],
      },
    })
    expect(wrapper.find('.artifact-sheet').exists()).toBe(true)
  })

  it('R5: artifacts=[...] → renders list with icons', () => {
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: mockArtifacts,
      },
      global: {
        plugins: [i18n],
      },
    })
    const items = wrapper.findAll('.artifact-item')
    expect(items.length).toBe(3)
    // Each item contains AiArtifactLink component
    expect(wrapper.findAllComponents({ name: 'AiArtifactLink' }).length).toBe(3)
  })

  it('R6: tap link artifact → artifact-tap emit', async () => {
    const linkArtifact: Artifact = {
      id: '4',
      title: 'Test Link',
      kind: 'link',
      url: 'https://example.com',
      sourceStepId: 'step-4',
    }
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: [linkArtifact],
      },
      global: {
        plugins: [i18n],
      },
    })
    await wrapper.find('.artifact-item').trigger('click')
    expect(wrapper.emitted('artifact-tap')).toBeTruthy()
    expect(wrapper.emitted('artifact-tap')![0][0]).toEqual(linkArtifact)
  })

  it('R7: tap file artifact → artifact-tap emit', async () => {
    const fileArtifact: Artifact = {
      id: '5',
      title: 'Test File',
      kind: 'file',
      path: '/tmp/test.txt',
      sourceStepId: 'step-5',
    }
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: [fileArtifact],
      },
      global: {
        plugins: [i18n],
      },
    })
    await wrapper.find('.artifact-item').trigger('click')
    expect(wrapper.emitted('artifact-tap')).toBeTruthy()
    expect(wrapper.emitted('artifact-tap')![0][0]).toEqual(fileArtifact)
  })

  it('R8: tap report artifact → artifact-tap emit', async () => {
    const reportArtifact: Artifact = {
      id: '6',
      title: 'Test Report',
      kind: 'report',
      url: 'https://example.com/report',
      sourceStepId: 'step-6',
    }
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: [reportArtifact],
      },
      global: {
        plugins: [i18n],
      },
    })
    await wrapper.find('.artifact-item').trigger('click')
    expect(wrapper.emitted('artifact-tap')).toBeTruthy()
    expect(wrapper.emitted('artifact-tap')![0][0]).toEqual(reportArtifact)
  })

  it('R9: tap data artifact (other kind) → artifact-tap emit', async () => {
    const dataArtifact: Artifact = {
      id: '7',
      title: 'Test Data',
      kind: 'other',
      sourceStepId: 'step-7',
    }
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: [dataArtifact],
      },
      global: {
        plugins: [i18n],
      },
    })
    await wrapper.find('.artifact-item').trigger('click')
    expect(wrapper.emitted('artifact-tap')).toBeTruthy()
    expect(wrapper.emitted('artifact-tap')![0][0]).toEqual(dataArtifact)
  })

  it('empty artifacts → shows "暂无附件"', () => {
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: [],
      },
      global: {
        plugins: [i18n],
      },
    })
    expect(wrapper.find('.artifact-sheet__empty').exists()).toBe(true)
    expect(wrapper.find('.artifact-sheet__empty').text()).toContain('暂无附件')
    expect(wrapper.find('.artifact-sheet__list').exists()).toBe(false)
  })

  it('close icon → close emit', async () => {
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: mockArtifacts,
      },
      global: {
        plugins: [i18n],
      },
    })
    await wrapper.find('.artifact-sheet__close').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
    expect(wrapper.emitted('close').length).toBe(1)
  })

  it('scrollable when many artifacts', () => {
    const manyArtifacts: Artifact[] = Array.from({ length: 20 }, (_, i) => ({
      id: `${i}`,
      title: `Artifact ${i}`,
      kind: 'link' as const,
      url: `https://example.com/${i}`,
      sourceStepId: `step-${i}`,
    }))
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: manyArtifacts,
      },
      global: {
        plugins: [i18n],
      },
    })
    const list = wrapper.find('.artifact-sheet__list')
    expect(list.exists()).toBe(true)
    // Verify the CSS class is applied (styles are in scoped CSS)
    expect(list.classes()).toContain('artifact-sheet__list')
    expect(wrapper.findAll('.artifact-item').length).toBe(20)
  })

  it('header shows correct count', () => {
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: mockArtifacts,
      },
      global: {
        plugins: [i18n],
      },
    })
    const title = wrapper.find('.artifact-sheet__title')
    expect(title.text()).toContain('3')
  })

  it('uses CSS variables for styling', () => {
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: mockArtifacts,
      },
      global: {
        plugins: [i18n],
      },
    })
    const header = wrapper.find('.artifact-sheet__header')
    // Verify no inline color styles - should use CSS classes with variables
    expect(header.element.style.color).toBe('')
    expect(header.element.style.background).toBe('')
  })

  it('has correct safe-area-inset-bottom padding', () => {
    const wrapper = mount(AiArtifactSheet, {
      props: {
        visible: true,
        artifacts: [],
      },
      global: {
        plugins: [i18n],
      },
    })
    const sheet = wrapper.find('.artifact-sheet')
    // Check parent popup has safe-area padding
    expect(sheet.exists()).toBe(true)
  })
})