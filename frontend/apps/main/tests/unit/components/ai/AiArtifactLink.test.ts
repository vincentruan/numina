import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiArtifactLink from '@/components/ai/AiArtifactLink.vue'
import type { Artifact } from '@/types/agent-stream'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiProcess: {
        openArtifact: '打开',
        copyPath: '复制路径',
        pathCopied: '✅ 已复制路径',
        copyFailed: '❌ 复制失败',
      },
    },
  },
})

function mountWith(artifact: Artifact) {
  return mount(AiArtifactLink, {
    props: { artifact },
    global: { plugins: [i18n] },
  })
}

describe('AiArtifactLink', () => {
  it('renders title', () => {
    const w = mountWith({ id: 'a1', title: 'Q3 资产报告' })
    expect(w.text()).toContain('Q3 资产报告')
  })

  it('renders Open button as <a> with secure attributes when url is present', () => {
    const w = mountWith({ id: 'a1', title: 'External', url: 'https://example.com' })
    const a = w.find('a')
    expect(a.exists()).toBe(true)
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toBe('noopener noreferrer')
    expect(a.text()).toBe('打开')
  })

  it('renders Copy-path button when only path is present', () => {
    const w = mountWith({ id: 'a1', title: 'Local file', path: '/data/report.pdf' })
    const btn = w.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('复制路径')
    expect(w.find('a').exists()).toBe(false)
  })

  it('renders no action when neither url nor path is present', () => {
    const w = mountWith({ id: 'a1', title: 'Bare artifact' })
    expect(w.find('a').exists()).toBe(false)
    expect(w.find('button').exists()).toBe(false)
  })

  it('applies kind-* class for known kinds', () => {
    expect(mountWith({ id: '1', title: 'r', kind: 'report' }).classes()).toContain('kind-report')
    expect(mountWith({ id: '1', title: 'f', kind: 'file' }).classes()).toContain('kind-file')
    expect(mountWith({ id: '1', title: 'i', kind: 'image' }).classes()).toContain('kind-image')
    expect(mountWith({ id: '1', title: 'l', kind: 'link' }).classes()).toContain('kind-link')
  })

  it('falls back to kind-other when kind is missing', () => {
    expect(mountWith({ id: '1', title: 'x' }).classes()).toContain('kind-other')
  })
})
