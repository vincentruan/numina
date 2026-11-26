/**
 * KnowledgeOcean3D component integration — WebGL gate, picking, pinch,
 * lifecycle and single-clock wiring. `three` is mocked with a spy so the
 * no-WebGL branch can prove the heavy module was never even imported.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import { ref, nextTick, defineComponent, KeepAlive, h } from 'vue'
import type {
  OceanDomain,
  OceanSubject,
} from '@/components/learning/KnowledgeOcean.vue'

const threeMock = vi.hoisted(() => ({
  importSpy: vi.fn(),
  renderers: [] as Array<{
    setSize: ReturnType<typeof vi.fn>
    setPixelRatio: ReturnType<typeof vi.fn>
    render: ReturnType<typeof vi.fn>
    dispose: ReturnType<typeof vi.fn>
    forceContextLoss: ReturnType<typeof vi.fn>
  }>,
}))

vi.mock('three', async (importOriginal) => {
  threeMock.importSpy()
  const actual = await importOriginal<typeof import('three')>()

  class FakeWebGLRenderer {
    setSize = vi.fn()
    setPixelRatio = vi.fn()
    render = vi.fn()
    dispose = vi.fn()
    forceContextLoss = vi.fn()
    shadowMap = { enabled: false }
    domElement: unknown
    constructor(options: { canvas?: unknown } = {}) {
      this.domElement = options.canvas
      threeMock.renderers.push(this)
    }
  }

  return { ...actual, WebGLRenderer: FakeWebGLRenderer }
})

const driverMock = vi.hoisted(() => ({ tickDriver: vi.fn() }))
vi.mock('@/motion/animeDriver', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/motion/animeDriver')>()
  return { ...actual, tickDriver: driverMock.tickDriver }
})

const { isWebGLAvailable } = vi.hoisted(() => ({
  isWebGLAvailable: vi.fn(() => true),
}))
vi.mock('@/composables/useWebGLAvailable', () => ({ isWebGLAvailable }))

const { cameraFactory, cameraInstances } = vi.hoisted(() => {
  const instances: Array<{
    diveTo: ReturnType<typeof vi.fn>
    ascend: ReturnType<typeof vi.fn>
    reset: ReturnType<typeof vi.fn>
    dispose: ReturnType<typeof vi.fn>
  }> = []
  return {
    cameraInstances: instances,
    cameraFactory: vi.fn(() => {
      const controller = {
        diveTo: vi.fn().mockResolvedValue(undefined),
        ascend: vi.fn().mockResolvedValue(undefined),
        reset: vi.fn().mockResolvedValue(undefined),
        dispose: vi.fn(),
      }
      instances.push(controller)
      return controller
    }),
  }
})
vi.mock('../OceanCameraController', () => ({
  createOceanCameraController: cameraFactory,
}))

import * as THREE from 'three'
import KnowledgeOcean3D from '../KnowledgeOcean3D.vue'

const subjects: OceanSubject[] = [
  {
    id: 'math',
    terrain: 'logic',
    displayName: 'Math',
    icon: '📐',
    topicCount: 3,
    masteryRatio: 0.5,
  },
]
const domains: OceanDomain[] = [
  {
    id: 'math:fractions',
    subject: 'math',
    domain: 'fractions',
    displayName: 'Fractions',
    topicCount: 2,
    masteryRatio: 0.25,
  },
]

const rafCallbacks: FrameRequestCallback[] = []
let rafId = 0
let frameTime = 0
let documentHidden = false

function makeI18n(): ReturnType<typeof createI18n> {
  return createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN },
  })
}

function setSize(element: HTMLElement, width: number, height: number): void {
  Object.defineProperty(element, 'clientWidth', {
    configurable: true,
    value: width,
  })
  Object.defineProperty(element, 'clientHeight', {
    configurable: true,
    value: height,
  })
  vi.spyOn(element, 'getBoundingClientRect').mockReturnValue({
    left: 0,
    top: 0,
    width,
    height,
    right: width,
    bottom: height,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  })
}

async function mountComponent(
  props: Record<string, unknown> = {},
): Promise<VueWrapper> {
  const wrapper = mount(KnowledgeOcean3D, {
    props: {
      subjects,
      domains,
      selectedSubject: '',
      selectedDomain: '',
      selectedTopicLevel: false,
      ...props,
    },
    global: { plugins: [makeI18n()] },
  })
  setSize(wrapper.find('.knowledge-ocean-3d').element as HTMLElement, 400, 300)
  setSize(wrapper.find('canvas').element as HTMLElement, 400, 300)
  await flushPromises()
  await flushPromises()
  return wrapper
}

/** Mount inside KeepAlive so onActivated/onDeactivated fire for real. */
async function mountKeepAlive() {
  const show = ref(true)
  const Host = defineComponent({
    setup() {
      return () =>
        h(KeepAlive, null, {
          default: () =>
            show.value
              ? [
                  h(KnowledgeOcean3D, {
                    subjects,
                    domains,
                    selectedSubject: '',
                    selectedDomain: '',
                    selectedTopicLevel: false,
                  }),
                ]
              : [],
        })
    },
  })
  const host = mount(Host, { global: { plugins: [makeI18n()] } })
  const canvas = host.find('canvas')
  setSize(canvas.element as HTMLElement, 400, 300)
  await flushPromises()
  await flushPromises()
  return { host, show }
}

