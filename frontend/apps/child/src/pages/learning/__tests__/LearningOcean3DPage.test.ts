/**
 * LearningOcean3DPage tests — data derivation, page-local navigation, states,
 * and route registration.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'

vi.mock('@/api/learning', () => ({
  getMyLearningMapIndex: vi.fn(),
  getTopicIndex: vi.fn(),
}))

const cameraSpies = vi.hoisted(() => ({
  resetCamera: vi.fn(() => Promise.resolve()),
  diveTo: vi.fn(() => Promise.resolve()),
}))

vi.mock('@/components/learning/ocean3d/KnowledgeOcean3D.vue', () => ({
  default: {
    name: 'KnowledgeOcean3D',
    template: '<div data-test="ocean3d" />',
    props: ['subjects', 'domains', 'selectedSubject', 'selectedDomain', 'selectedTopicLevel'],
    emits: [
      'previewSubject',
      'selectSubject',
      'previewDomain',
      'selectDomain',
      'zoomOut',
      'fallback',
      'interacted',
      'oceanNavigation',
    ],
    methods: cameraSpies,
  },
}))

vi.mock('@/components/learning/TopicConstellation.vue', () => ({
  default: {
    name: 'TopicConstellation',
    template: `
      <svg data-test="constellation">
        <g v-for="topic in topics" :key="topic.id" :data-test="'topic-' + topic.id" @click="$emit('selectTopic', { id: topic.id })" />
      </svg>
    `,
    props: ['topics', 'edges', 'viewWidth', 'viewHeight'],
    emits: ['selectTopic'],
  },
}))

import * as learningApi from '@/api/learning'
import LearningOcean3DPage from '../LearningOcean3DPage.vue'

const mockIndex = vi.mocked(learningApi.getMyLearningMapIndex)
const mockTopics = vi.mocked(learningApi.getTopicIndex)

function progressRow(topicId: string, mastery: string) {
  return {
    topic_id: topicId,
    mastery_level: mastery,
    next_review_at: null,
    subject: 'mathematics',
    domain: 'fractions',
  }
}

function topicRow(id: string, subject: string, domain: string, name: string, nameZh: string) {
  return { id, subject, domain, name, name_zh: nameZh, age_group: 'mid' }
}

const indexRows = [
  topicRow('t1', 'mathematics', 'fractions', 'Fractions', '分数'),
  topicRow('t2', 'mathematics', 'fractions', 'Decimals', '小数'),
  topicRow('t3', 'mathematics', 'geometry', 'Shapes', '图形'),
  topicRow('t4', 'science', 'space', 'Planets', '行星'),
]

const progressRows = [
  progressRow('t1', 'mastered'),
  progressRow('t2', 'learning'),
  progressRow('t4', 'mastered'),
]

function makeI18n(locale = 'zh-CN') {
  return createI18n({
    legacy: false,
    locale,
    messages: { 'zh-CN': zhCN, 'en-US': enUS },
  })
}

async function mountPage(locale = 'zh-CN') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/learning/ocean-3d', component: LearningOcean3DPage },
      { path: '/learning/topic/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/learning/ocean-3d')
  await router.isReady()

  const wrapper: VueWrapper = mount(LearningOcean3DPage, {
    global: { plugins: [router, makeI18n(locale)] },
  })
  return { wrapper, router }
}

async function settled(wrapper: VueWrapper) {
  await vi.waitFor(() => {
    expect(wrapper.find('[data-test="ocean3d"]').exists()).toBe(true)
  })
  await wrapper.vm.$nextTick()
}

describe('LearningOcean3DPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIndex.mockResolvedValue(progressRows)
    mockTopics.mockResolvedValue(indexRows)
  })

  it('derives subjects and domains from two index calls with progress-row mastery', async () => {
    const { wrapper } = await mountPage()
    await settled(wrapper)

    expect(mockIndex).toHaveBeenCalledTimes(1)
    expect(mockTopics).toHaveBeenCalledTimes(1)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    const subjects = ocean.props('subjects') as Array<{
      id: string
      displayName: string
      masteryRatio: number
      topicCount: number
      icon: string
      terrain: string
    }>
    expect(subjects.map((s) => s.id).sort()).toEqual(['mathematics', 'science'])
    const math = subjects.find((s) => s.id === 'mathematics')
    expect(math).toMatchObject({ topicCount: 3, masteryRatio: 1 / 3, icon: '📐', terrain: 'math' })
    expect(math?.displayName).toBe('数学')

    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()

    const domains = ocean.props('domains') as Array<{
      id: string
      subject: string
      domain: string
      topicCount: number
      masteryRatio: number
    }>
    expect(domains).toHaveLength(2)
    expect(domains.find((d) => d.domain === 'fractions')).toMatchObject({
      id: 'mathematics:fractions',
      subject: 'mathematics',
      topicCount: 2,
      masteryRatio: 0.5,
    })
    expect(domains.find((d) => d.domain === 'geometry')).toMatchObject({
      topicCount: 1,
      masteryRatio: 0,
    })
    expect(ocean.props('selectedSubject')).toBe('mathematics')
  })

  it('localizes topic names via useLocalizedTopic and keeps edges empty', async () => {
    const { wrapper } = await mountPage()
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()
    ocean.vm.$emit('selectDomain', { subject: 'mathematics', domain: 'mathematics:fractions' })
    await wrapper.vm.$nextTick()

    const constellation = wrapper.findComponent({ name: 'TopicConstellation' })
    expect(constellation.exists()).toBe(true)
    expect(constellation.props('topics')).toEqual([
      { id: 't1', displayName: '分数', masteryLevel: 'mastered' },
      { id: 't2', displayName: '小数', masteryLevel: 'learning' },
    ])
    expect(constellation.props('edges')).toEqual([])
    expect(constellation.props('viewWidth')).toBeGreaterThan(0)
    expect(constellation.props('viewHeight')).toBeGreaterThan(0)

    ocean.vm.$emit('selectDomain', { subject: 'mathematics', domain: '__other__' })
    await wrapper.vm.$nextTick()
    expect(constellation.props('topics')).toEqual([])
  })

  it('shows the 2D topic layer on domain click without navigating, then returns to 3D L1', async () => {
    const { wrapper, router } = await mountPage()
    const push = vi.spyOn(router, 'push')
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()
    ocean.vm.$emit('selectDomain', { subject: 'mathematics', domain: 'mathematics:fractions' })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="constellation"]').exists()).toBe(true)
    expect(ocean.props('selectedTopicLevel')).toBe(true)
    expect(ocean.props('selectedSubject')).toBe('mathematics')
    expect(ocean.props('selectedDomain')).toBe('fractions')
    expect(wrapper.findComponent({ name: 'TopicConstellation' }).props('topics')).toEqual([
      { id: 't1', displayName: '分数', masteryLevel: 'mastered' },
      { id: 't2', displayName: '小数', masteryLevel: 'learning' },
    ])
    expect(push).not.toHaveBeenCalled()

    await wrapper.find('[data-test="ocean3d-back"]').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('[data-test="constellation"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="ocean3d"]').exists()).toBe(true)
    expect(ocean.props('selectedSubject')).toBe('mathematics')
    expect(ocean.props('selectedTopicLevel')).toBe(false)
  })

  it('pinch-out on the opaque 2D topic layer returns all the way to L0', async () => {
    const { wrapper } = await mountPage()
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()
    ocean.vm.$emit('selectDomain', {
      subject: 'mathematics',
      domain: 'mathematics:fractions',
    })
    await wrapper.vm.$nextTick()
    expect(ocean.props('selectedTopicLevel')).toBe(true)

    const layer = wrapper.find('[data-test="ocean3d-topic-layer"]')
    const touch = (x: number, y: number) => ({ clientX: x, clientY: y })
    await layer.trigger('touchstart', { touches: [touch(100, 100), touch(200, 100)] })
    await layer.trigger('touchmove', { touches: [touch(60, 100), touch(280, 100)] })
    await layer.trigger('touchend', { touches: [] })
    await wrapper.vm.$nextTick()

    expect(ocean.props('selectedSubject')).toBe('')
    expect(ocean.props('selectedDomain')).toBe('')
    expect(ocean.props('selectedTopicLevel')).toBe(false)
    expect(cameraSpies.resetCamera).toHaveBeenCalledTimes(1)
  })

  it('single-finger moves on the 2D topic layer do not reset the camera', async () => {
    const { wrapper } = await mountPage()
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()
    ocean.vm.$emit('selectDomain', {
      subject: 'mathematics',
      domain: 'mathematics:fractions',
    })
    await wrapper.vm.$nextTick()

    const layer = wrapper.find('[data-test="ocean3d-topic-layer"]')
    await layer.trigger('touchstart', { touches: [{ clientX: 100, clientY: 100 }] })
    await layer.trigger('touchmove', { touches: [{ clientX: 160, clientY: 120 }] })
    await layer.trigger('touchend', { touches: [] })
    await wrapper.vm.$nextTick()

    expect(ocean.props('selectedTopicLevel')).toBe(true)
    expect(cameraSpies.resetCamera).not.toHaveBeenCalled()
  })

  it('routes topic selection to the existing 2D topic page', async () => {
    const { wrapper, router } = await mountPage()
    const push = vi.spyOn(router, 'push')
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()
    ocean.vm.$emit('selectDomain', { subject: 'mathematics', domain: 'mathematics:fractions' })
    await wrapper.vm.$nextTick()

    wrapper.findComponent({ name: 'TopicConstellation' }).vm.$emit('selectTopic', { id: 't1' })
    await vi.waitFor(() => {
      expect(push).toHaveBeenCalledWith('/learning/topic/t1')
    })
  })

  it('zoomOut from L1 clears the selection and resets the camera', async () => {
    const { wrapper } = await mountPage()
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()
    ocean.vm.$emit('selectDomain', {
      subject: 'mathematics',
      domain: 'mathematics:fractions',
    })
    await wrapper.vm.$nextTick()
    expect(ocean.props('selectedDomain')).toBe('fractions')

    ocean.vm.$emit('zoomOut')
    await wrapper.vm.$nextTick()

    expect(ocean.props('selectedSubject')).toBe('')
    expect(ocean.props('selectedDomain')).toBe('')
    expect(ocean.props('selectedTopicLevel')).toBe(false)
    expect(cameraSpies.resetCamera).toHaveBeenCalledTimes(1)
  })

  it('applies component-initiated oceanNavigation through the same handler', async () => {
    const { wrapper } = await mountPage()
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('oceanNavigation', {
      id: 'mathematics',
      x: 0,
      z: 0,
      worldRadius: 1,
    })
    await wrapper.vm.$nextTick()
    expect(ocean.props('selectedSubject')).toBe('mathematics')
    expect(cameraSpies.diveTo).toHaveBeenCalledWith('mathematics')

    ocean.vm.$emit('oceanNavigation', {
      id: 'fractions',
      subject: 'mathematics',
      x: 0,
      z: 0,
      worldRadius: 1,
    })
    await wrapper.vm.$nextTick()
    expect(ocean.props('selectedDomain')).toBe('fractions')
    expect(ocean.props('selectedTopicLevel')).toBe(true)

    ocean.vm.$emit('oceanNavigation', null)
    await wrapper.vm.$nextTick()
    expect(ocean.props('selectedSubject')).toBe('')
    expect(ocean.props('selectedDomain')).toBe('')
    expect(ocean.props('selectedTopicLevel')).toBe(false)
  })

  it('keeps state stable for the real selectDomain + oceanNavigation event pair', async () => {
    const { wrapper } = await mountPage()
    await settled(wrapper)

    const ocean = wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await wrapper.vm.$nextTick()

    // The real component emits both events for one domain pick.
    ocean.vm.$emit('selectDomain', {
      subject: 'mathematics',
      domain: 'mathematics:fractions',
    })
    ocean.vm.$emit('oceanNavigation', {
      id: 'mathematics:fractions',
      subject: 'mathematics',
      x: 0,
      z: 0,
      worldRadius: 1,
    })
    await wrapper.vm.$nextTick()

    expect(ocean.props('selectedSubject')).toBe('mathematics')
    expect(ocean.props('selectedDomain')).toBe('fractions')
    expect(ocean.props('selectedTopicLevel')).toBe(true)
    expect(
      wrapper.findComponent({ name: 'TopicConstellation' }).props('topics'),
    ).toHaveLength(2)
    // Only zoomOut/reset (not a domain dive) may reset the camera.
    expect(cameraSpies.resetCamera).not.toHaveBeenCalled()

    ocean.vm.$emit('zoomOut')
    await wrapper.vm.$nextTick()
    expect(cameraSpies.resetCamera).toHaveBeenCalledTimes(1)
    expect(ocean.props('selectedSubject')).toBe('')
    expect(ocean.props('selectedDomain')).toBe('')
  })

  it('keeps state page-local: remounting starts at L0 with an empty selection', async () => {
    const first = await mountPage()
    await settled(first.wrapper)
    const ocean = first.wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    ocean.vm.$emit('selectSubject', 'mathematics')
    await first.wrapper.vm.$nextTick()
    ocean.vm.$emit('selectDomain', { subject: 'mathematics', domain: 'mathematics:fractions' })
    await first.wrapper.vm.$nextTick()
    expect(ocean.props('selectedTopicLevel')).toBe(true)
    first.wrapper.unmount()

    const second = await mountPage()
    await settled(second.wrapper)
    const remounted = second.wrapper.findComponent({ name: 'KnowledgeOcean3D' })
    expect(remounted.props('selectedSubject')).toBe('')
    expect(remounted.props('selectedDomain')).toBe('')
    expect(remounted.props('selectedTopicLevel')).toBe(false)
    expect(second.wrapper.find('[data-test="constellation"]').exists()).toBe(false)
  })

  it('shows loading, error with retry, and empty states', async () => {
    mockIndex.mockImplementation(
      () => new Promise<typeof progressRows>(() => {}),
    )
    const pending = await mountPage()
    expect(pending.wrapper.find('[data-test="ocean3d-skeleton"]').exists()).toBe(true)
    pending.wrapper.unmount()

    mockIndex.mockRejectedValueOnce(new Error('boom'))
    const errorPage = await mountPage()
    await vi.waitFor(() => {
      expect(errorPage.wrapper.find('[data-test="ocean3d-error"]').exists()).toBe(true)
    })
    expect(errorPage.wrapper.text()).toContain('海洋暂时打不开')
    expect(errorPage.wrapper.find('[data-test="ocean3d-retry"]').exists()).toBe(true)

    mockIndex.mockImplementationOnce(() => Promise.resolve([]))
    mockTopics.mockResolvedValueOnce([])
    await errorPage.wrapper.find('[data-test="ocean3d-retry"]').trigger('click')
    await vi.waitFor(() => {
      expect(errorPage.wrapper.find('[data-test="ocean3d-error"]').exists()).toBe(false)
    })
    await vi.waitFor(() => {
      expect(errorPage.wrapper.find('[data-test="ocean3d-empty"]').exists()).toBe(true)
    })
    expect(errorPage.wrapper.text()).toContain('还没有知识点')
  })

  it('exposes localized keys in both locales', () => {
    for (const messages of [zhCN, enUS]) {
      const ocean3d = messages.learning.ocean3d
      expect(ocean3d).toMatchObject({
        title: expect.any(String),
        subtitle: expect.any(String),
        back: expect.any(String),
        retry: expect.any(String),
        error: expect.any(String),
        empty: expect.any(String),
        fallback: expect.any(String),
      })
      expect(ocean3d).not.toHaveProperty('hint')
      expect(ocean3d).not.toHaveProperty('topics')
      expect(ocean3d).not.toHaveProperty('backToOcean')
      expect(messages.learning.ocean.topics).toContain('{count}')
      expect(messages.learning.ocean.zoomHint).toEqual(expect.any(String))
      expect(messages.learning.ocean.backToOcean).toEqual(expect.any(String))
    }
  })

  it('registers /learning/ocean-3d as KnowledgeOcean3D after castle-3d', async () => {
    vi.doMock('@/api/learning', () => ({
      getMyLearningMapIndex: vi.fn(),
      getMyLearningStats: vi.fn(),
      getTopicIndex: vi.fn(),
    }))
    vi.resetModules()
    const { default: router } = await import('@/router')
    const index = router.getRoutes().find((route) => route.name === 'KnowledgeOcean3D')
    expect(index).toBeDefined()
    expect(index?.path).toBe('/learning/ocean-3d')

    const children = router.getRoutes().find((route) => route.name === 'KnowledgeCastle3D')
    expect(children).toBeDefined()
    const all = router.getRoutes().map((route) => route.path)
    expect(all.indexOf('/learning/ocean-3d')).toBeGreaterThan(all.indexOf('/learning/castle-3d'))
    vi.doUnmock('@/api/learning')
    vi.resetModules()
  })
})
