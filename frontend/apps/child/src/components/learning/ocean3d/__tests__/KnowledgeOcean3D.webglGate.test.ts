/**
 * WebGL-gate regression: this file has no static `three` or component
 * import. It verifies the lazy-loading contract two ways:
 *  1. Source inspection: the SFC has no static VALUE import from `three`
 *     (only `import type`), so the heavy module cannot load eagerly.
 *  2. Runtime: with WebGL unavailable, the dynamically imported level
 *     camera controller module is never evaluated and fallback is emitted.
 */
import { readFileSync } from 'node:fs'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'

const gate = vi.hoisted(() => ({
  isWebGLAvailable: vi.fn(() => false),
  controllerImportSpy: vi.fn(),
}))

vi.mock('@/composables/useWebGLAvailable', () => ({
  isWebGLAvailable: gate.isWebGLAvailable,
}))
vi.mock('../OceanCameraController', () => {
  gate.controllerImportSpy()
  return { createOceanCameraController: vi.fn() }
})
// Scene modules import `three` at module scope in the real app; stubbing
// them keeps this test focused on the component's own import contract.
vi.mock('../OceanSceneBuilder', () => ({ buildOceanScene: vi.fn() }))
vi.mock('../OceanWater', () => ({ createOceanWater: vi.fn() }))
vi.mock('../OceanLabels', () => ({ createOceanLabels: vi.fn() }))

let KnowledgeOcean3D: typeof import('../KnowledgeOcean3D.vue').default
let componentLoaded = false

beforeEach(async () => {
  gate.isWebGLAvailable.mockReturnValue(false)
  if (!componentLoaded) {
    gate.controllerImportSpy.mockClear()
    const module = await import('../KnowledgeOcean3D.vue')
    KnowledgeOcean3D = module.default
    componentLoaded = true
  }
  gate.controllerImportSpy.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('KnowledgeOcean3D WebGL gate', () => {
  it('has no static value import of three and dynamically imports it only after WebGL detection', () => {
    const source = readFileSync(
      `${process.cwd()}/src/components/learning/ocean3d/KnowledgeOcean3D.vue`,
      'utf8',
    )
    // Every static clause that ends in `from 'three'` must be `import type`.
    const importStarts = [...source.matchAll(/^import\s/gm)].map(
      (match) => match.index ?? 0,
    )
    const threeSources = [...source.matchAll(/from\s+['"]three['"]/g)].map(
      (match) => match.index ?? 0,
    )
    expect(threeSources.length).toBeGreaterThan(0)
    for (const threeStart of threeSources) {
      const ownImportStart = [...importStarts]
        .reverse()
        .find((index) => index < threeStart)
      expect(ownImportStart).toBeDefined()
      expect(source.slice(ownImportStart, threeStart)).toMatch(
        /^import\s+type\b/,
      )
    }
    expect(source).toContain("await import('three')")
  })

  it('emits fallback with a friendly message and never loads the camera module when WebGL is unavailable', async () => {
    const wrapper = mount(KnowledgeOcean3D, {
      props: {
        subjects: [],
        domains: [],
        selectedSubject: '',
        selectedDomain: '',
        selectedTopicLevel: false,
      },
      global: {
        plugins: [
          createI18n({
            legacy: false,
            locale: 'zh-CN',
            messages: { 'zh-CN': zhCN },
          }),
        ],
      },
    })
    await flushPromises()

    expect(gate.isWebGLAvailable).toHaveBeenCalled()
    expect(wrapper.emitted('fallback')).toHaveLength(1)
    expect(wrapper.text()).toContain('3D')
    expect(wrapper.find('canvas').exists()).toBe(false)
    expect(gate.controllerImportSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