function touchEvent(
  type: string,
  touches: Array<{ clientX: number; clientY: number }>,
): Event {
  const event = new Event(type, { bubbles: true, cancelable: true })
  Object.defineProperty(event, 'touches', { value: touches })
  Object.defineProperty(event, 'changedTouches', { value: touches })
  return event
}

function stubHit(userData: Record<string, unknown>): void {
  const group = new THREE.Group()
  group.userData = userData
  const mesh = new THREE.Mesh()
  mesh.userData = userData
  mesh.parent = group
  vi.spyOn(THREE.Raycaster.prototype, 'intersectObjects').mockReturnValue([
    {
      object: mesh,
      distance: 1,
      point: new THREE.Vector3(),
      face: null,
      faceIndex: 0,
      uv: undefined,
      normal: undefined,
      instanceId: undefined,
    },
  ])
}

function runFrames(count: number): void {
  for (let i = 0; i < count; i++) {
    const callbacks = rafCallbacks.splice(0)
    frameTime += 16
    for (const callback of callbacks) callback(frameTime)
  }
}

beforeEach(() => {
  threeMock.renderers.length = 0
  cameraInstances.length = 0
  isWebGLAvailable.mockReturnValue(true)
  rafCallbacks.length = 0
  rafId = 0
  frameTime = 0
  vi.useFakeTimers()
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    rafCallbacks.push(callback)
    return ++rafId
  })
  vi.stubGlobal('cancelAnimationFrame', (id: number) => {
    const index = rafCallbacks.findIndex((_, i) => i + 1 === id)
    if (index >= 0) rafCallbacks.splice(index, 1)
  })
  class MockResizeObserver {
    observe = vi.fn()
    disconnect = vi.fn()
    constructor(public callback: ResizeObserverCallback) {}
  }
  vi.stubGlobal('ResizeObserver', MockResizeObserver)
  documentHidden = false
  Object.defineProperty(document, 'hidden', {
    configurable: true,
    get: () => documentHidden,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
  documentHidden = false
})

describe('KnowledgeOcean3D', () => {
  it('emits fallback with a friendly message and never imports three when WebGL is unavailable', async () => {
    isWebGLAvailable.mockReturnValue(false)
    threeMock.importSpy.mockClear()

    const wrapper = mount(KnowledgeOcean3D, {
      props: {
        subjects,
        domains,
        selectedSubject: '',
        selectedDomain: '',
        selectedTopicLevel: false,
      },
      global: { plugins: [makeI18n()] },
    })
    await flushPromises()

    expect(wrapper.emitted('fallback')).toHaveLength(1)
    expect(wrapper.text()).toContain('3D')
    expect(threeMock.importSpy).not.toHaveBeenCalled()
    expect(wrapper.find('canvas').exists()).toBe(false)
    wrapper.unmount()
  })

  it('mounts the scene with one renderer and one camera controller', async () => {
    const wrapper = await mountComponent()
    expect(threeMock.renderers).toHaveLength(1)
    expect(cameraFactory).toHaveBeenCalled()
    expect(threeMock.renderers).toHaveLength(1)
    expect(wrapper.emitted('fallback')).toBeUndefined()
    wrapper.unmount()
  })

  it('renders exactly once per frame with one clock tick (no component-side clock)', async () => {
    const wrapper = await mountComponent()
    const renderer = threeMock.renderers[0]

    expect(renderer.render).not.toHaveBeenCalled()
    runFrames(3)

    expect(renderer.render).toHaveBeenCalledTimes(3)
    expect(driverMock.tickDriver).toHaveBeenCalledTimes(3)
    wrapper.unmount()
  })

  it('emits selectSubject and oceanNavigation on island dblclick and dives to it', async () => {
    const wrapper = await mountComponent()
    stubHit({ islandId: 'math', type: 'island' })
    await wrapper
      .find('canvas')
      .trigger('dblclick', { clientX: 200, clientY: 150 })
    runFrames(1)

    expect(wrapper.emitted('selectSubject')?.[0]).toEqual(['math'])
    expect(wrapper.emitted('oceanNavigation')?.[0]).toEqual([
      expect.objectContaining({
        id: 'math',
        x: expect.any(Number),
        z: expect.any(Number),
        worldRadius: expect.any(Number),
      }),
    ])
    expect(cameraInstances[0].diveTo).toHaveBeenCalledWith(
      expect.objectContaining({
        x: expect.any(Number),
        z: expect.any(Number),
        worldRadius: expect.any(Number),
      }),
    )
    expect(wrapper.emitted('previewSubject')).toBeUndefined()
    wrapper.unmount()
  })

  it('emits previewSubject and interacted on single pointerup', async () => {
    const wrapper = await mountComponent()
    stubHit({ islandId: 'math', type: 'island' })

    await wrapper
      .find('canvas')
      .trigger('pointerup', { clientX: 200, clientY: 150 })
    runFrames(1)

    expect(wrapper.emitted('previewSubject')?.[0]).toEqual(['math'])
    expect(wrapper.emitted('interacted')).toHaveLength(1)
    expect(wrapper.emitted('selectSubject')).toBeUndefined()
    wrapper.unmount()
  })

  it('emits selectDomain with subject and domain on a domain-level dblclick', async () => {
    const wrapper = await mountComponent({ selectedSubject: 'math' })
    stubHit({ domainId: 'math:fractions', subject: 'math', type: 'domain' })

    await wrapper
      .find('canvas')
      .trigger('dblclick', { clientX: 200, clientY: 150 })
    runFrames(1)

    expect(wrapper.emitted('selectDomain')?.[0]).toEqual([
      { subject: 'math', domain: 'math:fractions' },
    ])
    expect(wrapper.emitted('oceanNavigation')).toHaveLength(1)
    wrapper.unmount()
  })

  it('emits zoomOut on pinch-out and ascends to L0', async () => {
    const wrapper = await mountComponent()
    const canvas = wrapper.find('canvas').element

    canvas.dispatchEvent(
      touchEvent('touchstart', [
        { clientX: 90, clientY: 100 },
        { clientX: 110, clientY: 100 },
      ]),
    )
    canvas.dispatchEvent(
      touchEvent('touchmove', [
        { clientX: 60, clientY: 100 },
        { clientX: 140, clientY: 100 },
      ]),
    )
    canvas.dispatchEvent(touchEvent('touchend', []))

    expect(wrapper.emitted('zoomOut')).toHaveLength(1)
    expect(cameraInstances[0].ascend).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('oceanNavigation')?.[0]).toEqual([null])
    wrapper.unmount()
  })

  it('does not pick in topic view mode', async () => {
    const wrapper = await mountComponent({ selectedTopicLevel: true })
    stubHit({ islandId: 'math', type: 'island' })

    await wrapper
      .find('canvas')
      .trigger('dblclick', { clientX: 200, clientY: 150 })

    expect(wrapper.emitted('selectSubject')).toBeUndefined()
    expect(THREE.Raycaster.prototype.intersectObjects).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('stops the loop and emits fallback once on webglcontextlost without resuming', async () => {
    const wrapper = await mountComponent()
    const renderer = threeMock.renderers[0]
    runFrames(2)
    expect(renderer.render).toHaveBeenCalledTimes(2)

    wrapper
      .find('canvas')
      .element.dispatchEvent(
        new Event('webglcontextlost', { bubbles: true, cancelable: true }),
      )
    expect(wrapper.emitted('fallback')).toHaveLength(1)

    runFrames(2)
    expect(renderer.render).toHaveBeenCalledTimes(2)

    // A later activation must not resurrect a lost context.
    ;(wrapper.vm as unknown as { onActivated?: () => void }).onActivated?.()
    runFrames(2)
    expect(renderer.render).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('fallback')).toHaveLength(1)
    wrapper.unmount()
  })

  it('pauses on deactivate/hidden and resumes on activate/visible', async () => {
    const { host, show } = await mountKeepAlive()
    const renderer = threeMock.renderers[0]
    runFrames(2)
    renderer.render.mockClear()

    show.value = false
    await nextTick()
    runFrames(3)
    expect(renderer.render.mock.calls.length).toBe(0)

    show.value = true
    await nextTick()
    runFrames(2)
    expect(renderer.render.mock.calls.length).toBe(2)

    documentHidden = true
    document.dispatchEvent(new Event('visibilitychange'))
    runFrames(2)
    expect(renderer.render.mock.calls.length).toBe(2)

    documentHidden = false
    document.dispatchEvent(new Event('visibilitychange'))
    runFrames(2)
    expect(renderer.render.mock.calls.length).toBe(4)
    host.unmount()
  })

  it('exposes resetCamera and diveTo and disposes everything on unmount', async () => {
    const wrapper = await mountComponent()
    const exposed = wrapper.vm as unknown as {
      resetCamera(): Promise<void>
      diveTo(id: string): Promise<void>
    }

    await exposed.resetCamera()
    expect(cameraInstances[0].reset).toHaveBeenCalledTimes(1)

    await exposed.diveTo('math')
    expect(cameraInstances[0].diveTo).toHaveBeenCalledTimes(1)

    wrapper.unmount()
    expect(threeMock.renderers[0].dispose).toHaveBeenCalledTimes(1)
    expect(cameraInstances[0].dispose).toHaveBeenCalledTimes(1)
    runFrames(2)
    expect(threeMock.renderers[0].render).toHaveBeenCalledTimes(0)
  })
})
